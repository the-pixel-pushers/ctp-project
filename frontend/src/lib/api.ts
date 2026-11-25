import type { Photo, QualityIssue } from './photos'
import type { TuningValues } from './tuning'

// In dev, Vite proxies /api to the FastAPI backend (see vite.config.ts).
// Set VITE_API_URL to point at a backend elsewhere (e.g. http://localhost:8000).
export const API_BASE: string = import.meta.env.VITE_API_URL ?? ''

/** Must match PHOTOSORT_MAX_FILES_PER_BATCH on the backend. */
const MAX_FILES_PER_BATCH = 100

export interface AnalysisOut {
  status: 'success' | 'error'
  flag: string | null
  score: number | null
  metrics: Record<string, number>
  error: string | null
}

export interface ImageResult {
  filename: string
  status: 'success' | 'error'
  analyses: Record<string, AnalysisOut>
  error: string | null
}

interface CullBatchResponse {
  batch_id: string
  total_processed: number
  results: ImageResult[]
}

async function postBatch(files: File[], overrides: TuningValues): Promise<ImageResult[]> {
  const form = new FormData()
  for (const file of files) form.append('files', file, file.name)
  if (Object.keys(overrides).length > 0) form.append('tuning', JSON.stringify(overrides))

  let res: Response
  try {
    res = await fetch(`${API_BASE}/api/v1/cull-batch`, { method: 'POST', body: form })
  } catch {
    throw new Error('Could not reach the backend. Is it running on http://localhost:8000?')
  }
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    throw new Error(body?.detail ? String(body.detail) : `Backend returned ${res.status}`)
  }
  const data: CullBatchResponse = await res.json()
  return data.results
}

/**
 * Send files to the backend for analysis. Results come back in the same order as `files`
 * (the backend preserves order), chunked to respect the per-batch limit. `overrides` are the
 * user's tuned analyzer settings (only values that differ from the server defaults).
 */
export async function cullPhotos(files: File[], overrides: TuningValues = {}): Promise<ImageResult[]> {
  const results: ImageResult[] = []
  for (let i = 0; i < files.length; i += MAX_FILES_PER_BATCH) {
    results.push(...(await postBatch(files.slice(i, i + MAX_FILES_PER_BATCH), overrides)))
  }
  return results
}

/** The analysis-derived Photo fields, shared by first analysis and re-analysis. */
export function analysisFields(analyses: Record<string, AnalysisOut>): Pick<Photo, 'issues' | 'flags' | 'metrics'> {
  return {
    issues: issuesFromAnalyses(analyses),
    flags: Object.fromEntries(Object.entries(analyses).map(([name, a]) => [name, a.flag ?? 'ERROR'])),
    metrics: Object.fromEntries(Object.entries(analyses).map(([name, a]) => [name, a.metrics ?? {}])),
  }
}

/** Translate the backend's analyzer flags into the issue tags the gallery groups by. */
export function issuesFromAnalyses(analyses: Record<string, AnalysisOut>): QualityIssue[] {
  const issues: QualityIssue[] = []
  if (analyses.overexposure?.flag === 'OVEREXPOSED') issues.push('overexposed')
  if (analyses.underexposure?.flag === 'UNDEREXPOSED') issues.push('underexposed')
  // SHALLOW_FOCUS (intentional background blur) counts as fine.
  if (analyses.blur?.flag === 'BLURRY') issues.push('blurry')
  return issues
}
