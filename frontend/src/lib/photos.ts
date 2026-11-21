export type QualityIssue = 'overexposed' | 'underexposed' | 'blurry'

/** A photo that has been analyzed by the backend and lives in the gallery. */
export interface Photo {
  id: string
  fileName: string
  /** The original upload, kept so downloads are full resolution. */
  file: File
  /** Object URL pointing at the local file (the backend is stateless and doesn't store images). */
  url: string
  resolution: string
  size: string
  issues: QualityIssue[]
  /** Raw backend flags, e.g. { blur: 'SHALLOW_FOCUS', overexposure: 'OK' } */
  flags: Record<string, string>
  liked: boolean
  dateAdded: string
}

export interface StagedFile {
  id: string
  file: File
  fileName: string
  size: string
  thumbnail: string
  resolution: string
  status: 'ready' | 'uploading' | 'error'
  error?: string
}

export const ACCEPTED_TYPES = ['image/jpeg', 'image/png']
export const ACCEPTED_EXTENSIONS = ['.jpg', '.jpeg', '.png']
export const MAX_FILE_BYTES = 25 * 1024 * 1024

export const ISSUE_META: Record<QualityIssue, { label: string; color: string; bgColor: string; borderColor: string; icon: string }> = {
  overexposed: {
    label: 'Over-exposed',
    color: 'text-amber-300',
    bgColor: 'bg-amber-400/[0.08]',
    borderColor: 'border-amber-400/20',
    icon: '☀️',
  },
  underexposed: {
    label: 'Under-exposed',
    color: 'text-blue-300',
    bgColor: 'bg-blue-400/[0.08]',
    borderColor: 'border-blue-400/20',
    icon: '🌙',
  },
  blurry: {
    label: 'Blurry',
    color: 'text-rose-300',
    bgColor: 'bg-rose-400/[0.08]',
    borderColor: 'border-rose-400/20',
    icon: '◎',
  },
}

export function formatSize(bytes: number): string {
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function isAcceptedFile(file: File): boolean {
  const name = file.name.toLowerCase()
  return ACCEPTED_TYPES.includes(file.type) || ACCEPTED_EXTENSIONS.some((ext) => name.endsWith(ext))
}

/** Read an image's pixel dimensions from an object URL. */
export function readResolution(url: string): Promise<string> {
  return new Promise((resolve) => {
    const img = new Image()
    img.onload = () => resolve(`${img.naturalWidth} × ${img.naturalHeight}`)
    img.onerror = () => resolve('—')
    img.src = url
  })
}
