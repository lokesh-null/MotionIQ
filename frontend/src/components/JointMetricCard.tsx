import React from 'react';
import { AlertCircle } from 'lucide-react';
import type { JointSummary } from '../types/biomechanics';

interface JointMetricCardProps {
  metricKey: string;
  summary: JointSummary;
}

export const JointMetricCard: React.FC<JointMetricCardProps> = ({ metricKey, summary }) => {
  const isFlexion = metricKey.includes('flexion');
  const isTrunk = metricKey.includes('trunk');
  const badgeLabel = isTrunk ? 'vs. Vertical' : isFlexion ? 'Flexion (0°=Straight)' : 'Internal (180°=Straight)';
  const confPct = Math.round((summary.mean_confidence || 0) * 100);
  const validPct = Math.round((summary.valid_ratio || 0) * 100);

  return (
    <div className="bg-[#161F2B] border border-white/10 rounded-xl p-4 flex flex-col justify-between gap-3">
      <div>
        <div className="flex items-start justify-between gap-2">
          <h4 className="text-sm font-semibold text-[#F4F7FA]">{summary.label}</h4>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#111821] border border-white/10 text-[#98A5B5] shrink-0">
            {badgeLabel}
          </span>
        </div>
        <p className="text-[11px] text-[#98A5B5] mt-1">{summary.landmarks}</p>
      </div>

      {!summary.sufficient_data ? (
        <div className="bg-[#0B0F14] border border-white/6 rounded-lg p-3 text-xs text-[#F4B860] flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>Insufficient reliable frames ({summary.valid_frames}/{summary.total_frames}).</span>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div className="bg-[#111821] p-2.5 rounded-lg border border-white/6">
            <div className="text-[11px] text-[#98A5B5]">Mean / ROM</div>
            <div className="font-mono font-semibold text-[#F4F7FA] mt-0.5">
              {summary.mean_deg}° <span className="text-[#36D6A0] text-[11px]">(Δ{summary.rom_deg}°)</span>
            </div>
          </div>
          <div className="bg-[#111821] p-2.5 rounded-lg border border-white/6">
            <div className="text-[11px] text-[#98A5B5]">Min / Max</div>
            <div className="font-mono font-semibold text-[#F4F7FA] mt-0.5">
              {summary.min_deg}° – {summary.max_deg}°
            </div>
          </div>
          <div className="bg-[#111821] p-2.5 rounded-lg border border-white/6">
            <div className="text-[11px] text-[#98A5B5]">Peak Ang. Vel</div>
            <div className="font-mono font-semibold text-[#F4F7FA] mt-0.5">
              {summary.peak_angular_velocity_deg_s !== null ? `${summary.peak_angular_velocity_deg_s} °/s` : 'N/A'}
            </div>
          </div>
          <div className="bg-[#111821] p-2.5 rounded-lg border border-white/6">
            <div className="text-[11px] text-[#98A5B5]">Valid Obs.</div>
            <div className="font-mono font-semibold text-[#F4F7FA] mt-0.5">
              {validPct}% ({summary.valid_frames})
            </div>
          </div>
        </div>
      )}

      {/* Confidence Bar */}
      <div className="space-y-1">
        <div className="flex justify-between text-[11px]">
          <span className="text-[#98A5B5]">Mean Landmark Confidence</span>
          <span
            className={`font-mono font-medium ${
              confPct >= 75 ? 'text-[#36D6A0]' : confPct >= 50 ? 'text-[#F4B860]' : 'text-[#F16D73]'
            }`}
          >
            {confPct}%
          </span>
        </div>
        <div className="w-full h-1.5 bg-[#0B0F14] rounded-full overflow-hidden">
          <div
            className={`h-full ${
              confPct >= 75 ? 'bg-[#36D6A0]' : confPct >= 50 ? 'bg-[#F4B860]' : 'bg-[#F16D73]'
            }`}
            style={{ width: `${Math.min(100, confPct)}%` }}
          />
        </div>
      </div>
    </div>
  );
};
