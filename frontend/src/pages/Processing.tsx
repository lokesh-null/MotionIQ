import React, { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, RefreshCw } from 'lucide-react';
import { Header } from '../components/Header';
import { ProcessingStatus } from '../components/ProcessingStatus';
import { fetchAnalysisStatus } from '../services/api';
import type { AnalysisStatusResponse } from '../types/biomechanics';

export const Processing: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [statusData, setStatusData] = useState<AnalysisStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    let timerId: number | undefined;
    let consecutiveFailures = 0;

    const poll = async () => {
      try {
        const res = await fetchAnalysisStatus(id);
        if (cancelled) return;
        consecutiveFailures = 0;
        setStatusData(res);
        setError(null);

        if (res.status === 'completed') {
          timerId = window.setTimeout(() => {
            if (!cancelled) navigate(`/results/${id}`, { replace: true });
          }, 400);
          return;
        }
        if (res.status === 'failed') {
          return;
        }
        timerId = window.setTimeout(poll, 600);
      } catch (e) {
        if (!cancelled) {
          consecutiveFailures += 1;
          const msg = e instanceof Error ? e.message : 'Unable to fetch processing status.';
          // Only surface transient network errors after multiple consecutive poll failures
          if (consecutiveFailures >= 5) {
            setError(
              msg.includes('Failed to fetch')
                ? 'Connection to cloud worker interrupted (server may be restarting). Retrying automatically...'
                : msg
            );
          }
          timerId = window.setTimeout(poll, 1500);
        }
      }
    };

    poll();
    return () => {
      cancelled = true;
      if (timerId) window.clearTimeout(timerId);
    };
  }, [id, navigate]);

  return (
    <div className="flex-1 flex flex-col min-w-0">
      <Header
        title="Processing Biomechanical Pipeline"
        subtitle="Real-time computer vision inference, kinematic calculation, and annotated video rendering"
      />

      <main className="p-6 max-w-4xl w-full mx-auto space-y-6">
        {error && (
          <div className="bg-[#F4B860]/10 border border-[#F4B860]/40 rounded-lg p-4 text-xs text-[#F4B860] flex flex-wrap items-center justify-between gap-3">
            <span>{error}</span>
            <Link
              to="/new"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-[#36D6A0] text-[#0B0F14] font-semibold"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Run New Analysis</span>
            </Link>
          </div>
        )}

        {statusData ? (
          <ProcessingStatus statusData={statusData} />
        ) : (
          <div className="bg-[#161F2B] border border-white/10 rounded-xl p-8 text-center text-xs text-[#98A5B5]">
            Connecting to MotionIQ processing worker...
          </div>
        )}

        {statusData?.status === 'failed' && (
          <div className="flex items-center gap-3">
            <Link
              to="/new"
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-[#36D6A0] text-[#0B0F14] text-xs font-semibold"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Try Another Video</span>
            </Link>
            <Link
              to="/"
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-[#161F2B] border border-white/10 text-xs text-[#F4F7FA]"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>Back to Dashboard</span>
            </Link>
          </div>
        )}
      </main>
    </div>
  );
};
