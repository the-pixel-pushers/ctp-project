import { useState } from 'react'
import { Heart, Trash2 } from 'lucide-react'
import type { MockPhoto } from '../data/mockData'
import { ISSUE_META } from '../data/mockData'

interface PhotoCardProps {
  photo: MockPhoto
  onToggleLike: (id: string) => void
  onDiscard: (id: string) => void
  compact?: boolean
}

export function PhotoCard({ photo, onToggleLike, onDiscard, compact = false }: PhotoCardProps) {
  const [isHovered, setIsHovered] = useState(false)
  const hasIssues = photo.issues.length > 0

  return (
    <div
      className={`group relative overflow-hidden transition-all duration-500 cursor-pointer rounded-xl ${
        hasIssues ? 'ring-1 ring-white/[0.04]' : ''
      }`}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* Image */}
      <div className={`relative overflow-hidden ${compact ? 'aspect-square' : 'aspect-[3/2]'}`}>
        <img
          src={photo.url}
          alt={photo.fileName}
          className={`w-full h-full object-cover transition-all duration-700 ease-out ${
            isHovered ? 'scale-[1.08]' : 'scale-100'
          }`}
        />

        {/* Vignette */}
        <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-black/0 to-black/20" />

        {/* Hover overlay */}
        <div
          className={`absolute inset-0 bg-black/30 backdrop-blur-[1px] transition-opacity duration-300 ${
            isHovered ? 'opacity-100' : 'opacity-0'
          }`}
        />

        {/* Issue pills — top left, always visible */}
        {hasIssues && (
          <div className="absolute top-2.5 left-2.5 z-20 flex flex-wrap gap-1">
            {photo.issues.map((issue) => {
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
            })}
          </div>
        )}

        {/* Clean badge for good photos */}
        {!hasIssues && (
          <div className="absolute top-2.5 left-2.5 z-20">
            <span className="inline-flex items-center gap-1 text-[9px] font-mono font-semibold uppercase tracking-[0.12em] px-2 py-0.5 rounded-full backdrop-blur-md border bg-emerald-400/[0.08] text-emerald-300 border-emerald-400/20">
              ✓ Sharp
            </span>
          </div>
        )}

        {/* Hover action buttons — top right */}
        <div
          className={`absolute top-2.5 right-2.5 z-20 flex items-center gap-1.5 transition-all duration-300 ${
            isHovered ? 'opacity-100 translate-y-0' : 'opacity-0 -translate-y-1'
          }`}
        >
          <button
            onClick={(e) => { e.stopPropagation(); onToggleLike(photo.id) }}
            className={`p-2 rounded-full backdrop-blur-md transition-all duration-200 cursor-pointer border ${
              photo.liked
                ? 'bg-rose-500/20 text-rose-300 border-rose-400/20'
                : 'bg-black/30 text-white/70 border-white/[0.08] hover:bg-black/50 hover:text-white'
            }`}
          >
            <Heart className={`w-3.5 h-3.5 ${photo.liked ? 'fill-rose-300' : ''}`} strokeWidth={1.5} />
          </button>
          <button
            onClick={(e) => { e.stopPropagation(); onDiscard(photo.id) }}
            className="p-2 rounded-full backdrop-blur-md transition-all duration-200 cursor-pointer border bg-black/30 text-white/70 border-white/[0.08] hover:bg-red-500/20 hover:text-red-300 hover:border-red-400/20"
          >
            <Trash2 className="w-3.5 h-3.5" strokeWidth={1.5} />
          </button>
        </div>

        {/* File info — bottom, hover */}
        <div
          className={`absolute bottom-2.5 left-2.5 right-2.5 z-20 flex items-center justify-between transition-all duration-300 ${
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
      <div className={`absolute bottom-0 left-0 right-0 px-3 py-2 bg-gradient-to-t from-black/70 to-transparent pointer-events-none transition-opacity duration-300 ${
        isHovered ? 'opacity-0' : 'opacity-100'
      }`}>
        <p className="text-[10px] font-mono text-white/50 truncate">{photo.fileName}</p>
      </div>
    </div>
  )
}
