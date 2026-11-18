import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Activity,
  ArrowRight,
  BarChart3,
  Camera,
  FileDown,
  FolderOpen,
  PlusCircle,
  Trash2,
  Video,
} from 'lucide-react';
import { Header } from '../components/Header';
import {
  DEFAULT_MOVEMENTS,
  deleteAnalysis,
  fetchAnalyses,
  fetchMovementsAndGuidelines,
  getReportPdfUrl,
} from '../services/api';
import type { AnalysisListItem, MovementInfo } from '../types/biomechanics';

export const Dashboard: React.FC = () => {
  const [analyses, setAnalyses] = useState<AnalysisListItem[]>([]);
  const [movements, setMovements] = useState<MovementInfo[]>(DEFAULT_MOVEMENTS);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    try {
      setLoading(true);
      const [listData, mvData] = await Promise.all([fetchAnalyses(), fetchMovementsAndGuidelines()]);
      setAnalyses(listData);
      if (mvData.movements?.length) setMovements(mvData.movements);
      setError(null);
    } catch {
      // Keep default movements visible even if backend is waking up
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleDelete = async (id: string) => {
    try {
      await deleteAnalysis(id);
      setAnalyses((prev) => prev.filter((a) => a.analysis_id !== id));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to delete analysis.');
    }
  };

  const workflowSteps = [
    {
      icon: <Video className="w-4 h-4 text-[#36D6A0]" />,
      title: '1. Recording & Validation',
      desc: 'Upload MP4, MOV, or AVI footage and verify resolution, frame rate, and perspective guidelines.',
    },
    {
      icon: <Camera className="w-4 h-4 text-[#36D6A0]" />,
      title: '2. 33-Landmark Pose Tracking',
      desc: 'MediaPipe Pose Landmarker extracts confidence-scored body coordinates with real frame timestamps.',
    },
    {
      icon: <Activity className="w-4 h-4 text-[#36D6A0]" />,
      title: '3. Kinematic Computation',
      desc: 'Savitzky-Golay filtered joint angles, angular velocities, repetition segmentation, and symmetry checks.',
    },
    {
      icon: <BarChart3 className="w-4 h-4 text-[#36D6A0]" />,
      title: '4. Assessment & PDF Report',
      desc: 'Transparent rule evaluation against documented criteria plus downloadable ReportLab PDF output.',
    },
  ];

  return (
    <div className="flex-1 flex flex-col min-w-0">
      <Header
        title="Biomechanics Overview"
        subtitle="Computer-vision sports movement analysis and technique evaluation workspace"
      />

      <main className="p-6 space-y-6 max-w-7xl w-full mx-auto">
        {/* Welcome Banner */}
        <section className="bg-[#161F2B] border border-white/10 rounded-xl p-6 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-2 max-w-2xl">
            <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-md bg-[#36D6A0]/12 border border-[#36D6A0]/30 text-[#36D6A0] text-xs font-mono">
              <Activity className="w-3.5 h-3.5" />
              <span>MOTIONIQ ANALYTICAL ENGINE</span>
            </div>
            <h2 className="text-xl font-semibold text-[#F4F7FA]">
              Evidence-Based Movement Assessment from Video
            </h2>
            <p className="text-sm text-[#98A5B5] leading-relaxed">
              Analyze athletic technique using MediaPipe 33-landmark pose estimation, timestamped joint kinematics,
              movement-phase segmentation, and transparent biomechanical criteria without fabricated measurements.
            </p>
          </div>
          <Link
            to="/new"
            className="inline-flex items-center justify-center gap-2 px-5 py-3 rounded-lg bg-[#36D6A0] text-[#0B0F14] text-sm font-semibold hover:bg-[#2ec290] transition-colors shrink-0"
          >
            <PlusCircle className="w-4 h-4" />
            <span>Start New Analysis</span>
          </Link>
        </section>

        {error && (
          <div className="bg-[#F16D73]/10 border border-[#F16D73]/40 rounded-lg p-4 text-xs text-[#F16D73]">
            {error}
          </div>
        )}

        {/* Recent Assessments */}
        <section className="bg-[#161F2B] border border-white/10 rounded-xl p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-[#F4F7FA]">Recent Assessments</h3>
              <p className="text-xs text-[#98A5B5]">
                Persisted biomechanical assessments executed on real uploaded or sample videos
              </p>
            </div>
            <span className="text-xs font-mono text-[#98A5B5]">
              {analyses.length} {analyses.length === 1 ? 'record' : 'records'}
            </span>
          </div>

          {loading ? (
            <div className="p-8 text-center text-xs text-[#98A5B5]">Loading assessment history...</div>
          ) : analyses.length === 0 ? (
            <div className="bg-[#111821] border border-dashed border-white/12 rounded-xl p-10 text-center space-y-3">
              <div className="w-11 h-11 rounded-lg bg-[#161F2B] border border-white/10 mx-auto flex items-center justify-center text-[#98A5B5]">
                <FolderOpen className="w-5 h-5" />
              </div>
              <div className="text-sm font-medium text-[#F4F7FA]">No Movement Assessments Recorded Yet</div>
              <p className="text-xs text-[#98A5B5] max-w-md mx-auto">
                MotionIQ never populates placeholder metrics. Upload an athlete recording or select a real-human sample
                video in New Analysis to run pose tracking and generate your first assessment.
              </p>
              <div className="pt-1">
                <Link
                  to="/new"
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-[#36D6A0] text-[#0B0F14] text-xs font-semibold hover:bg-[#2ec290] transition-colors"
                >
                  <PlusCircle className="w-3.5 h-3.5" />
                  <span>Create First Assessment</span>
                </Link>
              </div>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-white/8 text-[#98A5B5] uppercase text-[11px]">
                    <th className="py-2.5 px-3">Movement</th>
                    <th className="py-2.5 px-3">Video File</th>
                    <th className="py-2.5 px-3">Perspective</th>
                    <th className="py-2.5 px-3">Reps</th>
                    <th className="py-2.5 px-3">Composite</th>
                    <th className="py-2.5 px-3">Quality</th>
                    <th className="py-2.5 px-3">Status</th>
                    <th className="py-2.5 px-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/6">
                  {analyses.map((item) => (
                    <tr key={item.analysis_id} className="hover:bg-[#111821]/60">
                      <td className="py-3 px-3 font-medium text-[#F4F7FA] capitalize">
                        {item.movement_type.replace('_', ' ')}
                      </td>
                      <td className="py-3 px-3 font-mono text-[#98A5B5]">{item.filename}</td>
                      <td className="py-3 px-3 uppercase font-mono text-[#98A5B5]">{item.camera_perspective}</td>
                      <td className="py-3 px-3 font-mono text-[#F4F7FA]">
                        {item.rep_count !== null ? item.rep_count : '—'}
                      </td>
                      <td className="py-3 px-3 font-mono text-[#36D6A0]">
                        {item.composite_score !== null ? `${item.composite_score}/100` : '—'}
                      </td>
                      <td className="py-3 px-3 font-mono text-[#98A5B5]">
                        {item.quality_status || '—'}
                      </td>
                      <td className="py-3 px-3">
                        <span
                          className={`px-2 py-0.5 rounded font-mono text-[10px] uppercase ${
                            item.status === 'completed'
                              ? 'bg-[#36D6A0]/15 text-[#36D6A0]'
                              : item.status === 'failed'
                              ? 'bg-[#F16D73]/15 text-[#F16D73]'
                              : 'bg-[#F4B860]/15 text-[#F4B860]'
                          }`}
                        >
                          {item.status}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-right">
                        <div className="inline-flex items-center gap-2">
                          {item.status === 'completed' ? (
                            <>
                              <Link
                                to={`/results/${item.analysis_id}`}
                                className="px-2.5 py-1 rounded bg-[#36D6A0]/15 text-[#36D6A0] hover:bg-[#36D6A0]/25 font-medium"
                              >
                                Results
                              </Link>
                              <a
                                href={getReportPdfUrl(item.analysis_id)}
                                className="p-1.5 rounded bg-[#111821] border border-white/10 text-[#F4F7FA] hover:border-[#36D6A0]/50"
                                title="Download PDF Report"
                              >
                                <FileDown className="w-3.5 h-3.5" />
                              </a>
                            </>
                          ) : item.status === 'processing' ? (
                            <Link
                              to={`/processing/${item.analysis_id}`}
                              className="px-2.5 py-1 rounded bg-[#F4B860]/15 text-[#F4B860]"
                            >
                              Progress
                            </Link>
                          ) : null}
                          <button
                            type="button"
                            onClick={() => handleDelete(item.analysis_id)}
                            className="p-1.5 rounded bg-[#111821] border border-white/10 text-[#98A5B5] hover:text-[#F16D73]"
                            title="Delete assessment"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {/* Available Movement Modules */}
        <section className="space-y-3">
          <h3 className="text-sm font-semibold text-[#F4F7FA]">Movement Analysis Modules</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {movements.map((mv) => (
              <Link
                key={mv.id}
                to={`/new?movement=${mv.id}`}
                className="bg-[#161F2B] border border-white/10 hover:border-[#36D6A0]/50 rounded-xl p-4 flex flex-col justify-between gap-3 transition-colors group"
              >
                <div className="space-y-2">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-semibold text-[#F4F7FA] group-hover:text-[#36D6A0] transition-colors">
                      {mv.name}
                    </span>
                    <span
                      className={`text-[10px] font-mono uppercase px-2 py-0.5 rounded ${
                        mv.status === 'experimental'
                          ? 'bg-[#F4B860]/15 text-[#F4B860]'
                          : 'bg-[#36D6A0]/15 text-[#36D6A0]'
                      }`}
                    >
                      {mv.status}
                    </span>
                  </div>
                  <p className="text-xs text-[#98A5B5] leading-relaxed">{mv.short_description}</p>
                </div>
                <div className="flex items-center justify-between text-[11px] font-mono text-[#98A5B5] pt-2 border-t border-white/6">
                  <span>Rec. view: {mv.recommended_perspective.toUpperCase()}</span>
                  <ArrowRight className="w-3.5 h-3.5 text-[#36D6A0]" />
                </div>
              </Link>
            ))}
          </div>
        </section>

        {/* Workflow Summary */}
        <section className="space-y-3">
          <h3 className="text-sm font-semibold text-[#F4F7FA]">Analytical Pipeline Architecture</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {workflowSteps.map((step) => (
              <div key={step.title} className="bg-[#111821] border border-white/8 rounded-xl p-4 space-y-2">
                <div className="flex items-center gap-2">
                  {step.icon}
                  <span className="text-xs font-semibold text-[#F4F7FA]">{step.title}</span>
                </div>
                <p className="text-xs text-[#98A5B5] leading-relaxed">{step.desc}</p>
              </div>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
};
