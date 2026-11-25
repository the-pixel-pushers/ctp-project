import { useRef, useState } from 'react'
import { Upload, X, ArrowUpRight, Layers, Loader2, AlertCircle } from 'lucide-react'
import {
  ACCEPTED_EXTENSIONS,
  ACCEPTED_TYPES,
  MAX_FILE_BYTES,
  formatSize,
  isAcceptedFile,
  readResolution,
  type Photo,
  type StagedFile,
} from '../lib/photos'
import { analysisFields, cullPhotos } from '../lib/api'
import type { TuningValues } from '../lib/tuning'

interface UploadViewProps {
  onAnalyzed: (photos: Photo[]) => void
  /** User-tuned analyzer settings sent with the batch (empty = server defaults). */
  overrides: TuningValues
}

export function UploadView({ onAnalyzed, overrides }: UploadViewProps) {
  const [stagedFiles, setStagedFiles] = useState<StagedFile[]>([])
  const [isDragging, setIsDragging] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const addFiles = async (fileList: FileList | File[]) => {
    const files = Array.from(fileList)
    const accepted = files.filter(isAcceptedFile)
    const rejected = files.length - accepted.length
    setError(rejected > 0 ? `${rejected} file${rejected !== 1 ? 's' : ''} skipped — only JPG and PNG are supported` : null)

    const staged = await Promise.all(
      accepted.map(async (file): Promise<StagedFile> => {
        const thumbnail = URL.createObjectURL(file)
        const tooBig = file.size > MAX_FILE_BYTES
        return {
          id: crypto.randomUUID(),
          file,
          fileName: file.name,
          size: formatSize(file.size),
          thumbnail,
          resolution: await readResolution(thumbnail),
          status: tooBig ? 'error' : 'ready',
          error: tooBig ? 'Larger than 25 MB' : undefined,
        }
      })
    )
    setStagedFiles((prev) => [...prev, ...staged])
  }

  const removeFile = (id: string) => {
    setStagedFiles((prev) => {
      const target = prev.find((f) => f.id === id)
      if (target) URL.revokeObjectURL(target.thumbnail)
      return prev.filter((f) => f.id !== id)
    })
  }

  const clearAll = () => {
    stagedFiles.forEach((f) => URL.revokeObjectURL(f.thumbnail))
    setStagedFiles([])
    setError(null)
  }

  const importFiles = async () => {
    const toUpload = stagedFiles.filter((f) => f.status !== 'error')
    if (toUpload.length === 0 || isUploading) return

    setIsUploading(true)
    setError(null)
    const uploadingIds = new Set(toUpload.map((f) => f.id))
    setStagedFiles((prev) => prev.map((f) => (uploadingIds.has(f.id) ? { ...f, status: 'uploading' } : f)))

    try {
      const results = await cullPhotos(
        toUpload.map((f) => f.file),
        overrides
      )
      const today = new Date().toISOString().slice(0, 10)
      const analyzed: Photo[] = []
      const failed = new Map<string, string>()

      results.forEach((result, i) => {
        const staged = toUpload[i]
        if (result.status === 'error') {
          failed.set(staged.id, result.error ?? 'Analysis failed')
          return
        }
        analyzed.push({
          id: staged.id,
          fileName: staged.fileName,
          file: staged.file,
          url: staged.thumbnail, // ownership of the object URL moves to the gallery
          resolution: staged.resolution,
          size: staged.size,
          ...analysisFields(result.analyses),
          liked: false,
          dateAdded: today,
        })
      })

      // Keep only files that failed (plus any that were already invalid) in the staging list.
      setStagedFiles((prev) =>
        prev
          .filter((f) => !uploadingIds.has(f.id) || failed.has(f.id))
          .map((f) => (failed.has(f.id) ? { ...f, status: 'error', error: failed.get(f.id) } : f))
      )
      if (failed.size > 0) {
        setError(`${failed.size} file${failed.size !== 1 ? 's' : ''} could not be analyzed`)
      }
      if (analyzed.length > 0) onAnalyzed(analyzed)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Upload failed')
      setStagedFiles((prev) => prev.map((f) => (uploadingIds.has(f.id) ? { ...f, status: 'ready' } : f)))
    } finally {
      setIsUploading(false)
    }
  }

  const readyCount = stagedFiles.filter((f) => f.status !== 'error').length
  const totalBytes = stagedFiles.reduce((acc, f) => acc + f.file.size, 0)

  return (
    <div className="space-y-10">
      {/* Hero Section */}
      <div className="text-center space-y-4 max-w-2xl mx-auto">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-white/[0.06] bg-white/[0.03] text-[11px] font-mono text-neutral-500 uppercase tracking-widest">
          <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          Ready to import
        </div>
        <h1 className="text-5xl sm:text-6xl font-bold tracking-tight text-white leading-[1.05]">
          Drop your
          <br />
          <span className="bg-gradient-to-r from-violet-300 via-fuchsia-300 to-purple-400 bg-clip-text text-transparent">
            photos here
          </span>
        </h1>
        <p className="text-neutral-500 text-base max-w-md mx-auto leading-relaxed">
          Import your shoots and we'll detect exposure issues and blur automatically.
        </p>
      </div>

      {/* Hidden file input */}
      <input
        ref={inputRef}
        type="file"
        multiple
        accept={[...ACCEPTED_TYPES, ...ACCEPTED_EXTENSIONS].join(',')}
        className="hidden"
        onChange={(e) => {
          if (e.target.files) addFiles(e.target.files)
          e.target.value = '' // allow re-selecting the same files
        }}
      />

      {/* Drag & Drop Zone */}
      <div
        onClick={() => inputRef.current?.click()}
        onDragEnter={(e) => { e.preventDefault(); setIsDragging(true) }}
        onDragLeave={(e) => { e.preventDefault(); setIsDragging(false) }}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault()
          setIsDragging(false)
          if (e.dataTransfer.files.length > 0) addFiles(e.dataTransfer.files)
        }}
        className={`
          relative group rounded-2xl border transition-all duration-500 cursor-pointer overflow-hidden
          ${isDragging
            ? 'border-violet-400/40 bg-violet-500/[0.06] scale-[1.005]'
            : 'border-white/[0.06] bg-white/[0.02] hover:border-white/[0.1] hover:bg-white/[0.03]'
          }
        `}
      >
        {isDragging && (
          <div className="absolute inset-0 bg-gradient-to-b from-violet-500/[0.08] to-transparent pointer-events-none" />
        )}

        <div className="relative flex flex-col items-center justify-center py-24 px-6 pointer-events-none">
          <div
            className={`
              flex items-center justify-center w-14 h-14 rounded-2xl mb-8 transition-all duration-500
              border
              ${isDragging
                ? 'border-violet-400/30 bg-violet-500/10 shadow-[0_0_40px_rgba(139,92,246,0.15)]'
                : 'border-white/[0.06] bg-white/[0.03] group-hover:border-white/[0.1]'
              }
            `}
          >
            <Upload
              className={`w-6 h-6 transition-all duration-500 ${
                isDragging ? 'text-violet-300' : 'text-neutral-500 group-hover:text-neutral-300'
              }`}
              strokeWidth={1.5}
            />
          </div>

          <p className="text-lg font-medium text-neutral-200 mb-1.5">
            Drag & drop files
          </p>
          <p className="text-sm text-neutral-600 mb-8">
            or click anywhere in this area to browse
          </p>

          <span className="px-6 py-3 rounded-full bg-white text-black text-sm font-semibold transition-all duration-300 group-hover:scale-105 group-hover:shadow-[0_0_30px_rgba(255,255,255,0.1)] flex items-center gap-2">
            Choose Files
            <ArrowUpRight className="w-4 h-4" />
          </span>

          <div className="flex items-center gap-4 mt-8">
            {['JPG', 'PNG'].map((fmt) => (
              <span
                key={fmt}
                className="text-[10px] font-mono text-neutral-600 tracking-wider border border-white/[0.04] rounded px-2 py-0.5 uppercase"
              >
                {fmt}
              </span>
            ))}
            <span className="text-[10px] font-mono text-neutral-700 tracking-wider">≤ 25 MB each</span>
          </div>
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div className="flex items-center gap-3 px-4 py-3 rounded-xl border border-red-400/20 bg-red-500/[0.06] text-red-300 text-[13px]">
          <AlertCircle className="w-4 h-4 flex-shrink-0" strokeWidth={1.5} />
          <span className="flex-1">{error}</span>
          <button onClick={() => setError(null)} className="p-1 rounded hover:bg-red-500/10 cursor-pointer">
            <X className="w-3.5 h-3.5" strokeWidth={1.5} />
          </button>
        </div>
      )}

      {/* Staged Files */}
      {stagedFiles.length > 0 && (
        <div className="space-y-5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Layers className="w-4 h-4 text-neutral-500" strokeWidth={1.5} />
              <h2 className="text-sm font-semibold text-neutral-300 tracking-wide">
                Staged
              </h2>
              <span className="font-mono text-[11px] text-neutral-600 bg-white/[0.03] border border-white/[0.05] px-2 py-0.5 rounded-full">
                {stagedFiles.length}
              </span>
            </div>
            <button
              onClick={clearAll}
              disabled={isUploading}
              className="text-[11px] font-mono text-neutral-600 hover:text-red-400 transition-colors cursor-pointer tracking-wide uppercase disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Clear all
            </button>
          </div>

          <div className="grid gap-2">
            {stagedFiles.map((file) => (
              <div
                key={file.id}
                className="flex items-center gap-4 p-3 rounded-xl border border-white/[0.04] bg-white/[0.015] hover:bg-white/[0.025] hover:border-white/[0.08] transition-all duration-300 group"
              >
                <div className="relative w-11 h-11 rounded-lg overflow-hidden flex-shrink-0 border border-white/[0.06]">
                  <img
                    src={file.thumbnail}
                    alt={file.fileName}
                    className="w-full h-full object-cover"
                  />
                </div>

                <div className="flex-1 min-w-0">
                  <p className="text-[13px] font-medium text-neutral-200 truncate">
                    {file.fileName}
                  </p>
                  <p className="text-[11px] font-mono text-neutral-600">
                    {file.size} · {file.resolution}
                  </p>
                </div>

                <div className="flex-shrink-0 flex items-center gap-3">
                  {file.status === 'ready' && (
                    <div className="flex items-center gap-2">
                      <div className="h-[3px] w-16 rounded-full bg-white/[0.06] overflow-hidden">
                        <div className="h-full w-full bg-gradient-to-r from-violet-400 to-fuchsia-400 rounded-full" />
                      </div>
                      <span className="text-[10px] font-mono text-emerald-400/80">READY</span>
                    </div>
                  )}
                  {file.status === 'uploading' && (
                    <div className="flex items-center gap-2 text-violet-300">
                      <Loader2 className="w-3.5 h-3.5 animate-spin" strokeWidth={1.5} />
                      <span className="text-[10px] font-mono">ANALYZING</span>
                    </div>
                  )}
                  {file.status === 'error' && (
                    <span className="text-[10px] font-mono text-red-400/80 uppercase" title={file.error}>
                      {file.error ?? 'Error'}
                    </span>
                  )}
                </div>

                <button
                  onClick={() => removeFile(file.id)}
                  disabled={file.status === 'uploading'}
                  className="p-1.5 rounded-lg text-neutral-700 hover:text-red-400 hover:bg-red-500/[0.06] transition-all duration-200 opacity-0 group-hover:opacity-100 cursor-pointer disabled:hidden"
                >
                  <X className="w-4 h-4" strokeWidth={1.5} />
                </button>
              </div>
            ))}
          </div>

          <div className="flex items-center justify-between pt-2">
            <p className="text-[11px] font-mono text-neutral-600">
              {formatSize(totalBytes)} total
            </p>
            <button
              onClick={importFiles}
              disabled={readyCount === 0 || isUploading}
              className="px-6 py-2.5 rounded-full bg-white text-black text-[13px] font-semibold transition-all duration-300 hover:scale-105 hover:shadow-[0_0_30px_rgba(255,255,255,0.1)] cursor-pointer flex items-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:scale-100"
            >
              {isUploading ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  Analyzing…
                </>
              ) : (
                <>
                  Import {readyCount} file{readyCount !== 1 && 's'}
                  <ArrowUpRight className="w-3.5 h-3.5" />
                </>
              )}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
