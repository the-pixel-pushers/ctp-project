import { useState } from 'react'
import { Check, Download, Heart, Trash2 } from 'lucide-react'
import { ISSUE_META, type Photo } from '../lib/photos'

interface PhotoCardProps {
  photo: Photo
  selected: boolean
  /** True when at least one photo is selected — checkboxes stay visible. */
  selectionMode: boolean
  onToggleSelect: (id: string, shiftKey: boolean) => void
  onToggleLike: (id: string) => void
  onDiscard: (id: string) => void
  onDownload: (id: string) => void
  compact?: boolean
}

export function PhotoCard({
  photo,
  selected,
  selectionMode,
  onToggleSelect,
  onToggleLike,
  onDiscard,
  onDownload,
  compact = false,
}: PhotoCardProps) {
  const [isHovered, setIsHovered] = useState(false)
  const hasIssues = photo.issues.length > 0
  const showCheckbox = selected || selectionMode || isHovered

  return (
    <div
      className={`group relative overflow-hidden transition-all duration-300 cursor-pointer rounded-xl select-none ${
        selected
          ? 'ring-2 ring-violet-400 ring-offset-2 ring-offset-[#0a0a0a]'
          : hasIssues ? 'ring-1 ring-white/[0.04]' : ''
      }`}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      onClick={(e) => onToggleSelect(photo.id, e.shiftKey)}
      onDoubleClick={(e) => { e.preventDefault(); onToggleLike(photo.id) }}
    >
      {/* Image */}
      <div className={`relative overflow-hidden ${compact ? 'aspect-square' : 'aspect-[3/2]'}`}>
        <img
          src={photo.url}
          alt={photo.fileName}
          draggable={false}
          className={`w-full h-full object-cover transition-all duration-700 ease-out ${
            isHovered ? 'scale-[1.08]' : 'scale-100'
          } ${selected ? 'scale-[0.97]' : ''}`}
        />

        {/* Vignette */}
        <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-black/0 to-black/20" />

        {/* Hover / selected overlay */}
        <div
          className={`absolute inset-0 transition-opacity duration-300 ${
            selected ? 'bg-violet-500/15 opacity-100' : 'bg-black/30 backdrop-blur-[1px]'
          } ${selected || isHovered ? 'opacity-100' : 'opacity-0'}`}
        />

        {/* Issue pills — top left, always visible */}
        <div className="absolute top-2.5 left-2.5 z-20 flex flex-wrap gap-1 pr-24">
          {hasIssues ? (
            photo.issues.map((issue) => {
              const meta = ISSUE_META[issue]
              return (
                <span
                  key={issue}
                  className={`inline-flex items-center gap-1 text-[9px] font-mono font-semibold uppercase tracking-[0.12em] px-2 py-0.5 rounded-full backdrop-blur-md border ${meta.bgColor} ${meta.color} ${meta.borderColor}`}
                >
                  <span className="text-[8px]">{meta.icon}</span>
                  {meta.label}
                </span>
              )
            })
          ) : (
            <span className="inline-flex items-center gap-1 text-[9px] font-mono font-semibold uppercase tracking-[0.12em] px-2 py-0.5 rounded-full backdrop-blur-md border bg-emerald-400/[0.08] text-emerald-300 border-emerald-400/20">
              ✓ Sharp
            </span>
          )}
        </div>

        {/* Top right: hover actions + selection checkbox */}
        <div className="absolute top-2.5 right-2.5 z-20 flex items-center gap-1.5">
          <div
            className={`flex items-center gap-1.5 transition-all duration-300 ${
              isHovered ? 'opacity-100 translate-y-0' : 'opacity-0 -translate-y-1 pointer-events-none'
            }`}
          >
            <button
              title="Download original"
              onClick={(e) => { e.stopPropagation(); onDownload(photo.id) }}
              className="p-2 rounded-full backdrop-blur-md transition-all duration-200 cursor-pointer border bg-black/30 text-white/70 border-white/[0.08] hover:bg-black/50 hover:text-white"
            >
              <Download className="w-3.5 h-3.5" strokeWidth={1.5} />
            </button>
            <button
              title="Delete"
              onClick={(e) => { e.stopPropagation(); onDiscard(photo.id) }}
              className="p-2 rounded-full backdrop-blur-md transition-all duration-200 cursor-pointer border bg-black/30 text-white/70 border-white/[0.08] hover:bg-red-500/20 hover:text-red-300 hover:border-red-400/20"
            >
              <Trash2 className="w-3.5 h-3.5" strokeWidth={1.5} />
            </button>
          </div>

          <button
            title={selected ? 'Deselect' : 'Select'}
            onClick={(e) => { e.stopPropagation(); onToggleSelect(photo.id, e.shiftKey) }}
            className={`w-6 h-6 rounded-full border-2 flex items-center justify-center transition-all duration-200 cursor-pointer ${
              selected
                ? 'bg-violet-400 border-violet-400 text-black opacity-100'
                : `bg-black/30 border-white/60 text-transparent hover:border-white ${showCheckbox ? 'opacity-100' : 'opacity-0'}`
            }`}
          >
            <Check className="w-3.5 h-3.5" strokeWidth={3} />
          </button>
        </div>

        {/* Like button — bottom right, always visible when liked */}
        <button
          title={photo.liked ? 'Unlike' : 'Like (or double-click)'}
          onClick={(e) => { e.stopPropagation(); onToggleLike(photo.id) }}
          className={`absolute bottom-2.5 right-2.5 z-30 p-2 rounded-full backdrop-blur-md transition-all duration-200 cursor-pointer border ${
            photo.liked
              ? 'bg-rose-500/20 text-rose-300 border-rose-400/20 opacity-100'
              : `bg-black/30 text-white/70 border-white/[0.08] hover:bg-black/50 hover:text-white ${isHovered ? 'opacity-100' : 'opacity-0'}`
          }`}
        >
          <Heart className={`w-3.5 h-3.5 ${photo.liked ? 'fill-rose-300' : ''}`} strokeWidth={1.5} />
        </button>

        {/* File info — bottom, hover */}
        <div
          className={`absolute bottom-2.5 left-2.5 right-12 z-20 flex items-center justify-between transition-all duration-300 ${
            isHovered ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-1'
          }`}
        >
          <span className="text-[11px] font-medium text-white/80 truncate">{photo.fileName}</span>
          <span className="text-[9px] font-mono text-white/50 bg-black/40 backdrop-blur-md border border-white/[0.06] px-2 py-0.5 rounded ml-2 flex-shrink-0">
            {photo.resolution}
          </span>
        </div>
      </div>

      {/* Minimal bottom bar — visible when NOT hovered */}
      <div className={`absolute bottom-0 left-0 right-0 pl-3 pr-12 py-2 bg-gradient-to-t from-black/70 to-transparent pointer-events-none transition-opacity duration-300 ${
        isHovered ? 'opacity-0' : 'opacity-100'
      }`}>
        <p className="text-[10px] font-mono text-white/50 truncate">{photo.fileName}</p>
      </div>
    </div>
  )
}
