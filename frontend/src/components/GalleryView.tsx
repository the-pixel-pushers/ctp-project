import { useState, useMemo, useEffect, type Dispatch, type ReactNode, type SetStateAction } from 'react'
import {
  Search,
  LayoutGrid,
  Rows3,
  ChevronDown,
  ChevronRight,
  Sun,
  Moon,
  CircleDot,
  ShieldCheck,
  Eye,
  Trash2,
  Heart,
  HeartOff,
  Upload,
  Download,
  CheckSquare,
  X,
  Loader2,
} from 'lucide-react'
import { ISSUE_META, type Photo } from '../lib/photos'
import { downloadPhotos } from '../lib/download'
import { PhotoCard } from './PhotoCard'

type FilterMode = 'all' | 'liked' | 'overexposed' | 'underexposed' | 'blurry' | 'clean' | 'issues'
type ViewMode = 'grouped' | 'flat'

interface IssueGroup {
  key: string
  label: string
  icon: ReactNode
  accentColor: string
  accentBg: string
  accentBorder: string
  photos: Photo[]
}

interface PendingDelete {
  ids: string[]
  label: string
}

interface GalleryViewProps {
  photos: Photo[]
  setPhotos: Dispatch<SetStateAction<Photo[]>>
  onGoToUpload: () => void
}

const plural = (n: number, word = 'photo') => `${n} ${word}${n !== 1 ? 's' : ''}`

export function GalleryView({ photos, setPhotos, onGoToUpload }: GalleryViewProps) {
  const [searchQuery, setSearchQuery] = useState('')
  const [filterMode, setFilterMode] = useState<FilterMode>('all')
  const [viewMode, setViewMode] = useState<ViewMode>('grouped')
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set())
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [lastSelectedId, setLastSelectedId] = useState<string | null>(null)
  const [pendingDelete, setPendingDelete] = useState<PendingDelete | null>(null)
  const [isDownloading, setIsDownloading] = useState(false)

  // Only count selections for photos that still exist.
  const selectedPhotos = useMemo(() => photos.filter((p) => selectedIds.has(p.id)), [photos, selectedIds])
  const selectionMode = selectedPhotos.length > 0
  const likedPhotos = photos.filter((p) => p.liked)

  /* ---------------- Likes ---------------- */

  const setLiked = (ids: Set<string>, liked: boolean) => {
    setPhotos((prev) => prev.map((p) => (ids.has(p.id) ? { ...p, liked } : p)))
  }

  const toggleLike = (id: string) => {
    setPhotos((prev) => prev.map((p) => (p.id === id ? { ...p, liked: !p.liked } : p)))
  }

  /* ---------------- Delete ---------------- */

  const deletePhotos = (ids: string[]) => {
    const doomed = new Set(ids)
    setPhotos((prev) => {
      prev.filter((p) => doomed.has(p.id)).forEach((p) => URL.revokeObjectURL(p.url))
      return prev.filter((p) => !doomed.has(p.id))
    })
    setSelectedIds((prev) => new Set([...prev].filter((id) => !doomed.has(id))))
  }

  const requestDelete = (ids: string[], label: string) => {
    if (ids.length === 0) return
    setPendingDelete({ ids, label })
  }

  /* ---------------- Download ---------------- */

  const download = async (toDownload: Photo[]) => {
    if (toDownload.length === 0 || isDownloading) return
    setIsDownloading(true)
    try {
      await downloadPhotos(toDownload)
    } finally {
      setIsDownloading(false)
    }
  }

  /* ---------------- Grouping / filtering ---------------- */

  const toggleGroup = (key: string) => {
    setCollapsedGroups((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  const filtered = useMemo(() => {
    let result = [...photos]

    if (searchQuery) {
      const q = searchQuery.toLowerCase()
      result = result.filter((p) => p.fileName.toLowerCase().includes(q))
    }

    switch (filterMode) {
      case 'liked':
        result = result.filter((p) => p.liked)
        break
      case 'overexposed':
        result = result.filter((p) => p.issues.includes('overexposed'))
        break
      case 'underexposed':
        result = result.filter((p) => p.issues.includes('underexposed'))
        break
      case 'blurry':
        result = result.filter((p) => p.issues.includes('blurry'))
        break
      case 'clean':
        result = result.filter((p) => p.issues.length === 0)
        break
      case 'issues':
        result = result.filter((p) => p.issues.length > 0)
        break
    }

    return result
  }, [photos, searchQuery, filterMode])

  const groups: IssueGroup[] = useMemo(() => {
    const overexposed = filtered.filter((p) => p.issues.includes('overexposed'))
    const underexposed = filtered.filter((p) => p.issues.includes('underexposed'))
    const blurry = filtered.filter((p) => p.issues.includes('blurry'))
    const clean = filtered.filter((p) => p.issues.length === 0)

    const result: IssueGroup[] = []

    if (clean.length > 0) {
      result.push({
        key: 'clean',
        label: 'Sharp & Well-Exposed',
        icon: <ShieldCheck className="w-4 h-4" strokeWidth={1.5} />,
        accentColor: 'text-emerald-400',
        accentBg: 'bg-emerald-400/[0.06]',
        accentBorder: 'border-emerald-400/15',
        photos: clean,
      })
    }

    if (overexposed.length > 0) {
      result.push({
        key: 'overexposed',
        label: ISSUE_META.overexposed.label,
        icon: <Sun className="w-4 h-4" strokeWidth={1.5} />,
        accentColor: ISSUE_META.overexposed.color,
        accentBg: ISSUE_META.overexposed.bgColor,
        accentBorder: ISSUE_META.overexposed.borderColor,
        photos: overexposed,
      })
    }

    if (underexposed.length > 0) {
      result.push({
        key: 'underexposed',
        label: ISSUE_META.underexposed.label,
        icon: <Moon className="w-4 h-4" strokeWidth={1.5} />,
        accentColor: ISSUE_META.underexposed.color,
        accentBg: ISSUE_META.underexposed.bgColor,
        accentBorder: ISSUE_META.underexposed.borderColor,
        photos: underexposed,
      })
    }

    if (blurry.length > 0) {
      result.push({
        key: 'blurry',
        label: ISSUE_META.blurry.label,
        icon: <CircleDot className="w-4 h-4" strokeWidth={1.5} />,
        accentColor: ISSUE_META.blurry.color,
        accentBg: ISSUE_META.blurry.bgColor,
        accentBorder: ISSUE_META.blurry.borderColor,
        photos: blurry,
      })
    }

    return result
  }, [filtered])

  /* ---------------- Selection ---------------- */

  const toggleSelect = (id: string, shiftKey: boolean) => {
    // Shift-click selects the range between the last clicked photo and this one.
    if (shiftKey && lastSelectedId) {
      const order = filtered.map((p) => p.id)
      const a = order.indexOf(lastSelectedId)
      const b = order.indexOf(id)
      if (a !== -1 && b !== -1) {
        const [start, end] = a < b ? [a, b] : [b, a]
        setSelectedIds((prev) => new Set([...prev, ...order.slice(start, end + 1)]))
        setLastSelectedId(id)
        return
      }
    }
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
    setLastSelectedId(id)
  }

  const selectMany = (ids: string[]) => setSelectedIds((prev) => new Set([...prev, ...ids]))
  const clearSelection = () => setSelectedIds(new Set())

  // Esc cancels a pending delete, otherwise clears the selection.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return
      if (pendingDelete) setPendingDelete(null)
      else setSelectedIds(new Set())
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [pendingDelete])

  const allSelectedLiked = selectionMode && selectedPhotos.every((p) => p.liked)

  /* ---------------- Stats ---------------- */

  const issueCount = photos.filter((p) => p.issues.length > 0).length
  const cleanPhotos = photos.filter((p) => p.issues.length === 0)
  const cleanCount = cleanPhotos.length

  const filterChips: { label: string; value: FilterMode; icon: ReactNode; count: number }[] = [
    { label: 'All', value: 'all', icon: null, count: photos.length },
    { label: 'Liked', value: 'liked', icon: <Heart className="w-3 h-3" strokeWidth={1.5} />, count: likedPhotos.length },
    { label: 'Clean', value: 'clean', icon: <ShieldCheck className="w-3 h-3" strokeWidth={1.5} />, count: cleanCount },
    { label: 'Has Issues', value: 'issues', icon: <Eye className="w-3 h-3" strokeWidth={1.5} />, count: issueCount },
    { label: 'Over-exposed', value: 'overexposed', icon: <Sun className="w-3 h-3" strokeWidth={1.5} />, count: photos.filter((p) => p.issues.includes('overexposed')).length },
    { label: 'Under-exposed', value: 'underexposed', icon: <Moon className="w-3 h-3" strokeWidth={1.5} />, count: photos.filter((p) => p.issues.includes('underexposed')).length },
    { label: 'Blurry', value: 'blurry', icon: <CircleDot className="w-3 h-3" strokeWidth={1.5} />, count: photos.filter((p) => p.issues.includes('blurry')).length },
  ]

  const renderCard = (photo: Photo, compact = false) => (
    <PhotoCard
      key={photo.id}
      photo={photo}
      selected={selectedIds.has(photo.id)}
      selectionMode={selectionMode}
      onToggleSelect={toggleSelect}
      onToggleLike={toggleLike}
      onDiscard={(id) => requestDelete([id], photo.fileName)}
      onDownload={() => download([photo])}
      compact={compact}
    />
  )

  return (
    <div className={`space-y-8 ${selectionMode ? 'pb-24' : ''}`}>
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <h1 className="text-4xl sm:text-5xl font-bold tracking-tight text-white leading-tight">
            Gallery
          </h1>
          <p className="text-neutral-500 text-sm mt-1">
            Click photos to select · Shift-click for a range · Double-click to like
          </p>
        </div>

        {/* Summary stats */}
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2.5">
            <div className="w-2 h-2 rounded-full bg-emerald-400" />
            <div>
              <p className="text-lg font-bold font-mono text-white">{cleanCount}</p>
              <p className="text-[9px] font-mono text-neutral-600 uppercase tracking-wider">Clean</p>
            </div>
          </div>
          <div className="w-px h-8 bg-white/[0.06]" />
          <div className="flex items-center gap-2.5">
            <div className="w-2 h-2 rounded-full bg-amber-400" />
            <div>
              <p className="text-lg font-bold font-mono text-white">{issueCount}</p>
              <p className="text-[9px] font-mono text-neutral-600 uppercase tracking-wider">Issues</p>
            </div>
          </div>
          <div className="w-px h-8 bg-white/[0.06]" />
          <div className="flex items-center gap-2.5">
            <Heart className="w-3 h-3 text-rose-300 fill-rose-300" strokeWidth={1.5} />
            <div>
              <p className="text-lg font-bold font-mono text-white">{likedPhotos.length}</p>
              <p className="text-[9px] font-mono text-neutral-600 uppercase tracking-wider">Liked</p>
            </div>
          </div>
          <div className="w-px h-8 bg-white/[0.06]" />
          <div>
            <p className="text-lg font-bold font-mono text-white">{photos.length}</p>
            <p className="text-[9px] font-mono text-neutral-600 uppercase tracking-wider">Total</p>
          </div>
        </div>
      </div>

      {/* Toolbar */}
      <div className="rounded-2xl border border-white/[0.05] bg-white/[0.015] p-4 space-y-4">
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
          {/* Search */}
          <div className="relative flex-1">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-600" strokeWidth={1.5} />
            <input
              type="text"
              placeholder="Search photos..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-11 pr-4 py-2.5 rounded-xl bg-white/[0.03] border border-white/[0.05] text-sm text-neutral-200 placeholder-neutral-600 focus:outline-none focus:border-violet-500/30 focus:bg-white/[0.04] transition-all font-mono"
            />
          </div>

          {/* Select all visible */}
          <button
            onClick={() => selectMany(filtered.map((p) => p.id))}
            disabled={filtered.length === 0}
            className="flex items-center gap-2 px-3 py-2.5 rounded-xl border border-white/[0.05] bg-white/[0.03] text-[12px] font-medium text-neutral-400 hover:text-white transition-all cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <CheckSquare className="w-4 h-4" strokeWidth={1.5} />
            Select all
          </button>

          {/* View Toggle */}
          <div className="flex items-center border border-white/[0.05] rounded-xl bg-white/[0.03] p-1">
            <button
              onClick={() => setViewMode('grouped')}
              className={`flex items-center gap-2 px-3 py-2 rounded-lg text-[12px] font-medium transition-all duration-200 cursor-pointer ${
                viewMode === 'grouped'
                  ? 'bg-white text-black'
                  : 'text-neutral-600 hover:text-neutral-300'
              }`}
            >
              <Rows3 className="w-4 h-4" strokeWidth={1.5} />
              Grouped
            </button>
            <button
              onClick={() => setViewMode('flat')}
              className={`flex items-center gap-2 px-3 py-2 rounded-lg text-[12px] font-medium transition-all duration-200 cursor-pointer ${
                viewMode === 'flat'
                  ? 'bg-white text-black'
                  : 'text-neutral-600 hover:text-neutral-300'
              }`}
            >
              <LayoutGrid className="w-4 h-4" strokeWidth={1.5} />
              Grid
            </button>
          </div>
        </div>

        {/* Filter Chips */}
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-[10px] font-mono text-neutral-600 uppercase tracking-wider mr-1">
            Filter
          </span>
          {filterChips.map((chip) => (
            <button
              key={chip.value}
              onClick={() => setFilterMode(chip.value)}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[11px] font-mono tracking-wide transition-all duration-200 cursor-pointer border ${
                filterMode === chip.value
                  ? 'bg-white text-black border-white/20 font-semibold'
                  : 'bg-transparent text-neutral-500 border-white/[0.05] hover:text-neutral-200 hover:border-white/[0.1]'
              }`}
            >
              {chip.icon}
              {chip.label}
              <span className={`text-[9px] ${filterMode === chip.value ? 'text-black/50' : 'text-neutral-700'}`}>
                {chip.count}
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      {photos.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24 text-neutral-600">
          <Upload className="w-12 h-12 mb-4 text-neutral-800" strokeWidth={1} />
          <p className="text-sm font-medium text-neutral-500">No photos yet</p>
          <p className="text-[11px] font-mono text-neutral-700 mt-1 mb-6">Upload some photos to analyze them</p>
          <button
            onClick={onGoToUpload}
            className="px-5 py-2 rounded-full bg-white text-black text-[13px] font-semibold hover:scale-105 transition-all cursor-pointer"
          >
            Go to Upload
          </button>
        </div>
      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24 text-neutral-600">
          <Eye className="w-12 h-12 mb-4 text-neutral-800" strokeWidth={1} />
          <p className="text-sm font-medium text-neutral-500">No photos found</p>
          <p className="text-[11px] font-mono text-neutral-700 mt-1">Adjust your search or filters</p>
        </div>
      ) : viewMode === 'grouped' ? (
        /* ======= GROUPED VIEW: Swimlanes ======= */
        <div className="space-y-6">
          {groups.map((group) => {
            const isCollapsed = collapsedGroups.has(group.key)

            return (
              <section key={group.key} className="space-y-3">
                {/* Group Header */}
                <div className={`flex items-center gap-2 pr-2 rounded-xl border transition-all duration-300 ${group.accentBg} ${group.accentBorder}`}>
                  <button
                    onClick={() => toggleGroup(group.key)}
                    className="flex-1 flex items-center gap-3 px-4 py-3 cursor-pointer text-left"
                  >
                    {isCollapsed
                      ? <ChevronRight className={`w-4 h-4 ${group.accentColor}`} strokeWidth={1.5} />
                      : <ChevronDown className={`w-4 h-4 ${group.accentColor}`} strokeWidth={1.5} />
                    }
                    <div className={group.accentColor}>{group.icon}</div>
                    <span className={`text-[13px] font-semibold tracking-wide ${group.accentColor}`}>
                      {group.label}
                    </span>
                    <span className="text-[11px] font-mono text-neutral-600 bg-white/[0.04] border border-white/[0.04] px-2 py-0.5 rounded-full">
                      {plural(group.photos.length)}
                    </span>
                  </button>

                  <button
                    onClick={() => selectMany(group.photos.map((p) => p.id))}
                    className="text-[10px] font-mono text-neutral-600 hover:text-white transition-colors uppercase tracking-wider flex items-center gap-1.5 px-2 py-1.5 rounded-lg cursor-pointer"
                  >
                    <CheckSquare className="w-3 h-3" strokeWidth={1.5} />
                    Select group
                  </button>
                  {group.key !== 'clean' && (
                    <button
                      onClick={() => requestDelete(group.photos.map((p) => p.id), `the ${group.label.toLowerCase()} group`)}
                      className="text-[10px] font-mono text-neutral-600 hover:text-red-400 transition-colors uppercase tracking-wider flex items-center gap-1.5 px-2 py-1.5 rounded-lg cursor-pointer"
                    >
                      <Trash2 className="w-3 h-3" strokeWidth={1.5} />
                      Discard group
                    </button>
                  )}
                </div>

                {/* Group Photo Grid — collapsible */}
                {!isCollapsed && (
                  <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-2 pl-4 border-l-2 ml-2" style={{
                    borderColor: group.key === 'clean' ? 'rgba(52,211,153,0.15)' :
                                 group.key === 'overexposed' ? 'rgba(251,191,36,0.15)' :
                                 group.key === 'underexposed' ? 'rgba(96,165,250,0.15)' :
                                 'rgba(251,113,133,0.15)'
                  }}>
                    {group.photos.map((photo) => renderCard(photo, true))}
                  </div>
                )}
              </section>
            )
          })}
        </div>
      ) : (
        /* ======= FLAT GRID VIEW ======= */
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
          {filtered.map((photo) => renderCard(photo))}
        </div>
      )}

      {/* Bottom Summary Bar */}
      {filtered.length > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 rounded-xl border border-white/[0.04] bg-white/[0.01]">
          <p className="text-[11px] font-mono text-neutral-600">
            Showing {filtered.length} of {photos.length} photos
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <button
              onClick={() => requestDelete(photos.filter((p) => p.issues.length > 0).map((p) => p.id), 'all flagged photos')}
              disabled={issueCount === 0}
              className="flex items-center gap-1.5 px-4 py-2 rounded-full text-[12px] font-mono text-neutral-500 border border-white/[0.05] hover:border-red-400/20 hover:text-red-400 hover:bg-red-400/[0.04] transition-all cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <Trash2 className="w-3.5 h-3.5" strokeWidth={1.5} />
              Discard all flagged
            </button>
            <button
              onClick={() => download(likedPhotos)}
              disabled={likedPhotos.length === 0 || isDownloading}
              className="flex items-center gap-1.5 px-4 py-2 rounded-full text-[12px] font-mono text-neutral-400 border border-white/[0.05] hover:border-white/[0.15] hover:text-white transition-all cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <Download className="w-3.5 h-3.5" strokeWidth={1.5} />
              Download liked ({likedPhotos.length})
            </button>
            <button
              onClick={() => setLiked(new Set(cleanPhotos.map((p) => p.id)), true)}
              disabled={cleanCount === 0}
              className="flex items-center gap-1.5 px-4 py-2 rounded-full text-[12px] font-mono text-black bg-white hover:scale-105 transition-all cursor-pointer font-semibold disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:scale-100"
            >
              <Heart className="w-3.5 h-3.5" strokeWidth={1.5} />
              Like all clean photos
            </button>
          </div>
        </div>
      )}

      {/* Floating selection action bar */}
      {selectionMode && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 w-[calc(100%-2rem)] max-w-max">
          <div className="flex flex-wrap items-center justify-center gap-1 px-2 py-1.5 rounded-full border border-white/[0.08] bg-black/80 backdrop-blur-2xl shadow-2xl shadow-black/60">
            <button
              onClick={clearSelection}
              title="Clear selection (Esc)"
              className="p-2 rounded-full text-neutral-400 hover:text-white hover:bg-white/[0.06] transition-all cursor-pointer"
            >
              <X className="w-4 h-4" strokeWidth={1.5} />
            </button>
            <span className="px-2 text-[13px] font-medium text-white whitespace-nowrap">
              {selectedPhotos.length} selected
            </span>

            <div className="w-px h-5 bg-white/[0.08] mx-1" />

            <button
              onClick={() => setLiked(new Set(selectedPhotos.map((p) => p.id)), !allSelectedLiked)}
              className="flex items-center gap-2 px-3 py-2 rounded-full text-[13px] font-medium text-neutral-300 hover:text-rose-300 hover:bg-rose-500/10 transition-all cursor-pointer"
            >
              {allSelectedLiked
                ? <><HeartOff className="w-3.5 h-3.5" strokeWidth={1.5} />Unlike</>
                : <><Heart className="w-3.5 h-3.5" strokeWidth={1.5} />Like</>
              }
            </button>
            <button
              onClick={() => download(selectedPhotos)}
              disabled={isDownloading}
              className="flex items-center gap-2 px-3 py-2 rounded-full text-[13px] font-medium text-neutral-300 hover:text-white hover:bg-white/[0.06] transition-all cursor-pointer disabled:opacity-50"
            >
              {isDownloading
                ? <Loader2 className="w-3.5 h-3.5 animate-spin" strokeWidth={1.5} />
                : <Download className="w-3.5 h-3.5" strokeWidth={1.5} />
              }
              {selectedPhotos.length > 1 ? 'Download .zip' : 'Download'}
            </button>
            <button
              onClick={() => requestDelete(selectedPhotos.map((p) => p.id), plural(selectedPhotos.length))}
              className="flex items-center gap-2 px-3 py-2 rounded-full text-[13px] font-medium text-red-300 hover:text-red-200 hover:bg-red-500/15 transition-all cursor-pointer"
            >
              <Trash2 className="w-3.5 h-3.5" strokeWidth={1.5} />
              Delete
            </button>
          </div>
        </div>
      )}

      {/* Delete confirmation */}
      {pendingDelete && (
        <div
          className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 backdrop-blur-sm px-4"
          onClick={() => setPendingDelete(null)}
        >
          <div
            className="w-full max-w-sm rounded-2xl border border-white/[0.08] bg-[#111] p-6 space-y-5 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="space-y-1.5">
              <h2 className="text-base font-semibold text-white">
                Delete {plural(pendingDelete.ids.length)}?
              </h2>
              <p className="text-[13px] text-neutral-500 leading-relaxed">
                This removes {pendingDelete.label} from the gallery. The original files on your computer are not touched.
              </p>
            </div>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setPendingDelete(null)}
                className="px-4 py-2 rounded-full text-[13px] font-medium text-neutral-300 hover:bg-white/[0.06] cursor-pointer"
              >
                Cancel
              </button>
              <button
                autoFocus
                onClick={() => { deletePhotos(pendingDelete.ids); setPendingDelete(null) }}
                className="px-4 py-2 rounded-full text-[13px] font-semibold text-white bg-red-500 hover:bg-red-400 cursor-pointer"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
