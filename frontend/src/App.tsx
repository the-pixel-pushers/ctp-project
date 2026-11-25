import { useRef, useState } from 'react'
import { Aperture, Upload, Images, Sparkles, AlertCircle, X } from 'lucide-react'
import { UploadView } from './components/UploadView'
import { GalleryView } from './components/GalleryView'
import { TuningPanel } from './components/TuningPanel'
import { PresetSuggestionBanner, type SuggestionState } from './components/PresetSuggestionBanner'
import { analysisFields, cullPhotos, suggestPreset, type AnalysisFields } from './lib/api'
import type { Photo } from './lib/photos'
import { overridesOf, useTuning, valuesEqual, valuesForPreset, type TuningValues } from './lib/tuning'

type Tab = 'upload' | 'gallery'

/** What Undo needs after accepting a suggestion, plus the values the preset applied. */
interface UndoSnapshot {
  values: TuningValues
  fields: Map<string, AnalysisFields>
  appliedValues: TuningValues
}

const sameFlags = (a: Record<string, string>, b: Record<string, string>) =>
  Object.keys(a).length === Object.keys(b).length && Object.entries(a).every(([k, v]) => b[k] === v)

function App() {
  const [activeTab, setActiveTab] = useState<Tab>('upload')
  const [photos, setPhotos] = useState<Photo[]>([])
  const tuning = useTuning()
  const [isReanalyzing, setIsReanalyzing] = useState(false)
  const [reanalyzeError, setReanalyzeError] = useState<string | null>(null)
  const [suggestion, setSuggestion] = useState<SuggestionState | null>(null)
  const [undoSnapshot, setUndoSnapshot] = useState<UndoSnapshot | null>(null)
  // Bumped on every import so a late suggestion response for an older batch is ignored.
  const suggestionRequest = useRef(0)

  const handleAnalyzed = (newPhotos: Photo[], overridesUsed: TuningValues) => {
    setPhotos((prev) => [...newPhotos, ...prev])
    setActiveTab('gallery')
    const request = ++suggestionRequest.current
    setSuggestion(null)
    setUndoSnapshot(null)
    // The suggestion rules are calibrated on default-tuning metrics; a batch analyzed with a
    // deliberate preset or slider change is left alone.
    if (Object.keys(overridesUsed).length > 0) return
    suggestPreset(newPhotos)
      .then((s) => {
        if (s && request === suggestionRequest.current) setSuggestion({ kind: 'offer', suggestion: s })
      })
      .catch(() => {
        /* a suggestion is optional: no banner */
      })
  }

  /**
   * Re-run every photo in the gallery through the backend with the given (or current) overrides.
   * Resolves to how many photos' flags changed, or null if nothing was re-analyzed.
   */
  const reanalyze = async (
    overrides: TuningValues = tuning.overrides
  ): Promise<{ changed: number; total: number } | null> => {
    if (isReanalyzing || photos.length === 0) return null
    setIsReanalyzing(true)
    setReanalyzeError(null)
    const targets = photos
    try {
      const results = await cullPhotos(
        targets.map((p) => p.file),
        overrides
      )
      const updates = new Map<string, AnalysisFields>()
      let failed = 0
      let changed = 0
      results.forEach((result, i) => {
        if (result.status !== 'success') {
          failed++
          return
        }
        const fields = analysisFields(result.analyses)
        if (!sameFlags(targets[i].flags, fields.flags)) changed++
        updates.set(targets[i].id, fields)
      })
      // Merge by id: photos may have been liked or deleted while the request was in flight.
      setPhotos((prev) => prev.map((p) => (updates.has(p.id) ? { ...p, ...updates.get(p.id)! } : p)))
      if (failed > 0) setReanalyzeError(`${failed} photo${failed !== 1 ? 's' : ''} could not be re-analyzed`)
      return { changed, total: updates.size }
    } catch (e) {
      setReanalyzeError(e instanceof Error ? e.message : 'Re-analysis failed')
      return null
    } finally {
      setIsReanalyzing(false)
    }
  }

  const presetLabel = (id: string) => tuning.catalog?.presets.find((p) => p.id === id)?.label ?? id

  const acceptPreset = async (presetId: string) => {
    const catalog = tuning.catalog
    const preset = catalog?.presets.find((p) => p.id === presetId)
    if (!catalog || !preset || isReanalyzing) return
    const request = suggestionRequest.current
    const snapshot: UndoSnapshot = {
      values: tuning.values,
      fields: new Map(photos.map((p) => [p.id, { issues: p.issues, flags: p.flags, metrics: p.metrics }])),
      appliedValues: valuesForPreset(catalog, preset),
    }
    tuning.applyPreset(preset)
    const outcome = await reanalyze(overridesOf(catalog, snapshot.appliedValues))
    if (!outcome) {
      tuning.restoreValues(snapshot.values) // labels weren't updated, so don't leave settings changed
      return
    }
    if (request !== suggestionRequest.current) return // a new import replaced this suggestion
    setUndoSnapshot(snapshot)
    setSuggestion({ kind: 'applied', presetId, ...outcome })
  }

  const undoPreset = () => {
    if (!undoSnapshot) return
    const { values, fields } = undoSnapshot
    tuning.restoreValues(values)
    setPhotos((prev) => prev.map((p) => (fields.has(p.id) ? { ...p, ...fields.get(p.id)! } : p)))
    setUndoSnapshot(null)
    setSuggestion(null)
  }

  const dismissSuggestion = () => {
    setSuggestion(null)
    setUndoSnapshot(null)
  }

  // Undo only makes sense while the accepted preset is still what's applied.
  const canUndo = undoSnapshot !== null && valuesEqual(undoSnapshot.appliedValues, tuning.values)

  return (
    <div className="min-h-screen bg-[#0a0a0a] noise-bg flex flex-col relative overflow-hidden">
      {/* Ambient background glows */}
      <div className="pointer-events-none fixed inset-0 z-0">
        <div className="absolute -top-[30%] -left-[10%] w-[600px] h-[600px] rounded-full bg-purple-600/[0.04] blur-[120px] glow-pulse" />
        <div className="absolute -bottom-[20%] -right-[10%] w-[500px] h-[500px] rounded-full bg-blue-500/[0.03] blur-[120px] glow-pulse" style={{ animationDelay: '1.5s' }} />
      </div>

      {/* Floating Navigation */}
      <header className="fixed top-4 left-1/2 -translate-x-1/2 z-50 w-auto">
        <nav className="flex items-center gap-1 px-2 py-1.5 rounded-full border border-white/[0.06] bg-black/60 backdrop-blur-2xl shadow-2xl shadow-black/40">
          {/* Logo */}
          <div className="flex items-center gap-2 pl-3 pr-4">
            <Aperture className="w-5 h-5 text-white" strokeWidth={1.5} />
            <span className="text-sm font-semibold tracking-tight text-white">
              PhotoCull
            </span>
          </div>

          <div className="w-px h-5 bg-white/[0.08]" />

          {/* Tab Buttons */}
          <button
            onClick={() => setActiveTab('upload')}
            className={`flex items-center gap-2 px-4 py-2 rounded-full text-[13px] font-medium transition-all duration-300 cursor-pointer ${
              activeTab === 'upload'
                ? 'bg-white text-black'
                : 'text-neutral-400 hover:text-white'
            }`}
          >
            <Upload className="w-3.5 h-3.5" />
            Upload
          </button>
          <button
            onClick={() => setActiveTab('gallery')}
            className={`flex items-center gap-2 px-4 py-2 rounded-full text-[13px] font-medium transition-all duration-300 cursor-pointer ${
              activeTab === 'gallery'
                ? 'bg-white text-black'
                : 'text-neutral-400 hover:text-white'
            }`}
          >
            <Images className="w-3.5 h-3.5" />
            Gallery
          </button>

          <div className="w-px h-5 bg-white/[0.08]" />

          {/* CTA */}
          <button
            onClick={() => setActiveTab('upload')}
            className="flex items-center gap-1.5 px-4 py-2 rounded-full text-[13px] font-medium text-black bg-gradient-to-r from-violet-400 to-fuchsia-400 hover:from-violet-300 hover:to-fuchsia-300 transition-all duration-300 cursor-pointer shadow-lg shadow-violet-500/20">
            <Sparkles className="w-3.5 h-3.5" />
            Analyze
          </button>
        </nav>
      </header>

      {/* Main Content */}
      <main className="flex-1 relative z-10 pt-24 pb-12">
        <div className="max-w-[1400px] mx-auto px-6">
          <TuningPanel
            tuning={tuning}
            photoCount={photos.length}
            isReanalyzing={isReanalyzing}
            onReanalyze={() => reanalyze()}
            suggestedPresetId={suggestion?.kind === 'offer' ? suggestion.suggestion.preset_id : null}
          />

          {suggestion && (
            <PresetSuggestionBanner
              state={suggestion}
              labelFor={presetLabel}
              isReanalyzing={isReanalyzing}
              canUndo={canUndo}
              onAccept={acceptPreset}
              onUndo={undoPreset}
              onDismiss={dismissSuggestion}
            />
          )}

          {reanalyzeError && (
            <div className="mb-6 flex items-center gap-3 px-4 py-3 rounded-xl border border-red-400/20 bg-red-500/[0.06] text-red-300 text-[13px]">
              <AlertCircle className="w-4 h-4 flex-shrink-0" strokeWidth={1.5} />
              <span className="flex-1">{reanalyzeError}</span>
              <button
                onClick={() => setReanalyzeError(null)}
                aria-label="Dismiss error"
                className="p-1 rounded hover:bg-red-500/10 cursor-pointer"
              >
                <X className="w-3.5 h-3.5" strokeWidth={1.5} />
              </button>
            </div>
          )}

          {activeTab === 'upload' ? (
            <UploadView onAnalyzed={handleAnalyzed} overrides={tuning.overrides} />
          ) : (
            <GalleryView photos={photos} setPhotos={setPhotos} onGoToUpload={() => setActiveTab('upload')} />
          )}
        </div>
      </main>

      {/* Footer */}
      <footer className="relative z-10 border-t border-white/[0.04] py-6">
        <div className="max-w-[1400px] mx-auto px-6 flex items-center justify-between">
          <p className="text-[11px] font-mono text-neutral-600 tracking-wide uppercase">
            PhotoCull v0.1.0
          </p>
          <p className="text-[11px] font-mono text-neutral-700">
            Intelligent photo culling for modern photographers
          </p>
        </div>
      </footer>
    </div>
  )
}

export default App
