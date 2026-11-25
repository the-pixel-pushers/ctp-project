// Tuning model. The backend (GET /api/v1/settings) is the source of truth for params, bounds,
// defaults, sliders and presets; this file only resolves them into raw overrides and persists them.

import { useCallback, useEffect, useMemo, useState } from 'react'
import { API_BASE } from './api'

export interface ParamSpec {
  key: string
  label: string
  description: string
  kind: 'int' | 'float'
  min: number
  max: number
  step: number
  default: number
}

export interface SliderLevel {
  label: string
  values: Record<string, Record<string, number>>
}

export interface SliderSpec {
  id: string
  label: string
  description: string
  default_level: number
  levels: SliderLevel[]
}

export interface PresetSpec {
  id: string
  label: string
  description: string
  levels: Record<string, number>
}

export interface Catalog {
  params: Record<string, ParamSpec[]>
  sliders: SliderSpec[]
  presets: PresetSpec[]
  default_preset: string
}

/** analyzer -> param -> value */
export type TuningValues = Record<string, Record<string, number>>

const STORAGE_KEY = 'photocull.tuning.v1'
const EPSILON = 1e-9

export async function fetchCatalog(): Promise<Catalog> {
  const res = await fetch(`${API_BASE}/api/v1/settings`)
  if (!res.ok) throw new Error(`Backend returned ${res.status}`)
  return res.json()
}

export function defaultValues(catalog: Catalog): TuningValues {
  return Object.fromEntries(
    Object.entries(catalog.params).map(([name, specs]) => [name, Object.fromEntries(specs.map((s) => [s.key, s.default]))])
  )
}

function mergeLevels(base: TuningValues, levels: SliderLevel[]): TuningValues {
  const out: TuningValues = Object.fromEntries(Object.entries(base).map(([k, v]) => [k, { ...v }]))
  for (const level of levels) {
    for (const [analyzer, params] of Object.entries(level.values)) {
      if (out[analyzer]) Object.assign(out[analyzer], params)
    }
  }
  return out
}

export function valuesForPreset(catalog: Catalog, preset: PresetSpec): TuningValues {
  const levels = catalog.sliders.map((s) => s.levels[preset.levels[s.id] ?? s.default_level])
  return mergeLevels(defaultValues(catalog), levels)
}

export function setSliderLevel(values: TuningValues, slider: SliderSpec, level: number): TuningValues {
  return mergeLevels(values, [slider.levels[level]])
}

function levelMatches(values: TuningValues, level: SliderLevel): boolean {
  return Object.entries(level.values).every(([analyzer, params]) =>
    Object.entries(params).every(([key, v]) => Math.abs((values[analyzer]?.[key] ?? NaN) - v) < EPSILON)
  )
}

/** Index of the slider level matching `values`, or null when the user has set something custom. */
export function currentLevel(values: TuningValues, slider: SliderSpec): number | null {
  const i = slider.levels.findIndex((l) => levelMatches(values, l))
  return i === -1 ? null : i
}

export function valuesEqual(a: TuningValues, b: TuningValues): boolean {
  return Object.keys(a).every((name) =>
    Object.keys(a[name]).every((key) => Math.abs(a[name][key] - (b[name]?.[key] ?? NaN)) < EPSILON)
  )
}

export function activePreset(catalog: Catalog, values: TuningValues): PresetSpec | null {
  return catalog.presets.find((p) => valuesEqual(valuesForPreset(catalog, p), values)) ?? null
}

/** Only the values that differ from the server defaults; this is what gets sent and persisted. */
export function overridesOf(catalog: Catalog, values: TuningValues): TuningValues {
  const out: TuningValues = {}
  for (const [name, specs] of Object.entries(catalog.params)) {
    for (const spec of specs) {
      const v = values[name]?.[spec.key]
      if (v !== undefined && Math.abs(v - spec.default) >= EPSILON) (out[name] ??= {})[spec.key] = v
    }
  }
  return out
}

/** Saved overrides laid over the current defaults; unknown keys are dropped and values clamped. */
function restore(catalog: Catalog, saved: unknown): TuningValues {
  const values = defaultValues(catalog)
  if (typeof saved !== 'object' || saved === null) return values
  for (const [name, specs] of Object.entries(catalog.params)) {
    const group = (saved as Record<string, unknown>)[name]
    if (typeof group !== 'object' || group === null) continue
    for (const spec of specs) {
      const v = (group as Record<string, unknown>)[spec.key]
      if (typeof v === 'number' && Number.isFinite(v)) values[name][spec.key] = clamp(spec, v)
    }
  }
  return values
}

export function clamp(spec: ParamSpec, v: number): number {
  const bounded = Math.min(spec.max, Math.max(spec.min, v))
  return spec.kind === 'int' ? Math.round(bounded) : bounded
}

export function useTuning() {
  const [catalog, setCatalog] = useState<Catalog | null>(null)
  const [values, setValues] = useState<TuningValues>({})
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    fetchCatalog()
      .then((c) => {
        if (cancelled) return
        let saved: unknown = null
        try {
          saved = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? 'null')
        } catch {
          /* corrupt entry: fall back to defaults */
        }
        setCatalog(c)
        setValues(restore(c, saved))
      })
      .catch(() => !cancelled && setError('Tuning unavailable: could not load settings from the backend.'))
    return () => {
      cancelled = true
    }
  }, [])

  const overrides = useMemo(() => (catalog ? overridesOf(catalog, values) : {}), [catalog, values])

  useEffect(() => {
    if (!catalog) return
    if (Object.keys(overrides).length === 0) localStorage.removeItem(STORAGE_KEY)
    else localStorage.setItem(STORAGE_KEY, JSON.stringify(overrides))
  }, [catalog, overrides])

  const setLevel = useCallback(
    (slider: SliderSpec, level: number) => setValues((prev) => setSliderLevel(prev, slider, level)),
    []
  )
  const applyPreset = useCallback(
    (preset: PresetSpec) => catalog && setValues(valuesForPreset(catalog, preset)),
    [catalog]
  )
  const resetSlider = useCallback(
    (slider: SliderSpec) => setValues((prev) => setSliderLevel(prev, slider, slider.default_level)),
    []
  )
  const resetAll = useCallback(() => catalog && setValues(defaultValues(catalog)), [catalog])
  /** Put back a previously captured `values` snapshot (used by Undo). */
  const restoreValues = useCallback((snapshot: TuningValues) => setValues(snapshot), [])

  return { catalog, values, overrides, error, setLevel, applyPreset, resetSlider, resetAll, restoreValues }
}

export type Tuning = ReturnType<typeof useTuning>