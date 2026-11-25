import { Loader2, Sparkles, Undo2, X } from 'lucide-react'
import type { PresetSuggestion } from '../lib/api'

export type SuggestionState =
  | { kind: 'offer'; suggestion: PresetSuggestion }
  | { kind: 'applied'; presetId: string; changed: number; total: number }

interface PresetSuggestionBannerProps {
  state: SuggestionState
  labelFor: (presetId: string) => string
  isReanalyzing: boolean
  /** Undo is only offered while the applied preset is still the active tuning. */
  canUndo: boolean
  onAccept: (presetId: string) => void
  onUndo: () => void
  onDismiss: () => void
}

const pct = (share: number) => `${Math.round(share * 100)}%`

export function PresetSuggestionBanner({
  state,
  labelFor,
  isReanalyzing,
  canUndo,
  onAccept,
  onUndo,
  onDismiss,
}: PresetSuggestionBannerProps) {
  return (
    <div className="mb-6 flex flex-wrap items-center gap-3 px-4 py-3 rounded-xl border border-violet-400/20 bg-violet-500/[0.06] text-violet-200 text-[13px]">
      <Sparkles className="w-4 h-4 flex-shrink-0" strokeWidth={1.5} />

      {state.kind === 'offer' ? (
        <>
          <div className="flex-1 min-w-[16rem] space-y-1">
            <p>
              Looks like a <strong className="font-semibold text-white">{labelFor(state.suggestion.preset_id)}</strong>{' '}
              session ({pct(state.suggestion.confidence)}).
            </p>
            {state.suggestion.reasons.map((reason) => (
              <p key={reason} className="text-[12px] text-violet-300/80">
                {reason}.
              </p>
            ))}
            {state.suggestion.alternatives.length > 0 && (
              <div className="flex flex-wrap items-center gap-1.5 pt-1 text-[11px] text-violet-300/70">
                Also possible:
                {state.suggestion.alternatives.map((alt) => (
                  <button
                    key={alt.preset_id}
                    onClick={() => onAccept(alt.preset_id)}
                    disabled={isReanalyzing}
                    title={`Switch to ${labelFor(alt.preset_id)} and re-analyze`}
                    className="px-2 py-0.5 rounded-full border border-violet-300/20 hover:border-violet-300/50 hover:text-white cursor-pointer disabled:opacity-50"
                  >
                    {labelFor(alt.preset_id)} ({pct(alt.confidence)})
                  </button>
                ))}
              </div>
            )}
          </div>
          <button
            onClick={() => onAccept(state.suggestion.preset_id)}
            disabled={isReanalyzing}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white text-black text-[12px] font-semibold cursor-pointer disabled:opacity-50"
          >
            {isReanalyzing && <Loader2 className="w-3 h-3 animate-spin" />}
            Switch &amp; re-analyze
          </button>
        </>
      ) : (
        <>
          <p className="flex-1 min-w-[16rem]">
            Switched to <strong className="font-semibold text-white">{labelFor(state.presetId)}</strong>:{' '}
            {state.changed} of {state.total} photo{state.total !== 1 && 's'} changed label.
          </p>
          {canUndo && (
            <button
              onClick={onUndo}
              disabled={isReanalyzing}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-violet-300/30 text-[12px] font-semibold hover:border-violet-300/60 hover:text-white cursor-pointer disabled:opacity-50"
            >
              <Undo2 className="w-3 h-3" strokeWidth={1.5} />
              Undo
            </button>
          )}
        </>
      )}

      <button onClick={onDismiss} aria-label="Dismiss suggestion" className="p-1 rounded hover:bg-white/[0.06] cursor-pointer">
        <X className="w-3.5 h-3.5" strokeWidth={1.5} />
      </button>
    </div>
  )
}
