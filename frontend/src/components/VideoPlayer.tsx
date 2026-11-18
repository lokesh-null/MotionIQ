import React, { useEffect, useMemo, useRef, useState } from 'react';
import { ChevronLeft, ChevronRight, Pause, Play, RotateCcw } from 'lucide-react';
import type { AnalysisResults } from '../types/biomechanics';
import { getAnnotatedVideoUrl } from '../services/api';

interface VideoPlayerProps {
  results: AnalysisResults;
}

export const VideoPlayer: React.FC<VideoPlayerProps> = ({ results }) => {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(results.video_metadata.duration_sec || 0);
  const [playbackRate, setPlaybackRate] = useState(1.0);
  const [loadError, setLoadError] = useState(false);

  const videoUrl = getAnnotatedVideoUrl(results.analysis_id);
  const timestamps = results.biomechanics.timestamps_sec || [];
  const phases = results.movement_analysis.frame_phases || [];
  const reps = results.movement_analysis.repetitions || [];
  const fps = results.processing_details.effective_fps || 30;

  // Locate closest sampled frame index to current video playback time
  const activeFrameIdx = useMemo(() => {
    if (timestamps.length === 0) return 0;
    let bestIdx = 0;
    let bestDiff = Math.abs(timestamps[0] - currentTime);
    for (let i = 1; i < timestamps.length; i++) {
      const diff = Math.abs(timestamps[i] - currentTime);
      if (diff < bestDiff) {
        bestDiff = diff;
        bestIdx = i;
      }
    }
    return bestIdx;
  }, [timestamps, currentTime]);

  const activePhase = phases[activeFrameIdx] || 'UNKNOWN';
  const primarySignalVal = results.movement_analysis.primary_signal_deg?.[activeFrameIdx];

  useEffect(() => {
    if (videoRef.current) {
      videoRef.current.playbackRate = playbackRate;
    }
  }, [playbackRate]);

  const togglePlay = () => {
    const v = videoRef.current;
    if (!v) return;
    if (v.paused) {
      v.play().catch(() => undefined);
    } else {
      v.pause();
    }
  };

  const seekTo = (t: number) => {
    const v = videoRef.current;
    if (!v) return;
    const clamped = Math.max(0, Math.min(duration || 999, t));
    v.currentTime = clamped;
    setCurrentTime(clamped);
  };

  const stepFrame = (delta: number) => {
    const v = videoRef.current;
    if (!v) return;
    v.pause();
    seekTo(v.currentTime + delta / fps);
  };

  return (
    <div className="bg-[#161F2B] border border-white/10 rounded-xl p-4 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-[#F4F7FA]">Annotated Pose & Kinematics Video</h3>
          <p className="text-xs text-[#98A5B5]">
            33-landmark skeleton overlay, joint-angle telemetry, movement phase, and timestamps
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs font-mono">
          <span className="px-2.5 py-1 rounded bg-[#0B0F14] border border-white/10 text-[#36D6A0]">
            PHASE: {activePhase}
          </span>
          {primarySignalVal !== null && primarySignalVal !== undefined && (
            <span className="px-2.5 py-1 rounded bg-[#0B0F14] border border-white/10 text-[#F4F7FA]">
              {primarySignalVal.toFixed(1)}°
            </span>
          )}
        </div>
      </div>

      {/* Video Surface */}
      <div className="bg-[#0B0F14] rounded-lg overflow-hidden border border-white/8 relative">
        {loadError ? (
          <div className="p-8 text-center text-xs text-[#F16D73]">
            Unable to stream annotated video from backend. Verify the backend server is running.
          </div>
        ) : (
          <video
            ref={videoRef}
            src={videoUrl}
            playsInline
            onPlay={() => setIsPlaying(true)}
            onPause={() => setIsPlaying(false)}
            onEnded={() => setIsPlaying(false)}
            onLoadedMetadata={(e) => {
              const d = e.currentTarget.duration;
              if (Number.isFinite(d) && d > 0) setDuration(d);
            }}
            onTimeUpdate={(e) => setCurrentTime(e.currentTarget.currentTime)}
            onError={() => setLoadError(true)}
            className="w-full max-h-[420px] object-contain mx-auto"
          />
        )}
      </div>

      {/* Timeline Scrubber */}
      <div className="space-y-2">
        <input
          type="range"
          min={0}
          max={duration || 1}
          step={0.01}
          value={Math.min(currentTime, duration || 1)}
          onChange={(e) => seekTo(parseFloat(e.target.value))}
          className="w-full accent-[#36D6A0] cursor-pointer"
          aria-label="Video timeline scrubber"
        />

        <div className="flex flex-wrap items-center justify-between gap-3">
          {/* Playback controls */}
          <div className="flex items-center gap-1.5">
            <button
              type="button"
              onClick={togglePlay}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#36D6A0] text-[#0B0F14] text-xs font-semibold hover:bg-[#2ec290] transition-colors"
            >
              {isPlaying ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
              <span>{isPlaying ? 'Pause' : 'Play'}</span>
            </button>
            <button
              type="button"
              onClick={() => stepFrame(-1)}
              title="Previous frame"
              className="p-1.5 rounded-lg bg-[#111821] border border-white/10 text-[#F4F7FA] hover:border-white/25"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button
              type="button"
              onClick={() => stepFrame(1)}
              title="Next frame"
              className="p-1.5 rounded-lg bg-[#111821] border border-white/10 text-[#F4F7FA] hover:border-white/25"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
            <button
              type="button"
              onClick={() => seekTo(0)}
              title="Restart"
              className="p-1.5 rounded-lg bg-[#111821] border border-white/10 text-[#98A5B5] hover:text-[#F4F7FA]"
            >
              <RotateCcw className="w-3.5 h-3.5" />
            </button>
            <span className="ml-2 text-xs font-mono text-[#98A5B5]">
              {currentTime.toFixed(2)}s / {duration.toFixed(2)}s
            </span>
          </div>

          {/* Playback Speed */}
          <div className="flex items-center gap-1 text-xs">
            <span className="text-[#98A5B5] mr-1">Speed:</span>
            {[0.25, 0.5, 0.75, 1.0].map((rate) => (
              <button
                key={rate}
                type="button"
                onClick={() => setPlaybackRate(rate)}
                className={`px-2 py-1 rounded font-mono transition-colors ${
                  playbackRate === rate
                    ? 'bg-[#36D6A0]/15 text-[#36D6A0] border border-[#36D6A0]/40'
                    : 'bg-[#111821] text-[#98A5B5] border border-white/6 hover:text-[#F4F7FA]'
                }`}
              >
                {rate}x
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Repetition Timeline Jump Pills */}
      {reps.length > 0 && (
        <div className="pt-2 border-t border-white/6 flex flex-wrap items-center gap-2">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-[#98A5B5]">
            Jump to Rep:
          </span>
          {reps.map((r) => {
            const targetTime = r.bottom_time_sec ?? r.peak_time_sec ?? r.release_time_sec ?? r.start_time_sec;
            return (
              <button
                key={r.rep_number}
                type="button"
                onClick={() => seekTo(targetTime)}
                className="px-2.5 py-1 rounded-md bg-[#111821] border border-white/10 hover:border-[#36D6A0]/50 text-xs font-mono text-[#F4F7FA] transition-colors"
                title={`Seek to Rep #${r.rep_number} peak (${targetTime.toFixed(2)}s)`}
              >
                Rep #{r.rep_number} ({r.start_time_sec.toFixed(1)}s–{r.end_time_sec.toFixed(1)}s)
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
};
