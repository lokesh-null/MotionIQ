import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { AlertCircle, CheckCircle2, Play, SlidersHorizontal } from 'lucide-react';
import { Header } from '../components/Header';
import { UploadZone } from '../components/UploadZone';
import {
  DEFAULT_GUIDELINES,
  DEFAULT_MOVEMENTS,
  DEFAULT_SAMPLES,
  fetchMovementsAndGuidelines,
  fetchSamples,
  startAnalysisProcess,
  uploadSampleVideo,
  uploadVideoFile,
} from '../services/api';
import type {
  CameraPerspective,
  MovementInfo,
  MovementType,
  RecordingGuidelines,
  SampleVideoItem,
  UploadResponse,
} from '../types/biomechanics';

export const NewAnalysis: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const initialMv = (searchParams.get('movement') as MovementType) || 'squat';

  const [movements, setMovements] = useState<MovementInfo[]>(DEFAULT_MOVEMENTS);
  const [guidelines, setGuidelines] = useState<Record<CameraPerspective, RecordingGuidelines>>(DEFAULT_GUIDELINES);
  const [samples, setSamples] = useState<SampleVideoItem[]>(DEFAULT_SAMPLES);

  const [movementType, setMovementType] = useState<MovementType>(initialMv);
  const [perspective, setPerspective] = useState<CameraPerspective>(
    initialMv === 'jumping_jack' ? 'front' : 'side'
  );
  const [confidenceThreshold, setConfidenceThreshold] = useState<number>(0.5);

  const [uploading, setUploading] = useState(false);
  const [starting, setStarting] = useState(false);
  const [uploadedInfo, setUploadedInfo] = useState<UploadResponse | null>(null);
  const [localPreviewUrl, setLocalPreviewUrl] = useState<string | null>(null);
  const [isBlobUrl, setIsBlobUrl] = useState(false);
  const [activeSampleTitle, setActiveSampleTitle] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([fetchMovementsAndGuidelines(), fetchSamples()])
      .then(([mvRes, smpRes]) => {
        if (mvRes.movements?.length) setMovements(mvRes.movements);
        if (mvRes.guidelines) setGuidelines(mvRes.guidelines);
        if (smpRes?.length) setSamples(smpRes);
      })
      .catch(() => {
        // Keep instant built-in defaults
      });
  }, []);

  useEffect(() => {
    return () => {
      if (localPreviewUrl && isBlobUrl) URL.revokeObjectURL(localPreviewUrl);
    };
  }, [localPreviewUrl, isBlobUrl]);

  const handleMovementChange = (mv: MovementType) => {
    setMovementType(mv);
    const info = movements.find((m) => m.id === mv);
    if (info) {
      setPerspective(info.recommended_perspective);
    }
  };

  const handleFileSelected = async (file: File) => {
    setError(null);
    setUploading(true);
    setActiveSampleTitle(file.name);
    if (localPreviewUrl && isBlobUrl) URL.revokeObjectURL(localPreviewUrl);
    const objUrl = URL.createObjectURL(file);
    setLocalPreviewUrl(objUrl);
    setIsBlobUrl(true);

    try {
      const res = await uploadVideoFile(file, movementType, perspective);
      setUploadedInfo(res);
    } catch (e) {
      setUploadedInfo(null);
      setError(e instanceof Error ? e.message : 'Upload validation failed.');
    } finally {
      setUploading(false);
    }
  };

  const handleSampleSelected = async (sample: SampleVideoItem) => {
    setError(null);
    setUploading(true);
    setUploadedInfo(null);
    setActiveSampleTitle(sample.title);
    if (localPreviewUrl && isBlobUrl) {
      URL.revokeObjectURL(localPreviewUrl);
    }
    // Immediate static CDN preview so video plays right away on any laptop or mobile browser
    setLocalPreviewUrl(`/samples/${sample.filename}`);
    setIsBlobUrl(false);
    setMovementType(sample.movement_type);
    setPerspective(sample.camera_perspective);

    try {
      const res = await uploadSampleVideo(
        sample.id,
        sample.movement_type,
        sample.camera_perspective,
        sample.filename
      );
      setUploadedInfo(res);
    } catch (e) {
      setUploadedInfo(null);
      setError(
        e instanceof Error
          ? e.message
          : 'Failed to prepare sample video on backend. If the cloud server was asleep, please tap the sample once more.'
      );
    } finally {
      setUploading(false);
    }
  };

  const handleStartAnalysis = async () => {
    if (!uploadedInfo) return;
    setError(null);
    setStarting(true);
    try {
      await startAnalysisProcess({
        analysis_id: uploadedInfo.analysis_id,
        movement_type: movementType,
        camera_perspective: perspective,
        confidence_threshold: confidenceThreshold,
      });
      navigate(`/processing/${uploadedInfo.analysis_id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to start analysis.');
      setStarting(false);
    }
  };

  const currentGuideline = guidelines?.[perspective];

  return (
    <div className="flex-1 flex flex-col min-w-0">
      <Header
        title="New Biomechanical Analysis"
        subtitle="Select movement module, choose a built-in sample or upload video, and run analysis"
      />

      <main className="p-4 md:p-6 max-w-6xl w-full mx-auto grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Config + Upload */}
        <div className="lg:col-span-7 space-y-6">
          {/* 1. Movement Module Selector */}
          <section className="bg-[#161F2B] border border-white/10 rounded-xl p-4 md:p-5 space-y-3">
            <h2 className="text-sm font-semibold text-[#F4F7FA]">1. Select Movement Module</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
              {movements.map((mv) => {
                const active = movementType === mv.id;
                return (
                  <button
                    key={mv.id}
                    type="button"
                    onClick={() => handleMovementChange(mv.id)}
                    className={`text-left p-3 rounded-lg border transition-colors ${
                      active
                        ? 'bg-[#36D6A0]/12 border-[#36D6A0]/60'
                        : 'bg-[#111821] border-white/8 hover:border-white/20'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs font-semibold text-[#F4F7FA]">{mv.name}</span>
                      <span
                        className={`text-[10px] font-mono uppercase px-1.5 py-0.5 rounded ${
                          mv.status === 'experimental'
                            ? 'bg-[#F4B860]/15 text-[#F4B860]'
                            : 'bg-[#36D6A0]/15 text-[#36D6A0]'
                        }`}
                      >
                        {mv.status}
                      </span>
                    </div>
                    <p className="text-[11px] text-[#98A5B5] mt-1">{mv.short_description}</p>
                  </button>
                );
              })}
            </div>
          </section>

          {/* 2. Camera Perspective & Confidence */}
          <section className="bg-[#161F2B] border border-white/10 rounded-xl p-4 md:p-5 space-y-4">
            <h2 className="text-sm font-semibold text-[#F4F7FA]">2. Camera Perspective & Landmark Threshold</h2>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {(['side', 'front'] as CameraPerspective[]).map((p) => {
                const active = perspective === p;
                const recommended = movements.find((m) => m.id === movementType)?.recommended_perspective === p;
                const unsupported = movementType === 'jumping_jack' && p === 'side';
                return (
                  <button
                    key={p}
                    type="button"
                    onClick={() => setPerspective(p)}
                    className={`p-3 rounded-lg border text-left transition-colors ${
                      active
                        ? 'bg-[#36D6A0]/12 border-[#36D6A0]/60'
                        : 'bg-[#111821] border-white/8 hover:border-white/20'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold text-[#F4F7FA] capitalize">{p} View</span>
                      {recommended && (
                        <span className="text-[10px] font-mono text-[#36D6A0] bg-[#36D6A0]/15 px-1.5 py-0.5 rounded">
                          RECOMMENDED
                        </span>
                      )}
                      {unsupported && (
                        <span className="text-[10px] font-mono text-[#F4B860] bg-[#F4B860]/15 px-1.5 py-0.5 rounded">
                          LIMITED
                        </span>
                      )}
                    </div>
                    <p className="text-[11px] text-[#98A5B5] mt-1">
                      {p === 'side'
                        ? 'Perpendicular sagittal plane for flexion angles, depth, and trunk lean.'
                        : 'Facing camera for left-right alignment and bilateral abduction.'}
                    </p>
                  </button>
                );
              })}
            </div>

            {movementType === 'jumping_jack' && perspective === 'side' && (
              <div className="bg-[#F4B860]/10 border border-[#F4B860]/40 rounded-lg p-3 text-xs text-[#F4B860] flex items-start gap-2">
                <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                <span>Jumping jacks occur in the frontal plane; a frontal camera view is strongly recommended.</span>
              </div>
            )}

            <div className="bg-[#111821] border border-white/6 rounded-lg p-3 space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="flex items-center gap-2 text-[#F4F7FA] font-medium">
                  <SlidersHorizontal className="w-3.5 h-3.5 text-[#36D6A0]" />
                  Minimum Landmark Confidence Threshold
                </span>
                <span className="font-mono text-[#36D6A0]">{confidenceThreshold.toFixed(2)}</span>
              </div>
              <input
                type="range"
                min={0.3}
                max={0.8}
                step={0.05}
                value={confidenceThreshold}
                onChange={(e) => setConfidenceThreshold(parseFloat(e.target.value))}
                className="w-full accent-[#36D6A0]"
              />
              <p className="text-[11px] text-[#98A5B5]">
                Landmarks below this confidence threshold are masked out and never used in joint-angle calculations.
              </p>
            </div>
          </section>

          {/* 3. Upload & Preview */}
          <section className="bg-[#161F2B] border border-white/10 rounded-xl p-4 md:p-5 space-y-4">
            <h2 className="text-sm font-semibold text-[#F4F7FA]">3. Choose Sample or Upload Video</h2>
            <UploadZone
              selectedMovement={movementType}
              onFileSelected={handleFileSelected}
              onSampleSelected={handleSampleSelected}
              samples={samples}
              uploading={uploading}
              uploadedInfo={uploadedInfo}
              localPreviewUrl={localPreviewUrl}
              activeSampleTitle={activeSampleTitle}
              error={error}
            />

            <div className="pt-2 flex justify-end">
              <button
                type="button"
                disabled={!uploadedInfo || uploading || starting}
                onClick={handleStartAnalysis}
                className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-lg bg-[#36D6A0] text-[#0B0F14] text-sm font-semibold hover:bg-[#2ec290] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                <Play className="w-4 h-4" />
                <span>{starting ? 'Starting Pipeline...' : 'Start Biomechanical Analysis'}</span>
              </button>
            </div>
          </section>
        </div>

        {/* Right Column: Recording Guidelines */}
        <aside className="lg:col-span-5 space-y-4">
          {currentGuideline && (
            <div className="bg-[#161F2B] border border-white/10 rounded-xl p-4 md:p-5 space-y-4 lg:sticky lg:top-24">
              <div>
                <div className="text-[11px] font-mono uppercase tracking-wider text-[#36D6A0]">
                  Recording Guidelines
                </div>
                <h3 className="text-sm font-semibold text-[#F4F7FA] mt-1">{currentGuideline.title}</h3>
              </div>

              <div className="space-y-2">
                <div className="text-xs font-medium text-[#F4F7FA]">Setup Checklist</div>
                <ul className="space-y-2">
                  {currentGuideline.checklist.map((item, i) => (
                    <li key={i} className="text-xs text-[#98A5B5] flex items-start gap-2">
                      <CheckCircle2 className="w-3.5 h-3.5 text-[#36D6A0] shrink-0 mt-0.5" />
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="pt-3 border-t border-white/8 space-y-2">
                <div className="text-xs font-medium text-[#F4F7FA]">Measurable Kinematics from This Angle</div>
                <div className="flex flex-wrap gap-1.5">
                  {currentGuideline.suitable_for.map((tag, i) => (
                    <span
                      key={i}
                      className="text-[11px] px-2.5 py-1 rounded bg-[#111821] border border-white/8 text-[#98A5B5]"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              </div>

              <div className="bg-[#0B0F14] border border-white/6 rounded-lg p-3 text-[11px] text-[#98A5B5] leading-relaxed">
                <span className="text-[#F4F7FA] font-semibold block mb-1">2D Monocular Perspective Note</span>
                MotionIQ evaluates projected 2D kinematics and automatically checks body proportions to flag camera
                angle mismatches or occluded joints rather than guessing out-of-plane 3D angles.
              </div>
            </div>
          )}
        </aside>
      </main>
    </div>
  );
};
