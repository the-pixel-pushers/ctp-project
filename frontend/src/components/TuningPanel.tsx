import { useState } from 'react'
import { ChevronDown, Loader2, RefreshCw, RotateCcw, SlidersHorizontal } from 'lucide-react'
import { activePreset, currentLevel, type Tuning } from '../lib/tuning'

interface TuningPanelProps {
  tuning: Tuning
  /** Photos already in the gallery; when > 0 a "Re-analyze" action is offered. */
  photoCount: number
  isReanalyzing: boolean
  onReanalyze: () => void
}

function ResetButton({ onClick, title }: { onClick: () => void; title: string }) {
  return (
    <button
      onClick={onClick}
      title={title}
      aria-label={title}
      className="p-1 rounded text-neutral-500 hover:text-white hover:bg-white/[0.06] transition-colors cursor-pointer"
    >
      <RotateCcw className="w-3 h-3" strokeWidth={1.5} />
    </button>
  )
}

export function TuningPanel({ tuning, photoCount, isReanalyzing, onReanalyze }: TuningPanelProps) {
  const { catalog, values, overrides, error } = tuning
  const [open, setOpen] = useState(false)

  if (error) {
    return <p className="mb-6 text-[11px] font-mono text-neutral-600">{error}</p>
  }
  if (!catalog) return null

  const preset = activePreset(catalog, values)
  const isModified = Object.keys(overrides).length > 0
  const modifiedCount = catalog.sliders.filter((s) => currentLevel(values, s) !== s.default_level).length

  return (
    <section className="mb-8 rounded-2xl border border-white/[0.06] bg-white/[0.02]">
      <button
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="w-full flex items-center gap-3 px-4 py-3 cursor-pointer"
      >
        <SlidersHorizontal className="w-4 h-4 text-neutral-500" strokeWidth={1.5} />
        <span className="text-[13px] font-semibold text-neutral-300">Detection tuning</span>
        <span className="font-mono text-[11px] px-2 py-0.5 rounded-full border border-white/[0.06] bg-white/[0.03] text-neutral-400">
          {preset ? preset.label : 'Custom'}
        </span>
        {isModified && (
          <span className="flex items-center gap-1.5 text-[11px] font-mono text-violet-300" title="Differs from defaults">
            <span className="w-1.5 h-1.5 rounded-full bg-violet-400" />
            {modifiedCount > 0 ? `${modifiedCount} changed` : 'changed'}
          </span>
        )}
        <ChevronDown
          className={`ml-auto w-4 h-4 text-neutral-500 transition-transform ${open ? 'rotate-180' : ''}`}
          strokeWidth={1.5}
        />
      </button>

      {open && (
        <div className="px-4 pb-4 space-y-5 border-t border-white/[0.04] pt-4">
          {/* Presets */}
          <div className="space-y-2">
            <p className="text-[11px] font-mono uppercase tracking-wider text-neutral-600">Scene preset</p>
            <div className="flex flex-wrap gap-2">
              {catalog.presets.map((p) => (
                <button
                  key={p.id}
                  onClick={() => tuning.applyPreset(p)}
                  title={p.description}
                  className={`px-3 py-1.5 rounded-full text-[12px] font-medium border transition-colors cursor-pointer ${
                    preset?.id === p.id
                      ? 'bg-white text-black border-white'
                      : 'border-white/[0.08] text-neutral-400 hover:text-white hover:border-white/[0.2]'
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          {/* Plain-language sliders */}
          <div className="grid gap-x-8 gap-y-4 sm:grid-cols-2">
            {catalog.sliders.map((slider) => {
              const level = currentLevel(values, slider)
              const isDefault = level === slider.default_level
              return (
                <div key={slider.id} className="space-y-1.5">
                  <div className="flex items-center gap-2">
                    <label htmlFor={`slider-${slider.id}`} className="text-[12px] font-medium text-neutral-300">
                      {slider.label}
                    </label>
                    {!isDefault && <span className="w-1.5 h-1.5 rounded-full bg-violet-400" title="Changed" />}
                    <span className="ml-auto text-[11px] font-mono text-neutral-500">
                      {level === null ? 'Custom' : slider.levels[level].label}
                    </span>
                    {!isDefault && (
                      <ResetButton onClick={() => tuning.resetSlider(slider)} title={`Reset ${slider.label}`} />
                    )}
                  </div>
                  <input
                    id={`slider-${slider.id}`}
                    type="range"
                    min={0}
                    max={slider.levels.length - 1}
                    step={1}
                    value={level ?? slider.default_level}
                    onChange={(e) => tuning.setLevel(slider, Number(e.target.value))}
                    className="w-full accent-violet-400 cursor-pointer"
                  />
                  <p className="text-[11px] text-neutral-600">{slider.description}</p>
                </div>
              )
            })}
          </div>

          {/* Actions */}
          <div className="flex flex-wrap items-center gap-3 pt-1">
            <button
              onClick={tuning.resetAll}
              disabled={!isModified}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[12px] font-medium border border-white/[0.08] text-neutral-400 hover:text-white hover:border-white/[0.2] transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <RotateCcw className="w-3 h-3" strokeWidth={1.5} />
              Reset all to defaults
            </button>
            {photoCount > 0 && (
              <button
                onClick={onReanalyze}
                disabled={isReanalyzing}
                className="flex items-center gap-1.5 px-4 py-1.5 rounded-full text-[12px] font-semibold bg-white text-black hover:scale-105 transition-transform cursor-pointer disabled:opacity-50 disabled:hover:scale-100"
              >
                {isReanalyzing ? (
                  <Loader2 className="w-3 h-3 animate-spin" />
                ) : (
                  <RefreshCw className="w-3 h-3" strokeWidth={1.5} />
                )}
                Re-analyze {photoCount} photo{photoCount !== 1 && 's'}
              </button>
            )}
            <p className="text-[11px] text-neutral-600">
              {photoCount > 0
                ? 'Settings apply to new uploads; re-analyze to update photos already in the gallery.'
                : 'Settings apply to the next import.'}
            </p>
          </div>
        </div>
      )}
    </section>
  )
}
