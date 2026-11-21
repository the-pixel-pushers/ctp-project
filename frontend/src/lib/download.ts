import { zipSync, type Zippable } from 'fflate'
import type { Photo } from './photos'

function saveBlob(blob: Blob, fileName: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = fileName
  document.body.appendChild(a)
  a.click()
  a.remove()
  // Give the browser a moment to start the download before freeing the URL.
  setTimeout(() => URL.revokeObjectURL(url), 10_000)
}

/** Avoid clobbering files that share a name inside the zip: "a.jpg", "a (1).jpg", ... */
function uniqueName(name: string, used: Set<string>): string {
  if (!used.has(name)) return name
  const dot = name.lastIndexOf('.')
  const base = dot > 0 ? name.slice(0, dot) : name
  const ext = dot > 0 ? name.slice(dot) : ''
  for (let i = 1; ; i++) {
    const candidate = `${base} (${i})${ext}`
    if (!used.has(candidate)) return candidate
  }
}

/**
 * Download the original, full-resolution files. One photo downloads as-is;
 * several are bundled into a single zip (stored uncompressed: JPG/PNG are already compressed).
 */
export async function downloadPhotos(photos: Photo[]): Promise<void> {
  if (photos.length === 0) return
  if (photos.length === 1) {
    saveBlob(photos[0].file, photos[0].fileName)
    return
  }

  const used = new Set<string>()
  const entries: Zippable = {}
  for (const photo of photos) {
    const name = uniqueName(photo.fileName, used)
    used.add(name)
    entries[name] = [new Uint8Array(await photo.file.arrayBuffer()), { level: 0 }]
  }
  const zipped = zipSync(entries)
  const date = new Date().toISOString().slice(0, 10)
  saveBlob(new Blob([zipped as BlobPart], { type: 'application/zip' }), `photocull-${date}.zip`)
}
