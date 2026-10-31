import { useState, useMemo } from 'react'
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
} from 'lucide-react'
import { MOCK_PHOTOS, ISSUE_META, type MockPhoto, type QualityIssue } from '../data/mockData'
import { PhotoCard } from './PhotoCard'

type FilterMode = 'all' | 'overexposed' | 'underexposed' | 'blurry' | 'clean' | 'issues'
type ViewMode = 'grouped' | 'flat'

interface IssueGroup {
  key: string
  label: string
  icon: React.ReactNode
  accentColor: string
  accentBg: string
  accentBorder: string
  photos: MockPhoto[]
}

export function GalleryView() {
  const [searchQuery, setSearchQuery] = useState('')
  const [filterMode, setFilterMode] = useState<FilterMode>('all')
  const [viewMode, setViewMode] = useState<ViewMode>('grouped')
  const [photos, setPhotos] = useState<MockPhoto[]>(MOCK_PHOTOS)
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set())

  const toggleLike = (id: string) => {
    setPhotos((prev) =>
      prev.map((p) => (p.id === id ? { ...p, liked: !p.liked } : p))
    )
  }

  const discardPhoto = (id: string) => {
    setPhotos((prev) => prev.filter((p) => p.id !== id))
  }

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

  // Build groups for the grouped view
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

  // Stats
  const issueCount = photos.filter((p) => p.issues.length > 0).length
  const cleanCount = photos.filter((p) => p.issues.length === 0).length

  const filterChips: { label: string; value: FilterMode; icon: React.ReactNode; count: number }[] = [
    { label: 'All', value: 'all', icon: null, count: photos.length },
    { label: 'Clean', value: 'clean', icon: <ShieldCheck className="w-3 h-3" strokeWidth={1.5} />, count: cleanCount },
    { label: 'Has Issues', value: 'issues', icon: <Eye className="w-3 h-3" strokeWidth={1.5} />, count: issueCount },
    { label: 'Over-exposed', value: 'overexposed', icon: <Sun className="w-3 h-3" strokeWidth={1.5} />, count: photos.filter((p) => p.issues.includes('overexposed')).length },
    { label: 'Under-exposed', value: 'underexposed', icon: <Moon className="w-3 h-3" strokeWidth={1.5} />, count: photos.filter((p) => p.issues.includes('underexposed')).length },
    { label: 'Blurry', value: 'blurry', icon: <CircleDot className="w-3 h-3" strokeWidth={1.5} />, count: photos.filter((p) => p.issues.includes('blurry')).length },
  ]

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <h1 className="text-4xl sm:text-5xl font-bold tracking-tight text-white leading-tight">
            Gallery
          </h1>
          <p className="text-neutral-500 text-sm mt-1">
            Photos grouped by quality analysis
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
      {filtered.length === 0 ? (
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
                <button
                  onClick={() => toggleGroup(group.key)}
                  className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl border transition-all duration-300 cursor-pointer group/header ${group.accentBg} ${group.accentBorder}`}
                >
                  {/* Collapse chevron */}
                  <div className="transition-transform duration-200">
                    {isCollapsed
                      ? <ChevronRight className={`w-4 h-4 ${group.accentColor}`} strokeWidth={1.5} />
                      : <ChevronDown className={`w-4 h-4 ${group.accentColor}`} strokeWidth={1.5} />
                    }
                  </div>

                  {/* Accent dot */}
                  <div className={`${group.accentColor}`}>
                    {group.icon}
                  </div>

                  {/* Label */}
                  <span className={`text-[13px] font-semibold tracking-wide ${group.accentColor}`}>
                    {group.label}
                  </span>

                  {/* Count */}
                  <span className="text-[11px] font-mono text-neutral-600 bg-white/[0.04] border border-white/[0.04] px-2 py-0.5 rounded-full">
                    {group.photos.length} photo{group.photos.length !== 1 && 's'}
                  </span>

                  {/* Discard All — right side (only for issue groups) */}
                  {group.key !== 'clean' && (
                    <span className="ml-auto text-[10px] font-mono text-neutral-700 group-hover/header:text-red-400/60 transition-colors uppercase tracking-wider flex items-center gap-1.5">
                      <Trash2 className="w-3 h-3" strokeWidth={1.5} />
                      Discard group
                    </span>
                  )}
                </button>

                {/* Group Photo Grid — collapsible */}
                {!isCollapsed && (
                  <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-2 pl-4 border-l-2 ml-2" style={{
                    borderColor: group.key === 'clean' ? 'rgba(52,211,153,0.15)' :
                                 group.key === 'overexposed' ? 'rgba(251,191,36,0.15)' :
                                 group.key === 'underexposed' ? 'rgba(96,165,250,0.15)' :
                                 'rgba(251,113,133,0.15)'
                  }}>
                    {group.photos.map((photo) => (
                      <PhotoCard
                        key={photo.id}
                        photo={photo}
                        onToggleLike={toggleLike}
                        onDiscard={discardPhoto}
                        compact
                      />
                    ))}
                  </div>
                )}
              </section>
            )
          })}
        </div>
      ) : (
        /* ======= FLAT GRID VIEW ======= */
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
          {filtered.map((photo) => (
            <PhotoCard
              key={photo.id}
              photo={photo}
              onToggleLike={toggleLike}
              onDiscard={discardPhoto}
            />
          ))}
        </div>
      )}

      {/* Bottom Summary Bar */}
      {filtered.length > 0 && (
        <div className="flex items-center justify-between px-4 py-3 rounded-xl border border-white/[0.04] bg-white/[0.01]">
          <p className="text-[11px] font-mono text-neutral-600">
            Showing {filtered.length} of {photos.length} photos
          </p>
          <div className="flex items-center gap-3">
            <button className="flex items-center gap-1.5 px-4 py-2 rounded-full text-[12px] font-mono text-neutral-500 border border-white/[0.05] hover:border-red-400/20 hover:text-red-400 hover:bg-red-400/[0.04] transition-all cursor-pointer">
              <Trash2 className="w-3.5 h-3.5" strokeWidth={1.5} />
              Discard all flagged
            </button>
            <button className="flex items-center gap-1.5 px-4 py-2 rounded-full text-[12px] font-mono text-black bg-white hover:scale-105 transition-all cursor-pointer font-semibold">
              <Heart className="w-3.5 h-3.5" strokeWidth={1.5} />
              Keep clean photos
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
