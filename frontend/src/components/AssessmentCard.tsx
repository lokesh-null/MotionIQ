import React from 'react';
import { AlertTriangle, CheckCircle2, HelpCircle, XCircle } from 'lucide-react';
import type { AssessmentParameter } from '../types/biomechanics';

interface AssessmentCardProps {
  param: AssessmentParameter;
}

const STATUS_STYLE: Record<string, { badge: string; icon: React.ReactNode }> = {
  GOOD: {
    badge: 'bg-[#36D6A0]/15 text-[#36D6A0] border-[#36D6A0]/40',
    icon: <CheckCircle2 className="w-4 h-4 text-[#36D6A0]" />,
  },
  'NEEDS IMPROVEMENT': {
    badge: 'bg-[#F4B860]/15 text-[#F4B860] border-[#F4B860]/40',
    icon: <AlertTriangle className="w-4 h-4 text-[#F4B860]" />,
  },
  'OUTSIDE REFERENCE RANGE': {
    badge: 'bg-[#F16D73]/15 text-[#F16D73] border-[#F16D73]/40',
    icon: <XCircle className="w-4 h-4 text-[#F16D73]" />,
  },
  'INSUFFICIENT DATA': {
    badge: 'bg-white/10 text-[#98A5B5] border-white/20',
    icon: <HelpCircle className="w-4 h-4 text-[#98A5B5]" />,
  },
};

export const AssessmentCard: React.FC<AssessmentCardProps> = ({ param }) => {
  const st = STATUS_STYLE[param.status] || STATUS_STYLE['INSUFFICIENT DATA'];

  return (
    <div className="bg-[#161F2B] border border-white/10 rounded-xl p-4 space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          {st.icon}
          <h4 className="text-sm font-semibold text-[#F4F7FA]">{param.parameter_name}</h4>
        </div>
        <span className={`px-2.5 py-0.5 rounded text-[11px] font-mono font-semibold border ${st.badge}`}>
          {param.status}
        </span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs">
        <div className="bg-[#111821] p-2.5 rounded-lg border border-white/6">
          <div className="text-[11px] text-[#98A5B5]">Measured Value</div>
          <div className="font-mono font-semibold text-[#F4F7FA] mt-0.5">
            {param.measured_value !== null ? `${param.measured_value} ${param.unit}` : 'INSUFFICIENT'}
          </div>
        </div>
        <div className="bg-[#111821] p-2.5 rounded-lg border border-white/6">
          <div className="text-[11px] text-[#98A5B5]">Reference Criteria</div>
          <div className="font-mono text-[#F4F7FA] mt-0.5">{param.reference_range}</div>
        </div>
        <div className="bg-[#111821] p-2.5 rounded-lg border border-white/6">
          <div className="text-[11px] text-[#98A5B5]">Confidence / Source</div>
          <div className="font-mono text-[#F4F7FA] mt-0.5">
            {Math.round(param.confidence * 100)}% •{' '}
            <span className="text-[10px] text-[#98A5B5]">
              {param.criteria_source.replace(/_/g, ' ')}
            </span>
          </div>
        </div>
      </div>

      <p className="text-xs text-[#F4F7FA]/90 leading-relaxed">{param.explanation}</p>

      {param.recommendation && (
        <div className="bg-[#0B0F14] border border-white/6 rounded-lg px-3 py-2 text-xs text-[#98A5B5]">
          <span className="text-[#36D6A0] font-semibold">Adjustment Cue: </span>
          {param.recommendation}
        </div>
      )}
    </div>
  );
};
