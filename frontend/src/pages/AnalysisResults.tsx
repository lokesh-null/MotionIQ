import React, { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  Database,
  FileDown,
  FileText,
  Info,
  Layers,
  ShieldAlert,
} from 'lucide-react';
import { AssessmentCard } from '../components/AssessmentCard';
import { Header } from '../components/Header';
import { JointMetricCard } from '../components/JointMetricCard';
import { PerformanceChart } from '../components/PerformanceChart';
import { VideoPlayer } from '../components/VideoPlayer';
import { fetchAnalysisResults, getReportPdfUrl } from '../services/api';
import type { AnalysisResults } from '../types/biomechanics';

export const AnalysisResultsPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [results, setResults] = useState<AnalysisResults | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showReportModal, setShowReportModal] = useState(false);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    fetchAnalysisResults(id)
      .then((data) => {
        setResults(data);
        setError(null);
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load results.'))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="flex-1 flex flex-col min-w-0">
        <Header title="Analysis Results" subtitle="Loading computed biomechanical metrics..." />
        <main className="p-8 text-center text-xs text-[#98A5B5]">Loading analytical dashboard...</main>
      </div>
    );
  }

  if (error || !results) {
    return (
      <div className="flex-1 flex flex-col min-w-0">
        <Header title="Analysis Results" />
        <main className="p-6 max-w-3xl mx-auto space-y-4">
          <div className="bg-[#F16D73]/10 border border-[#F16D73]/40 rounded-xl p-5 text-xs text-[#F16D73]">
            {error || 'Results unavailable.'}
          </div>
          <Link to="/" className="inline-flex items-center gap-2 text-xs text-[#36D6A0]">
            <ArrowLeft className="w-3.5 h-3.5" /> Back to Dashboard
          </Link>
        </main>
      </div>
    );
  }

  const mv = results.movement_analysis;
  const assess = results.assessment;
  const quality = results.data_quality;
  const bio = results.biomechanics;
  const pdfUrl = getReportPdfUrl(results.analysis_id);

  const summaryEntries = Object.entries(bio.joint_summaries || {});
  const primarySummaries = summaryEntries.filter(([, s]) => s.sufficient_data);
  const primaryMetricValue =
    mv.summary_metrics.avg_max_knee_flexion_deg ??
    mv.summary_metrics.avg_front_knee_flexion_deg ??
    mv.summary_metrics.avg_max_shoulder_angle_deg ??
    mv.summary_metrics.avg_elbow_at_release_deg ??
    null;

  return (
    <div className="flex-1 flex flex-col min-w-0">
      <Header
        title={`${results.movement_label} — Results`}
        subtitle={`${results.video_metadata.filename} • ${results.video_metadata.width}×${results.video_metadata.height} @ ${results.video_metadata.fps} FPS • Analyzed in ${results.processing_details.processing_time_sec}s`}
        actions={
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setShowReportModal((prev) => !prev)}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-[#161F2B] border border-white/12 text-xs font-medium text-[#F4F7FA] hover:border-[#36D6A0]/50 transition-colors"
            >
              <FileText className="w-3.5 h-3.5 text-[#36D6A0]" />
              <span>{showReportModal ? 'Hide Report Preview' : 'Report Summary'}</span>
            </button>
            <a
              href={pdfUrl}
              download
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-[#161F2B] border border-[#36D6A0]/40 text-xs font-semibold text-[#36D6A0] hover:bg-[#36D6A0]/15 transition-colors"
            >
              <FileDown className="w-3.5 h-3.5" />
              <span>Download PDF</span>
            </a>
          </div>
        }
      />

      <main className="p-6 max-w-7xl w-full mx-auto space-y-6">
        {/* Optional Experimental / Quality Banner */}
        {(mv.experimental || quality.warnings.length > 0) && (
          <div className="bg-[#F4B860]/10 border border-[#F4B860]/35 rounded-xl p-4 space-y-1.5">
            {mv.experimental && (
              <div className="text-xs text-[#F4B860] flex items-start gap-2 font-medium">
                <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                <span>
                  Experimental Module: {mv.ball_velocity_disclaimer || 'Experimental upper-limb kinematics only.'}
                </span>
              </div>
            )}
            {quality.warnings.map((w, idx) => (
              <div key={idx} className="text-xs text-[#F4B860] flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                <span>{w}</span>
              </div>
            ))}
          </div>
        )}

        {/* In-App Report Preview Panel (Page 5 summary + PDF export) */}
        {showReportModal && (
          <section className="bg-[#161F2B] border border-[#36D6A0]/40 rounded-xl p-5 space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/8 pb-3">
              <div>
                <div className="text-xs font-mono text-[#36D6A0]">REPORT PREVIEW • ID {results.analysis_id.slice(0, 12)}</div>
                <h2 className="text-base font-semibold text-[#F4F7FA]">{results.movement_label} Assessment Report</h2>
              </div>
              <a
                href={pdfUrl}
                download
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-[#36D6A0] text-[#0B0F14] text-xs font-semibold"
              >
                <FileDown className="w-4 h-4" />
                <span>Download Full ReportLab PDF</span>
              </a>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
              <div className="bg-[#111821] p-3 rounded-lg border border-white/6">
                <div className="text-[#98A5B5]">Recording Metadata</div>
                <div className="text-[#F4F7FA] mt-1 font-mono">
                  {results.video_metadata.filename} ({results.video_metadata.duration_sec}s)
                </div>
              </div>
              <div className="bg-[#111821] p-3 rounded-lg border border-white/6">
                <div className="text-[#98A5B5]">Model & Sampling</div>
                <div className="text-[#F4F7FA] mt-1 font-mono">
                  {results.processing_details.model_used} • {results.processing_details.effective_fps} FPS
                </div>
              </div>
              <div className="bg-[#111821] p-3 rounded-lg border border-white/6">
                <div className="text-[#98A5B5]">Educational Disclaimer</div>
                <div className="text-[#98A5B5] mt-1">Included in PDF export with full time-series graphs.</div>
              </div>
            </div>
          </section>
        )}

        {/* Top Row: A. Annotated Video Player + B. Performance Summary */}
        <section className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <div className="lg:col-span-7">
            <VideoPlayer results={results} />
          </div>

          <div className="lg:col-span-5 space-y-4">
            {/* B. Performance Summary Card */}
            <div className="bg-[#161F2B] border border-white/10 rounded-xl p-5 space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-semibold text-[#F4F7FA]">Performance Summary</h3>
                  <p className="text-xs text-[#98A5B5]">Primary tracked side: {mv.primary_side_tracked}</p>
                </div>
                <div className="text-right">
                  <div className="text-[11px] text-[#98A5B5]">Composite Prototype Score</div>
                  <div className="text-xl font-mono font-bold text-[#36D6A0]">
                    {assess.composite_score !== null ? `${assess.composite_score}/100` : 'Withheld'}
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3 text-xs">
                <div className="bg-[#111821] p-3 rounded-lg border border-white/6">
                  <div className="text-[#98A5B5]">Repetitions Detected</div>
                  <div className="text-xl font-mono font-bold text-[#F4F7FA] mt-0.5">{mv.rep_count}</div>
                </div>
                <div className="bg-[#111821] p-3 rounded-lg border border-white/6">
                  <div className="text-[#98A5B5]">Active Duration</div>
                  <div className="text-xl font-mono font-bold text-[#F4F7FA] mt-0.5">
                    {mv.total_movement_duration_sec}s
                  </div>
                </div>
                <div className="bg-[#111821] p-3 rounded-lg border border-white/6">
                  <div className="text-[#98A5B5]">Avg Peak Primary Angle</div>
                  <div className="text-base font-mono font-semibold text-[#F4F7FA] mt-0.5">
                    {primaryMetricValue !== null && typeof primaryMetricValue === 'number'
                      ? `${primaryMetricValue}°`
                      : 'Insufficient'}
                  </div>
                </div>
                <div className="bg-[#111821] p-3 rounded-lg border border-white/6">
                  <div className="text-[#98A5B5]">Avg Rep Duration</div>
                  <div className="text-base font-mono font-semibold text-[#F4F7FA] mt-0.5">
                    {typeof mv.summary_metrics.avg_rep_duration_sec === 'number'
                      ? `${mv.summary_metrics.avg_rep_duration_sec}s`
                      : 'N/A'}
                  </div>
                </div>
              </div>

              {/* Repetition Breakdown Table */}
              {mv.repetitions.length > 0 && (
                <div className="space-y-2 pt-1">
                  <div className="text-xs font-semibold uppercase tracking-wider text-[#98A5B5]">
                    Per-Repetition Kinematics
                  </div>
                  <div className="max-h-56 overflow-y-auto border border-white/8 rounded-lg">
                    <table className="w-full text-left text-[11px] font-mono">
                      <thead className="bg-[#111821] text-[#98A5B5] sticky top-0">
                        <tr>
                          <th className="py-2 px-2.5">Rep</th>
                          <th className="py-2 px-2.5">Dur</th>
                          <th className="py-2 px-2.5">Peak Metric</th>
                          <th className="py-2 px-2.5">Secondary</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-white/6">
                        {mv.repetitions.map((r) => {
                          const m1 =
                            r.max_knee_flexion_deg !== undefined
                              ? `Knee ${r.max_knee_flexion_deg ?? '—'}°`
                              : r.front_knee_max_flexion_deg !== undefined
                              ? `${r.front_leg}: ${r.front_knee_max_flexion_deg ?? '—'}°`
                              : r.max_mean_shoulder_deg !== undefined
                              ? `Sh ${r.max_mean_shoulder_deg ?? '—'}°`
                              : `El ${r.elbow_angle_at_release_deg ?? '—'}°`;
                          const m2 =
                            r.max_trunk_inclination_deg !== undefined
                              ? `Trunk ${r.max_trunk_inclination_deg ?? '—'}°`
                              : r.max_ankle_spread_ratio !== undefined
                              ? `Spread ${r.max_ankle_spread_ratio ?? '—'}x`
                              : `Sh ${r.shoulder_angle_at_release_deg ?? '—'}°`;
                          return (
                            <tr key={r.rep_number} className="bg-[#0B0F14]/40">
                              <td className="py-2 px-2.5 text-[#36D6A0]">#{r.rep_number}</td>
                              <td className="py-2 px-2.5 text-[#F4F7FA]">{r.duration_sec}s</td>
                              <td className="py-2 px-2.5 text-[#F4F7FA]">{m1}</td>
                              <td className="py-2 px-2.5 text-[#98A5B5]">{m2}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Composite Score Methodology Transparency */}
              <div className="bg-[#111821] border border-white/6 rounded-lg p-3 text-[11px] text-[#98A5B5] space-y-1">
                <div className="font-semibold text-[#F4F7FA] flex items-center gap-1.5">
                  <Info className="w-3.5 h-3.5 text-[#36D6A0]" />
                  <span>Scoring Transparency ({Math.round(assess.composite_methodology.valid_weight_coverage * 100)}% coverage)</span>
                </div>
                <p>{assess.composite_methodology.normalization_method}</p>
                <p>{assess.composite_methodology.missing_data_handling}</p>
              </div>
            </div>
          </div>
        </section>

        {/* D. Biomechanical Graphs (Recharts) */}
        <section>
          <PerformanceChart results={results} />
        </section>

        {/* C. Joint Analysis Grid */}
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-[#F4F7FA]">Joint Kinematic Analysis</h3>
              <p className="text-xs text-[#98A5B5]">
                Calculated only from frames meeting landmark confidence threshold ({results.processing_details.confidence_threshold})
              </p>
            </div>
            <span className="text-xs font-mono text-[#98A5B5]">
              {primarySummaries.length}/{summaryEntries.length} valid series
            </span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {summaryEntries.map(([key, summary]) => (
              <JointMetricCard key={key} metricKey={key} summary={summary} />
            ))}
          </div>
        </section>

        {/* E. Technique Assessment */}
        <section className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h3 className="text-sm font-semibold text-[#F4F7FA]">Technique Assessment & Evidence</h3>
              <p className="text-xs text-[#98A5B5]">
                Transparent parameter checks distinguishing biomechanical definitions from prototype thresholds
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {assess.parameters.map((param) => (
              <AssessmentCard key={param.parameter_name} param={param} />
            ))}
          </div>

          {/* Positive & Improvement Summary */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-[#161F2B] border border-white/10 rounded-xl p-4 space-y-2.5">
              <div className="flex items-center gap-2 text-xs font-semibold text-[#36D6A0] uppercase tracking-wider">
                <CheckCircle2 className="w-4 h-4" />
                <span>Positive Observations</span>
              </div>
              {assess.positive_observations.length === 0 ? (
                <p className="text-xs text-[#98A5B5]">No criteria reached the GOOD threshold with available observations.</p>
              ) : (
                <ul className="space-y-2">
                  {assess.positive_observations.map((obs, idx) => (
                    <li key={idx} className="text-xs text-[#F4F7FA]/90 flex items-start gap-2">
                      <span className="text-[#36D6A0] mt-0.5">•</span>
                      <span>{obs}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="bg-[#161F2B] border border-white/10 rounded-xl p-4 space-y-2.5">
              <div className="flex items-center gap-2 text-xs font-semibold text-[#F4B860] uppercase tracking-wider">
                <Layers className="w-4 h-4" />
                <span>Areas Requiring Improvement & Adjustments</span>
              </div>
              {assess.technique_adjustments.length === 0 ? (
                <p className="text-xs text-[#98A5B5]">No technique adjustments flagged across evaluated parameters.</p>
              ) : (
                <ul className="space-y-2">
                  {assess.technique_adjustments.map((adj, idx) => (
                    <li key={idx} className="text-xs text-[#F4F7FA]/90">
                      <span className="font-semibold text-[#F4B860]">{adj.parameter}: </span>
                      <span className="text-[#98A5B5]">{adj.suggestion}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </section>

        {/* F. Data Quality & Camera Perspective Limitations */}
        <section className="bg-[#161F2B] border border-white/10 rounded-xl p-5 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/8 pb-3">
            <div className="flex items-center gap-2">
              <Database className="w-4 h-4 text-[#36D6A0]" />
              <h3 className="text-sm font-semibold text-[#F4F7FA]">Data Quality & Camera Diagnostics</h3>
            </div>
            <span
              className={`px-2.5 py-0.5 rounded font-mono text-xs font-semibold ${
                quality.quality_status === 'GOOD'
                  ? 'bg-[#36D6A0]/15 text-[#36D6A0]'
                  : quality.quality_status === 'LIMITED'
                  ? 'bg-[#F4B860]/15 text-[#F4B860]'
                  : 'bg-[#F16D73]/15 text-[#F16D73]'
              }`}
            >
              QUALITY: {quality.quality_status}
            </span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 text-xs">
            <div className="bg-[#111821] p-3 rounded-lg border border-white/6">
              <div className="text-[#98A5B5]">Total Frames</div>
              <div className="font-mono font-semibold text-[#F4F7FA] mt-0.5">{quality.total_frames}</div>
            </div>
            <div className="bg-[#111821] p-3 rounded-lg border border-white/6">
              <div className="text-[#98A5B5]">Processed</div>
              <div className="font-mono font-semibold text-[#F4F7FA] mt-0.5">{quality.frames_processed}</div>
            </div>
            <div className="bg-[#111821] p-3 rounded-lg border border-white/6">
              <div className="text-[#98A5B5]">Valid Landmark Ratio</div>
              <div className="font-mono font-semibold text-[#36D6A0] mt-0.5">
                {(quality.valid_frame_ratio * 100).toFixed(1)}%
              </div>
            </div>
            <div className="bg-[#111821] p-3 rounded-lg border border-white/6">
              <div className="text-[#98A5B5]">Full Body Visible</div>
              <div className="font-mono font-semibold text-[#F4F7FA] mt-0.5">
                {(quality.full_body_visible_ratio * 100).toFixed(1)}%
              </div>
            </div>
            <div className="bg-[#111821] p-3 rounded-lg border border-white/6">
              <div className="text-[#98A5B5]">Mean Confidence</div>
              <div className="font-mono font-semibold text-[#F4F7FA] mt-0.5">
                {(quality.mean_landmark_confidence * 100).toFixed(1)}%
              </div>
            </div>
            <div className="bg-[#111821] p-3 rounded-lg border border-white/6">
              <div className="text-[#98A5B5]">Inferred Perspective</div>
              <div className="font-mono font-semibold text-[#F4F7FA] uppercase mt-0.5">
                {quality.inferred_perspective}
              </div>
            </div>
          </div>

          {/* Per-Landmark Visibility Grid */}
          <div className="space-y-2">
            <div className="text-xs font-medium text-[#F4F7FA]">Per-Landmark Mean Visibility & Reliability</div>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2 text-[11px] font-mono">
              {Object.entries(quality.landmark_visibility || {}).map(([name, info]) => (
                <div key={name} className="bg-[#111821] p-2 rounded border border-white/6 flex flex-col gap-0.5">
                  <span className="text-[#98A5B5] truncate">{name.replace('_', ' ')}</span>
                  <span className={info.reliable_ratio >= 0.7 ? 'text-[#36D6A0]' : 'text-[#F4B860]'}>
                    {Math.round(info.mean_confidence * 100)}% ({Math.round(info.reliable_ratio * 100)}% ok)
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* 2D Camera Limitations & Disclaimer */}
          <div className="bg-[#0B0F14] border border-white/8 rounded-lg p-3.5 space-y-1.5 text-xs text-[#98A5B5]">
            <div className="flex items-center gap-2 font-semibold text-[#F4F7FA]">
              <ShieldAlert className="w-4 h-4 text-[#F4B860]" />
              <span>2D Camera Limitations & Prototype Scope</span>
            </div>
            {quality.camera_limitations.map((lim, i) => (
              <p key={i}>• {lim}</p>
            ))}
            <p className="text-[#F4B860]/90 pt-1">{assess.prototype_disclaimer}</p>
          </div>
        </section>
      </main>
    </div>
  );
};
