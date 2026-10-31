import { useState } from 'react'
import { Aperture, Upload, Images, Sparkles } from 'lucide-react'
import { UploadView } from './components/UploadView'
import { GalleryView } from './components/GalleryView'

type Tab = 'upload' | 'gallery'

function App() {
  const [activeTab, setActiveTab] = useState<Tab>('upload')

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
          <button className="flex items-center gap-1.5 px-4 py-2 rounded-full text-[13px] font-medium text-black bg-gradient-to-r from-violet-400 to-fuchsia-400 hover:from-violet-300 hover:to-fuchsia-300 transition-all duration-300 cursor-pointer shadow-lg shadow-violet-500/20">
            <Sparkles className="w-3.5 h-3.5" />
            Analyze
          </button>
        </nav>
      </header>

      {/* Main Content */}
      <main className="flex-1 relative z-10 pt-24 pb-12">
        <div className="max-w-[1400px] mx-auto px-6">
          {activeTab === 'upload' ? <UploadView /> : <GalleryView />}
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
