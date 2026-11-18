import type {
  AnalysisListItem,
  AnalysisResults,
  AnalysisStatusResponse,
  CameraPerspective,
  MovementInfo,
  MovementType,
  RecordingGuidelines,
  SampleVideoItem,
  UploadResponse,
} from '../types/biomechanics';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const data = await res.json();
      if (data?.detail) {
        detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
      }
    } catch {
      // ignore non-json error body
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export async function fetchMovementsAndGuidelines(): Promise<{
  movements: MovementInfo[];
  guidelines: Record<CameraPerspective, RecordingGuidelines>;
}> {
  const res = await fetch(`${API_BASE}/api/analysis/movements`);
  return handleResponse(res);
}

export async function fetchSamples(): Promise<SampleVideoItem[]> {
  const res = await fetch(`${API_BASE}/api/analysis/samples`);
  return handleResponse(res);
}

export async function fetchAnalyses(): Promise<AnalysisListItem[]> {
  const res = await fetch(`${API_BASE}/api/analysis`);
  return handleResponse(res);
}

export async function uploadVideoFile(
  file: File,
  movementType: MovementType,
  cameraPerspective: CameraPerspective
): Promise<UploadResponse> {
  const form = new FormData();
  form.append('file', file);
  form.append('movement_type', movementType);
  form.append('camera_perspective', cameraPerspective);
  const res = await fetch(`${API_BASE}/api/analysis/upload`, {
    method: 'POST',
    body: form,
  });
  return handleResponse(res);
}

export async function uploadSampleVideo(
  sampleId: string,
  movementType: MovementType,
  cameraPerspective: CameraPerspective
): Promise<UploadResponse> {
  const res = await fetch(`${API_BASE}/api/analysis/upload-sample`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      sample_id: sampleId,
      movement_type: movementType,
      camera_perspective: cameraPerspective,
    }),
  });
  return handleResponse(res);
}

export async function startAnalysisProcess(params: {
  analysis_id: string;
  movement_type: MovementType;
  camera_perspective: CameraPerspective;
  confidence_threshold: number;
  criteria_overrides?: Record<string, number>;
}): Promise<AnalysisStatusResponse> {
  const res = await fetch(`${API_BASE}/api/analysis/process`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  return handleResponse(res);
}

export async function fetchAnalysisStatus(analysisId: string): Promise<AnalysisStatusResponse> {
  const res = await fetch(`${API_BASE}/api/analysis/${analysisId}`);
  return handleResponse(res);
}

export async function fetchAnalysisResults(analysisId: string): Promise<AnalysisResults> {
  const res = await fetch(`${API_BASE}/api/analysis/${analysisId}/results`);
  return handleResponse(res);
}

export async function deleteAnalysis(analysisId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/analysis/${analysisId}`, { method: 'DELETE' });
  await handleResponse(res);
}

export function getRawVideoUrl(analysisId: string): string {
  return `${API_BASE}/api/analysis/${analysisId}/raw-video`;
}

export function getAnnotatedVideoUrl(analysisId: string): string {
  return `${API_BASE}/api/analysis/${analysisId}/video`;
}

export function getReportPdfUrl(analysisId: string): string {
  return `${API_BASE}/api/analysis/${analysisId}/report`;
}
