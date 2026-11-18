import React, { useRef, useState } from 'react';
import { AlertTriangle, CheckCircle2, FileVideo, Film, Loader2, UploadCloud } from 'lucide-react';
import type { MovementType, SampleVideoItem, UploadResponse } from '../types/biomechanics';
import { getRawVideoUrl } from '../services/api';

interface UploadZoneProps {
  selectedMovement: MovementType;
  onFileSelected: (file: File) => void;
  onSampleSelected: (sample: SampleVideoItem) => void;
  samples: SampleVideoItem[];
  uploading: boolean;
  uploadedInfo: UploadResponse | null;
  localPreviewUrl: string | null;
  activeSampleTitle: string | null;
  error: string | null;
}

export const UploadZone: React.FC<UploadZoneProps> = ({
  selectedMovement,
  onFileSelected,
  onSampleSelected,
  samples,
  uploading,
  uploadedInfo,
  localPreviewUrl,
  activeSampleTitle,
  error,
}) => {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [previewError, setPreviewError] = useState(false);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragActive(false);
    const file = e.dataTransfer.files?.[0];
    if (file) {
      setPreviewError(false);
      onFileSelected(file);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setPreviewError(false);
      onFileSelected(file);
    }
  };

  // Sort matching samples for the selected movement module first
  const sortedSamples = [...samples].sort((a, b) => {
    const aMatch = a.movement_type === selectedMovement ? 0 : 1;
    const bMatch = b.movement_type === selectedMovement ? 0 : 1;
    return aMatch - bMatch;
  });

  const previewSrc = localPreviewUrl || (uploadedInfo ? getRawVideoUrl(uploadedInfo.analysis_id) : null);

  return (
    <div className="space-y-4">
      {/* Verified real-human sample loader */}
      {sortedSamples.length > 0 && (
        <div className="bg-[#111821] border border-white/10 rounded-xl p-4">
          <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[#36D6A0]">
              <Film className="w-4 h-4" />
              <span>Choose Built-In Real-Human Sample Video (Works on Any Device)</span>
            </div>
            <span className="text-[11px] text-[#98A5B5]">Tap any sample to preview & analyze</span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
            {sortedSamples.map((s) => {
              const isSelected =
                uploadedInfo?.filename === s.filename || activeSampleTitle === s.title;
              const matchesModule = s.movement_type === selectedMovement;
              return (
                <button
                  key={s.id}
                  type="button"
                  disabled={uploading}
                  onClick={() => {
                    setPreviewError(false);
                    onSampleSelected(s);
                  }}
                  className={`text-left p-3 rounded-lg border transition-colors ${
                    isSelected
                      ? 'bg-[#36D6A0]/15 border-[#36D6A0]'
                      : matchesModule
                      ? 'bg-[#161F2B] border-[#36D6A0]/35 hover:border-[#36D6A0]'
                      : 'bg-[#161F2B]/70 border-white/8 hover:border-white/25'
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-semibold text-[#F4F7FA] truncate">{s.title}</span>
                    <span className="text-[10px] font-mono uppercase px-1.5 py-0.5 rounded bg-[#0B0F14] text-[#36D6A0] shrink-0">
                      {s.camera_perspective}
                    </span>
                  </div>
                  <p className="text-[11px] text-[#98A5B5] mt-1 line-clamp-2">{s.description}</p>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Drag and drop zone */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragActive(true);
        }}
        onDragLeave={() => setDragActive(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        className={`border-2 border-dashed rounded-xl p-5 text-center cursor-pointer transition-colors ${
          dragActive
            ? 'border-[#36D6A0] bg-[#36D6A0]/8'
            : 'border-white/12 bg-[#111821] hover:border-[#36D6A0]/50'
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".mp4,.mov,.avi,video/mp4,video/quicktime,video/x-msvideo"
          className="hidden"
          onChange={handleFileChange}
        />
        <div className="w-10 h-10 rounded-lg bg-[#161F2B] border border-white/10 mx-auto mb-2.5 flex items-center justify-center text-[#36D6A0]">
          <UploadCloud className="w-5 h-5" />
        </div>
        <div className="text-sm font-medium text-[#F4F7FA]">
          {uploading ? 'Preparing and validating video with backend...' : 'Or upload your own video file'}
        </div>
        <p className="text-xs text-[#98A5B5] mt-1">
          Supported formats: <span className="font-mono text-[#F4F7FA]">MP4, MOV, AVI</span> (max 250 MB, 0.5s–180s)
        </p>
      </div>

      {/* Validation Error */}
      {error && (
        <div className="bg-[#F16D73]/10 border border-[#F16D73]/40 rounded-lg p-3.5 flex items-start gap-2.5 text-xs text-[#F16D73]">
          <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
          <div>{error}</div>
        </div>
      )}

      {/* Instant Video Preview (shows immediately when sample or local file is chosen, even while backend validates) */}
      {(previewSrc || uploadedInfo) && (
        <div className="bg-[#161F2B] border border-white/10 rounded-xl p-4 space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              {uploading ? (
                <Loader2 className="w-4 h-4 text-[#36D6A0] animate-spin" />
              ) : (
                <CheckCircle2 className="w-4 h-4 text-[#36D6A0]" />
              )}
              <span className="text-xs font-semibold text-[#F4F7FA]">
                {uploadedInfo ? (
                  <>
                    Validated Recording: <span className="font-mono">{uploadedInfo.filename}</span>
                  </>
                ) : (
                  <>
                    Previewing: <span className="font-mono">{activeSampleTitle || 'Selected Video'}</span>
                  </>
                )}
              </span>
            </div>
            <span className="text-[11px] font-mono text-[#36D6A0]">
              {uploading ? 'CONNECTING TO BACKEND...' : 'READY FOR ANALYSIS'}
            </span>
          </div>

          {previewSrc && !previewError ? (
            <div className="bg-[#0B0F14] rounded-lg overflow-hidden border border-white/8">
              <video
                key={previewSrc}
                src={previewSrc}
                controls
                playsInline
                preload="metadata"
                onError={() => setPreviewError(true)}
                className="w-full max-h-72 object-contain mx-auto"
              />
            </div>
          ) : (
            <div className="bg-[#0B0F14] rounded-lg p-4 border border-white/8 flex items-center gap-3 text-xs text-[#98A5B5]">
              <FileVideo className="w-5 h-5 text-[#F4B860] shrink-0" />
              <span>
                Browser inline preview is unavailable for this container codec, but OpenCV decoded and validated the
                frames. The processed output will be transcoded to H.264 MP4 for playback.
              </span>
            </div>
          )}

          {uploadedInfo && (
            <>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                <div className="bg-[#111821] p-2.5 rounded-lg border border-white/6">
                  <div className="text-[11px] text-[#98A5B5]">Dimensions</div>
                  <div className="font-mono font-medium text-[#F4F7FA] mt-0.5">
                    {uploadedInfo.validation.metadata.width} × {uploadedInfo.validation.metadata.height}
                  </div>
                </div>
                <div className="bg-[#111821] p-2.5 rounded-lg border border-white/6">
                  <div className="text-[11px] text-[#98A5B5]">Frame Rate</div>
                  <div className="font-mono font-medium text-[#F4F7FA] mt-0.5">
                    {uploadedInfo.validation.metadata.fps} FPS
                  </div>
                </div>
                <div className="bg-[#111821] p-2.5 rounded-lg border border-white/6">
                  <div className="text-[11px] text-[#98A5B5]">Duration</div>
                  <div className="font-mono font-medium text-[#F4F7FA] mt-0.5">
                    {uploadedInfo.validation.metadata.duration_sec} s
                  </div>
                </div>
                <div className="bg-[#111821] p-2.5 rounded-lg border border-white/6">
                  <div className="text-[11px] text-[#98A5B5]">Frames</div>
                  <div className="font-mono font-medium text-[#F4F7FA] mt-0.5">
                    {uploadedInfo.validation.metadata.frame_count}
                  </div>
                </div>
              </div>

              {uploadedInfo.validation.warnings?.length > 0 && (
                <div className="bg-[#F4B860]/10 border border-[#F4B860]/30 rounded-lg p-3 space-y-1">
                  {uploadedInfo.validation.warnings.map((w, idx) => (
                    <div key={idx} className="text-xs text-[#F4B860] flex items-start gap-2">
                      <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                      <span>{w}</span>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
};
