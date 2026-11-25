import { useMemo, useState } from 'react'
import { Aperture, Upload, Images, Sparkles, AlertCircle, X } from 'lucide-react'
import { UploadView } from './components/UploadView'
import { GalleryView } from './components/GalleryView'
import { TuningPanel } from './components/TuningPanel'
import { analysisFields, cullPhotos } from './lib/api'
import type { Photo } from './lib/photos'
import {
  activePreset,
  looksLikeBokehSession,
  overridesOf,
  useTuning,
  valuesForPreset,
  type TuningValues,
} from './lib/tuning'

type Tab = 'upload' | 'gallery'

const BOKEH_PRESET_ID = 'portrait_bokeh'

function App() {
  const [activeTab, setActiveTab] = useState<Tab>('upload')
  const [photos, setPhotos] = useState<Photo[]>([])
  const tuning = useTuning()
  const [isReanalyzing, setIsReanalyzing] = useState(false)
  const [reanalyzeError, setReanalyzeError] = useState<string | null>(null)
  const [suggestionDismissed, setSuggestionDismissed] = useState(false)

  const handleAnalyzed = (newPhotos: Photo[]) => {
    setPhotos((prev) => [...newPhotos, ...prev])
    setActiveTab('gallery')
  }

  /** Re-run every photo in the gallery through the backend with the given (or current) overrides. */
  const reanalyze = async (overrides: TuningValues = tuning.overrides) => {
    if (isReanalyzing || photos.length === 0) return
    setIsReanalyzing(true)
    setReanalyzeError(null)
    const targets = photos
    try {
      const results = await cullPhotos(
        targets.map((p) => p.file),
        overrides
      )
      const updates = new Map<string, Pick<Photo, 'issues' | 'flags' | 'metrics'>>()
      let failed = 0
      results.forEach((result, i) => {
        if (result.status === 'success') updates.set(targets[i].id, analysisFields(result.analyses))
        else failed++
      })
      // Merge by id: photos may have been liked or deleted while the request was in flight.
      setPhotos((prev) => prev.map((p) => (updates.has(p.id) ? { ...p, ...updates.get(p.id)! } : p)))
      if (failed > 0) setReanalyzeError(`${failed} photo${failed !== 1 ? 's' : ''} could not be re-analyzed`)
    } catch (e) {
      setReanalyzeError(e instanceof Error ? e.message : 'Re-analysis failed')
    } finally {
      setIsReanalyzing(false)
    }
  }

  // Suggest the bokeh preset only while on the defaults, so it never overrides a deliberate choice.
  const bokehPreset = tuning.catalog?.presets.find((p) => p.id === BOKEH_PRESET_ID)
  const onDefaults =
    tuning.catalog !== null && activePreset(tuning.catalog, tuning.values)?.id === tuning.catalog.default_preset
  const bokehSignal = useMemo(() => looksLikeBokehSession(photos), [photos])
  const suggestion = bokehPreset && onDefaults && !suggestionDismissed ? bokehSignal : null

  const acceptSuggestion = () => {
    if (!tuning.catalog || !bokehPreset) return
    tuning.applyPreset(bokehPreset)
    reanalyze(overridesOf(tuning.catalog, valuesForPreset(tuning.catalog, bokehPreset)))
  }

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
          />

          {suggestion && (
            <div className="mb-6 flex flex-wrap items-center gap-3 px-4 py-3 rounded-xl border border-violet-400/20 bg-violet-500/[0.06] text-violet-200 text-[13px]">
              <Sparkles className="w-4 h-4 flex-shrink-0" strokeWidth={1.5} />
              <span className="flex-1 min-w-[16rem]">
                Looks like a bokeh session: {suggestion.count} of {suggestion.total} photos read as blurry but have a
                distinct sharp subject. Switch to “{bokehPreset?.label}” and re-analyze?
              </span>
              <button
                onClick={acceptSuggestion}
                disabled={isReanalyzing}
                className="px-3 py-1.5 rounded-full bg-white text-black text-[12px] font-semibold cursor-pointer disabled:opacity-50"
              >
                Switch &amp; re-analyze
              </button>
              <button
                onClick={() => setSuggestionDismissed(true)}
                aria-label="Dismiss suggestion"
                className="p-1 rounded hover:bg-white/[0.06] cursor-pointer"
              >
                <X className="w-3.5 h-3.5" strokeWidth={1.5} />
              </button>
            </div>
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
