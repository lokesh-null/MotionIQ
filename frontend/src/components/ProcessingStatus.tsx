import React from 'react';
import { CheckCircle2, Loader2, XCircle } from 'lucide-react';
import type { AnalysisStatusResponse } from '../types/biomechanics';

interface ProcessingStatusProps {
  statusData: AnalysisStatusResponse;
}

const PIPELINE_STAGES = [
  { key: 'video_validation', label: 'Video Validation' },
  { key: 'pose_estimation', label: 'Frame Extraction & MediaPipe Pose Estimation' },
  { key: 'landmark_processing', label: 'Landmark Confidence & Camera Quality Evaluation' },
  { key: 'biomechanical_calculations', label: 'Biomechanical Kinematics & Angular Velocity' },
  { key: 'movement_classification', label: 'Movement Phase & Repetition Detection' },
  { key: 'assessment_generation', label: 'Evidence-Based Technique Assessment' },
  { key: 'annotated_video', label: 'Annotated H.264 Skeleton Video Rendering' },
  { key: 'report_generation', label: 'PDF Assessment Report Compilation' },
];

export const ProcessingStatus: React.FC<ProcessingStatusProps> = ({ statusData }) => {
  const currentStageIdx = PIPELINE_STAGES.findIndex((s) => s.key === statusData.stage);
  const isFailed = statusData.status === 'failed';
  const isCompleted = statusData.status === 'completed';

  return (
    <div className="bg-[#161F2B] border border-white/10 rounded-xl p-6 space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="text-xs font-mono uppercase tracking-wider text-[#36D6A0]">
            {statusData.movement_type.replace('_', ' ')} • {statusData.camera_perspective} view
          </div>
          <h2 className="text-lg font-semibold text-[#F4F7FA] mt-1">{statusData.filename}</h2>
        </div>
        <div className="text-right">
          <div className="text-2xl font-mono font-bold text-[#F4F7FA]">
            {statusData.progress_percent.toFixed(1)}%
          </div>
          <div className="text-xs font-mono text-[#98A5B5]">
            Frames: {statusData.frames_processed} / {statusData.total_frames || '—'}
          </div>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="w-full h-2.5 bg-[#0B0F14] rounded-full overflow-hidden border border-white/6">
        <div
          className={`h-full transition-all duration-300 ${
            isFailed ? 'bg-[#F16D73]' : 'bg-[#36D6A0]'
          }`}
          style={{ width: `${Math.max(2, Math.min(100, statusData.progress_percent))}%` }}
        />
      </div>

      {/* Live Operation Box */}
      <div
        className={`rounded-lg p-3.5 border text-xs flex items-center gap-3 ${
          isFailed
            ? 'bg-[#F16D73]/10 border-[#F16D73]/40 text-[#F16D73]'
            : 'bg-[#111821] border-white/8 text-[#F4F7FA]'
        }`}
      >
        {isFailed ? (
          <XCircle className="w-4 h-4 shrink-0" />
        ) : isCompleted ? (
          <CheckCircle2 className="w-4 h-4 text-[#36D6A0] shrink-0" />
        ) : (
          <Loader2 className="w-4 h-4 text-[#36D6A0] animate-spin shrink-0" />
        )}
        <div>
          <div className="font-medium">
            {isFailed ? statusData.error_message || 'Processing failed' : statusData.current_operation}
          </div>
        </div>
      </div>

      {/* Pipeline Stage Checklist */}
      <div className="space-y-2">
        <div className="text-xs font-semibold uppercase tracking-wider text-[#98A5B5]">
          Pipeline Stage Telemetry
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {PIPELINE_STAGES.map((stage, idx) => {
            const done = isCompleted || (currentStageIdx > idx && !isFailed);
            const active = !isCompleted && !isFailed && currentStageIdx === idx;
            return (
              <div
                key={stage.key}
                className={`px-3 py-2.5 rounded-lg border text-xs flex items-center gap-2.5 ${
                  done
                    ? 'bg-[#36D6A0]/8 border-[#36D6A0]/30 text-[#F4F7FA]'
                    : active
                    ? 'bg-[#111821] border-[#36D6A0]/60 text-[#F4F7FA]'
                    : 'bg-[#111821]/60 border-white/6 text-[#98A5B5]'
                }`}
              >
                {done ? (
                  <CheckCircle2 className="w-3.5 h-3.5 text-[#36D6A0] shrink-0" />
                ) : active ? (
                  <Loader2 className="w-3.5 h-3.5 text-[#36D6A0] animate-spin shrink-0" />
                ) : (
                  <span className="w-3.5 h-3.5 rounded-full border border-white/20 shrink-0" />
                )}
                <span className="truncate">{stage.label}</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
