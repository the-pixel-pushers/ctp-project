import { useState } from 'react'
import { Upload, FileImage, X, ArrowUpRight, Layers } from 'lucide-react'
import { MOCK_STAGED_FILES, type StagedFile } from '../data/mockData'

export function UploadView() {
  const [stagedFiles, setStagedFiles] = useState<StagedFile[]>(MOCK_STAGED_FILES)
  const [isDragging, setIsDragging] = useState(false)

  const removeFile = (id: string) => {
    setStagedFiles((prev) => prev.filter((f) => f.id !== id))
  }

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

      {/* Drag & Drop Zone */}
      <div
        onDragEnter={(e) => { e.preventDefault(); setIsDragging(true) }}
        onDragLeave={(e) => { e.preventDefault(); setIsDragging(false) }}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => { e.preventDefault(); setIsDragging(false) }}
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

        <div className="relative flex flex-col items-center justify-center py-24 px-6">
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

          <button className="px-6 py-3 rounded-full bg-white text-black text-sm font-semibold transition-all duration-300 hover:scale-105 hover:shadow-[0_0_30px_rgba(255,255,255,0.1)] cursor-pointer flex items-center gap-2">
            Choose Files
            <ArrowUpRight className="w-4 h-4" />
          </button>

          <div className="flex items-center gap-4 mt-8">
            {['JPG', 'PNG', 'RAW', 'HEIF'].map((fmt) => (
              <span
                key={fmt}
                className="text-[10px] font-mono text-neutral-600 tracking-wider border border-white/[0.04] rounded px-2 py-0.5 uppercase"
              >
                {fmt}
              </span>
            ))}
          </div>
        </div>
      </div>

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
              onClick={() => setStagedFiles([])}
              className="text-[11px] font-mono text-neutral-600 hover:text-red-400 transition-colors cursor-pointer tracking-wide uppercase"
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
                  <p className="text-[11px] font-mono text-neutral-600">{file.size}</p>
                </div>

                <div className="flex-shrink-0 flex items-center gap-3">
                  <div className="flex items-center gap-2">
                    <div className="h-[3px] w-16 rounded-full bg-white/[0.06] overflow-hidden">
                      <div className="h-full w-full bg-gradient-to-r from-violet-400 to-fuchsia-400 rounded-full" />
                    </div>
                    <span className="text-[10px] font-mono text-emerald-400/80">READY</span>
                  </div>
                </div>

                <button
                  onClick={() => removeFile(file.id)}
                  className="p-1.5 rounded-lg text-neutral-700 hover:text-red-400 hover:bg-red-500/[0.06] transition-all duration-200 opacity-0 group-hover:opacity-100 cursor-pointer"
                >
                  <X className="w-4 h-4" strokeWidth={1.5} />
                </button>
              </div>
            ))}
          </div>

          <div className="flex items-center justify-between pt-2">
            <p className="text-[11px] font-mono text-neutral-600">
              {stagedFiles.reduce((acc, f) => acc + parseFloat(f.size), 0).toFixed(1)} MB total
            </p>
            <button className="px-6 py-2.5 rounded-full bg-white text-black text-[13px] font-semibold transition-all duration-300 hover:scale-105 hover:shadow-[0_0_30px_rgba(255,255,255,0.1)] cursor-pointer flex items-center gap-2">
              Import {stagedFiles.length} file{stagedFiles.length !== 1 && 's'}
              <ArrowUpRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
