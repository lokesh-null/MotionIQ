import React, { useMemo, useState } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Info } from 'lucide-react';
import type { AnalysisResults } from '../types/biomechanics';

interface PerformanceChartProps {
  results: AnalysisResults;
}

const CHART_COLORS = ['#36D6A0', '#60A5FA', '#F4B860', '#F16D73', '#A78BFA'];

const PHASE_PALETTE: Record<string, string> = {
  STANDING: '#475569',
  STARTING_POSITION: '#475569',
  INITIAL_STANDING: '#475569',
  PREPARATION: '#475569',
  PREPARATION_DIP: '#F4B860',
  DESCENDING: '#F4B860',
  DESCENT: '#F4B860',
  OUTWARD_MOVEMENT: '#F4B860',
  UPWARD_EXTENSION: '#F4B860',
  BOTTOM: '#36D6A0',
  MAXIMUM_EXTENSION: '#36D6A0',
  RELEASE_POINT: '#36D6A0',
  ASCENDING: '#60A5FA',
  ASCENT: '#60A5FA',
  RETURN_MOVEMENT: '#60A5FA',
  FOLLOW_THROUGH: '#60A5FA',
  RETURN_TO_STANDING: '#36D6A0',
};

export const PerformanceChart: React.FC<PerformanceChartProps> = ({ results }) => {
  const [activeTab, setActiveTab] = useState<'angles' | 'velocity' | 'reps' | 'symmetry' | 'trajectory'>('angles');

  const bio = results.biomechanics;
  const movement = results.movement_analysis;
  const timestamps = bio.timestamps_sec || [];

  // Select clean angle keys (avoid plotting redundant left+right+internal+flexion all at once)
  const angleKeys = useMemo(() => {
    const allKeys = Object.keys(bio.angles_deg || {}).filter((k) =>
      (bio.angles_deg[k] || []).some((v) => v !== null)
    );
    const preferred =
      results.movement_type === 'squat' || results.movement_type === 'lunge'
        ? ['left_knee_flexion', 'right_knee_flexion', 'left_hip_flexion', 'right_hip_flexion', 'trunk_inclination']
        : results.movement_type === 'jumping_jack'
        ? ['left_shoulder_angle', 'right_shoulder_angle', 'left_hip_internal', 'right_hip_internal']
        : ['right_elbow_internal', 'left_elbow_internal', 'right_shoulder_angle', 'trunk_inclination'];
    const filtered = preferred.filter((k) => allKeys.includes(k));
    return filtered.length > 0 ? filtered : allKeys.slice(0, 4);
  }, [bio.angles_deg, results.movement_type]);

  const timeSeriesData = useMemo(() => {
    return timestamps.map((t, idx) => {
      const row: Record<string, number | string | null> = { t: Number(t.toFixed(2)) };
      for (const k of angleKeys) {
        row[k] = bio.angles_deg[k]?.[idx] ?? null;
        row[`vel_${k}`] = bio.angular_velocities_deg_s[k]?.[idx] ?? null;
      }
      return row;
    });
  }, [timestamps, angleKeys, bio.angles_deg, bio.angular_velocities_deg_s]);

  // Normalized 0..100% repetition cycle overlay data
  const repOverlayData = useMemo(() => {
    const reps = movement.repetitions || [];
    if (reps.length === 0) return [];
    const points = 21;
    const rows: Record<string, number | null>[] = [];
    for (let i = 0; i < points; i++) {
      const row: Record<string, number | null> = { pct: i * 5 };
      reps.slice(0, 8).forEach((r) => {
        row[`Rep_${r.rep_number}`] = r.normalized_primary_curve?.[i] ?? null;
      });
      rows.push(row);
    }
    return rows;
  }, [movement.repetitions]);

  // Per-rep comparison bar chart data
  const repBarData = useMemo(() => {
    return (movement.repetitions || []).map((r) => ({
      rep: `Rep #${r.rep_number}`,
      duration_sec: r.duration_sec,
      peak_deg:
        r.max_knee_flexion_deg ??
        r.front_knee_max_flexion_deg ??
        r.max_mean_shoulder_deg ??
        r.elbow_angle_at_release_deg ??
        null,
    }));
  }, [movement.repetitions]);

  // Symmetry panel selection
  const symmetryEntries = Object.values(bio.symmetry || {});
  const primarySymmetry = symmetryEntries.find((s) => s.is_valid_comparison) || symmetryEntries[0];
  const symData = useMemo(() => {
    if (!primarySymmetry || !primarySymmetry.is_valid_comparison) return [];
    const isShoulder = primarySymmetry.joint.toLowerCase().includes('shoulder');
    const isHip = primarySymmetry.joint.toLowerCase().includes('hip');
    const lKey = isShoulder
      ? 'left_shoulder_angle'
      : isHip
      ? results.movement_type === 'jumping_jack'
        ? 'left_hip_internal'
        : 'left_hip_flexion'
      : 'left_knee_flexion';
    const rKey = lKey.replace('left_', 'right_');
    return timestamps.map((t, i) => ({
      t: Number(t.toFixed(2)),
      Left: bio.angles_deg[lKey]?.[i] ?? null,
      Right: bio.angles_deg[rKey]?.[i] ?? null,
      Diff: primarySymmetry.difference_series_deg?.[i] ?? null,
    }));
  }, [primarySymmetry, timestamps, bio.angles_deg, results.movement_type]);

  // Phase segments for timeline bar
  const phaseSegments = useMemo(() => {
    const phases = movement.frame_phases || [];
    if (phases.length === 0) return [];
    const segs: { phase: string; startIdx: number; endIdx: number; startTime: number; endTime: number }[] = [];
    let cur = phases[0];
    let sIdx = 0;
    for (let i = 1; i < phases.length; i++) {
      if (phases[i] !== cur) {
        segs.push({
          phase: cur,
          startIdx: sIdx,
          endIdx: i - 1,
          startTime: timestamps[sIdx] ?? 0,
          endTime: timestamps[i - 1] ?? 0,
        });
        cur = phases[i];
        sIdx = i;
      }
    }
    segs.push({
      phase: cur,
      startIdx: sIdx,
      endIdx: phases.length - 1,
      startTime: timestamps[sIdx] ?? 0,
      endTime: timestamps[phases.length - 1] ?? 0,
    });
    return segs;
  }, [movement.frame_phases, timestamps]);

  // 2D Trajectory points (normalized X vs inverted Y so vertical up matches screen up)
  const trajKeys = Object.keys(bio.trajectories || {});
  const [selectedTrajKey, setSelectedTrajKey] = useState<string>(trajKeys[0] || '');
  const activeTrajKey = trajKeys.includes(selectedTrajKey) ? selectedTrajKey : trajKeys[0] || '';
  const trajPoints = useMemo(() => {
    if (!activeTrajKey) return [];
    return (bio.trajectories[activeTrajKey] || [])
      .filter((p) => p.x !== null && p.y !== null)
      .map((p) => ({
        x: Number((p.x as number).toFixed(3)),
        y_up: Number((1.0 - (p.y as number)).toFixed(3)),
        t: p.t,
      }));
  }, [activeTrajKey, bio.trajectories]);

  const tabs = [
    { id: 'angles', label: 'Joint Angles vs Time' },
    { id: 'velocity', label: 'Angular Velocity' },
    { id: 'reps', label: 'Repetition Comparison' },
    { id: 'symmetry', label: 'Left-Right Symmetry' },
    { id: 'trajectory', label: 'Phases & Joint Trajectory' },
  ] as const;

  return (
    <div className="bg-[#161F2B] border border-white/10 rounded-xl p-4 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/8 pb-3">
        <div>
          <h3 className="text-sm font-semibold text-[#F4F7FA]">Biomechanical Signal Analysis</h3>
          <p className="text-xs text-[#98A5B5]">All curves plotted directly from processed MediaPipe landmark kinematics</p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                activeTab === tab.id
                  ? 'bg-[#36D6A0] text-[#0B0F14] font-semibold'
                  : 'bg-[#111821] text-[#98A5B5] border border-white/8 hover:text-[#F4F7FA]'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Tab 1: Joint Angles vs Time */}
      {activeTab === 'angles' && (
        <div className="h-80 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={timeSeriesData} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#243142" />
              <XAxis dataKey="t" stroke="#98A5B5" fontSize={11} unit="s" />
              <YAxis stroke="#98A5B5" fontSize={11} unit="°" domain={['auto', 'auto']} />
              <Tooltip
                contentStyle={{ backgroundColor: '#111821', borderColor: '#2A394D', fontSize: '12px', color: '#F4F7FA' }}
              />
              <Legend wrapperStyle={{ fontSize: '11px' }} />
              {angleKeys.map((k, idx) => (
                <Line
                  key={k}
                  type="monotone"
                  dataKey={k}
                  name={bio.joint_summaries[k]?.label || k}
                  stroke={CHART_COLORS[idx % CHART_COLORS.length]}
                  strokeWidth={2}
                  dot={false}
                  connectNulls={false}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Tab 2: Angular Velocity vs Time */}
      {activeTab === 'velocity' && (
        <div className="h-80 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={timeSeriesData} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#243142" />
              <XAxis dataKey="t" stroke="#98A5B5" fontSize={11} unit="s" />
              <YAxis stroke="#98A5B5" fontSize={11} unit="°/s" />
              <ReferenceLine y={0} stroke="#475569" strokeDasharray="3 3" />
              <Tooltip
                contentStyle={{ backgroundColor: '#111821', borderColor: '#2A394D', fontSize: '12px', color: '#F4F7FA' }}
              />
              <Legend wrapperStyle={{ fontSize: '11px' }} />
              {angleKeys.slice(0, 3).map((k, idx) => (
                <Line
                  key={k}
                  type="monotone"
                  dataKey={`vel_${k}`}
                  name={`${bio.joint_summaries[k]?.label || k} (°/s)`}
                  stroke={CHART_COLORS[idx % CHART_COLORS.length]}
                  strokeWidth={1.8}
                  dot={false}
                  connectNulls={false}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Tab 3: Repetition Comparison */}
      {activeTab === 'reps' && (
        <div className="space-y-4">
          {movement.repetitions.length === 0 ? (
            <div className="p-8 text-center text-xs text-[#98A5B5] bg-[#111821] rounded-lg border border-white/6">
              No complete repetitions were detected to compare across cycles.
            </div>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <div className="bg-[#111821] p-3 rounded-lg border border-white/6">
                <div className="text-xs font-medium text-[#F4F7FA] mb-2">
                  Normalized Cycle Overlay (0%–100% Rep Progress)
                </div>
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={repOverlayData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#243142" />
                      <XAxis dataKey="pct" stroke="#98A5B5" fontSize={11} unit="%" />
                      <YAxis stroke="#98A5B5" fontSize={11} unit="°" />
                      <Tooltip
                        contentStyle={{ backgroundColor: '#0B0F14', borderColor: '#2A394D', fontSize: '12px' }}
                      />
                      <Legend wrapperStyle={{ fontSize: '11px' }} />
                      {movement.repetitions.slice(0, 8).map((r, idx) => (
                        <Line
                          key={r.rep_number}
                          type="monotone"
                          dataKey={`Rep_${r.rep_number}`}
                          name={`Rep #${r.rep_number}`}
                          stroke={CHART_COLORS[idx % CHART_COLORS.length]}
                          strokeWidth={2}
                          dot={false}
                        />
                      ))}
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>

              <div className="bg-[#111821] p-3 rounded-lg border border-white/6">
                <div className="text-xs font-medium text-[#F4F7FA] mb-2">
                  Peak Angle & Cycle Duration per Repetition
                </div>
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={repBarData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#243142" />
                      <XAxis dataKey="rep" stroke="#98A5B5" fontSize={11} />
                      <YAxis yAxisId="left" stroke="#36D6A0" fontSize={11} unit="°" />
                      <YAxis yAxisId="right" orientation="right" stroke="#60A5FA" fontSize={11} unit="s" />
                      <Tooltip
                        contentStyle={{ backgroundColor: '#0B0F14', borderColor: '#2A394D', fontSize: '12px' }}
                      />
                      <Legend wrapperStyle={{ fontSize: '11px' }} />
                      <Bar yAxisId="left" dataKey="peak_deg" name="Peak Angle (°)" fill="#36D6A0" radius={[4, 4, 0, 0]} />
                      <Bar yAxisId="right" dataKey="duration_sec" name="Duration (s)" fill="#60A5FA" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Tab 4: Left-Right Symmetry */}
      {activeTab === 'symmetry' && (
        <div>
          {!primarySymmetry || !primarySymmetry.is_valid_comparison ? (
            <div className="bg-[#111821] border border-[#F4B860]/30 rounded-lg p-5 flex items-start gap-3 text-xs text-[#F4B860]">
              <Info className="w-5 h-5 shrink-0 mt-0.5" />
              <div className="space-y-1">
                <div className="font-semibold text-[#F4F7FA]">
                  Bilateral Symmetry Chart Withheld — Camera Perspective Constraint
                </div>
                <p className="text-[#98A5B5]">
                  {primarySymmetry?.reason ||
                    'Both left and right landmarks must be simultaneously visible under a compatible frontal view for valid bilateral comparison.'}
                </p>
              </div>
            </div>
          ) : (
            <div className="space-y-3">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs">
                <div className="bg-[#111821] p-3 rounded-lg border border-white/6">
                  <span className="text-[#98A5B5]">Mean Abs Difference: </span>
                  <span className="font-mono font-semibold text-[#F4F7FA]">
                    {primarySymmetry.mean_abs_diff_deg}°
                  </span>
                </div>
                <div className="bg-[#111821] p-3 rounded-lg border border-white/6">
                  <span className="text-[#98A5B5]">Max Abs Difference: </span>
                  <span className="font-mono font-semibold text-[#F4F7FA]">
                    {primarySymmetry.max_abs_diff_deg}°
                  </span>
                </div>
                <div className="bg-[#111821] p-3 rounded-lg border border-white/6">
                  <span className="text-[#98A5B5]">Bilateral Correlation (r): </span>
                  <span className="font-mono font-semibold text-[#36D6A0]">
                    {primarySymmetry.correlation ?? 'N/A'}
                  </span>
                </div>
              </div>
              <div className="h-72 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={symData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#243142" />
                    <XAxis dataKey="t" stroke="#98A5B5" fontSize={11} unit="s" />
                    <YAxis stroke="#98A5B5" fontSize={11} unit="°" />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#111821', borderColor: '#2A394D', fontSize: '12px' }}
                    />
                    <Legend wrapperStyle={{ fontSize: '11px' }} />
                    <Line type="monotone" dataKey="Left" stroke="#36D6A0" strokeWidth={2} dot={false} connectNulls={false} />
                    <Line type="monotone" dataKey="Right" stroke="#60A5FA" strokeWidth={2} dot={false} connectNulls={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Tab 5: Movement Phase Timeline & Joint Trajectory */}
      {activeTab === 'trajectory' && (
        <div className="space-y-4">
          {/* Phase Timeline Strip */}
          <div className="bg-[#111821] p-3.5 rounded-lg border border-white/6 space-y-2">
            <div className="text-xs font-medium text-[#F4F7FA]">Movement-Phase Timeline</div>
            <div className="w-full h-7 rounded overflow-hidden flex border border-white/10">
              {phaseSegments.map((seg, i) => {
                const widthPct = ((seg.endIdx - seg.startIdx + 1) / Math.max(1, timestamps.length)) * 100;
                return (
                  <div
                    key={i}
                    style={{
                      width: `${widthPct}%`,
                      backgroundColor: PHASE_PALETTE[seg.phase] || '#334155',
                    }}
                    title={`${seg.phase}: ${seg.startTime.toFixed(2)}s – ${seg.endTime.toFixed(2)}s`}
                    className="h-full border-r border-[#0B0F14]/40 last:border-r-0"
                  />
                );
              })}
            </div>
            <div className="flex flex-wrap gap-3 text-[11px] text-[#98A5B5] pt-1">
              {Array.from(new Set(movement.frame_phases)).map((ph) => (
                <div key={ph} className="flex items-center gap-1.5">
                  <span
                    className="w-2.5 h-2.5 rounded-sm inline-block"
                    style={{ backgroundColor: PHASE_PALETTE[ph] || '#334155' }}
                  />
                  <span>{ph}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Joint 2D Spatial Trajectory */}
          {trajKeys.length > 0 && (
            <div className="bg-[#111821] p-3.5 rounded-lg border border-white/6 space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="text-xs font-medium text-[#F4F7FA]">
                  2D Normalized Joint Trajectory (Image Plane X vs Height 1−Y)
                </div>
                <select
                  value={activeTrajKey}
                  onChange={(e) => setSelectedTrajKey(e.target.value)}
                  className="bg-[#161F2B] border border-white/12 rounded px-2.5 py-1 text-xs text-[#F4F7FA]"
                >
                  {trajKeys.map((k) => (
                    <option key={k} value={k}>
                      {k.replace('_', ' ')}
                    </option>
                  ))}
                </select>
              </div>
              <div className="h-60">
                <ResponsiveContainer width="100%" height="100%">
                  <ScatterChart margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#243142" />
                    <XAxis type="number" dataKey="x" name="Horizontal X" domain={[0, 1]} stroke="#98A5B5" fontSize={11} />
                    <YAxis type="number" dataKey="y_up" name="Vertical Height" domain={[0, 1]} stroke="#98A5B5" fontSize={11} />
                    <Tooltip
                      cursor={{ strokeDasharray: '3 3' }}
                      contentStyle={{ backgroundColor: '#0B0F14', borderColor: '#2A394D', fontSize: '12px' }}
                    />
                    <Scatter name={activeTrajKey} data={trajPoints} fill="#36D6A0" line={{ stroke: '#36D6A0', strokeWidth: 1.5 }} />
                  </ScatterChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
