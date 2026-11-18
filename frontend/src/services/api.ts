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

const API_BASE = (import.meta.env.VITE_API_BASE_URL || '').trim().replace(/\/+$/, '');

export const DEFAULT_MOVEMENTS: MovementInfo[] = [
  {
    id: 'squat',
    name: 'Squat Analysis',
    short_description:
      'Sagittal knee/hip flexion, trunk inclination, squat depth, repetition timing, and symmetry indicators.',
    recommended_perspective: 'side',
    supported_perspectives: ['side', 'front'],
    status: 'primary',
  },
  {
    id: 'lunge',
    name: 'Lunge Analysis',
    short_description:
      'Front and rear knee flexion, hip alignment, trunk control, phase timing, and range of motion.',
    recommended_perspective: 'side',
    supported_perspectives: ['side', 'front'],
    status: 'core',
  },
  {
    id: 'jumping_jack',
    name: 'Jumping Jack Analysis',
    short_description:
      'Bilateral shoulder abduction, arm elevation, lower-limb abduction, and left-right coordination.',
    recommended_perspective: 'front',
    supported_perspectives: ['front'],
    status: 'core',
  },
  {
    id: 'basketball_shooting',
    name: 'Basketball Shooting Analysis',
    short_description:
      'Experimental kinematic tracking of shooting-arm elbow/shoulder angles, arm elevation, and release posture.',
    recommended_perspective: 'side',
    supported_perspectives: ['side', 'front'],
    status: 'experimental',
  },
];

export const DEFAULT_GUIDELINES: Record<CameraPerspective, RecordingGuidelines> = {
  side: {
    title: 'Side-View Recording (Sagittal Plane)',
    checklist: [
      'Keep the entire body (head to feet) visible inside the frame throughout the exercise.',
      'Position the camera approximately perpendicular (90 deg) to your movement direction.',
      'Mount the camera on a tripod or stable stationary surface at hip/waist height.',
      'Ensure even lighting with clear contrast between clothing and background.',
      'Avoid baggy clothing that obscures knee, hip, or ankle landmarks.',
    ],
    suitable_for: [
      'Sagittal-plane joint kinematics',
      'Squat depth & knee flexion',
      'Hip flexion & trunk inclination',
      'Lunge front/rear knee flexion',
      'Shooting-arm elbow/shoulder trajectory',
    ],
  },
  front: {
    title: 'Frontal Recording (Coronal Plane)',
    checklist: [
      'Face the camera directly so both left and right limbs remain unobstructed.',
      'Ensure adequate distance so overhead arm reaches (e.g., jumping jacks) remain inside frame.',
      'Mount the camera level and stationary to minimize perspective distortion.',
      'Ensure uniform lighting and minimal background clutter or bystanders.',
    ],
    suitable_for: [
      'Observable left-right alignment indicators',
      'Bilateral shoulder abduction & jumping jacks',
      'Movement symmetry comparisons',
      'Lower-limb lateral spread tracking',
    ],
  },
};

export const DEFAULT_SAMPLES: SampleVideoItem[] = [
  {
    id: 'squat_side_1',
    filename: 'squat_side_1.mp4',
    title: 'Bodyweight Squats — Side View',
    movement_type: 'squat',
    camera_perspective: 'side',
    description:
      'Real human side-view squat recording suitable for sagittal-plane knee flexion, hip angle, depth, and trunk inclination analysis.',
    file_size_bytes: 2024448,
  },
  {
    id: 'squat_front_1',
    filename: 'squat_front_1.mp4',
    title: 'Squats — Frontal View',
    movement_type: 'squat',
    camera_perspective: 'front',
    description:
      'Frontal-view squat recording used for bilateral knee symmetry indicators and frontal tracking evaluation.',
    file_size_bytes: 658636,
  },
  {
    id: 'squat_side_2',
    filename: 'squat_side_2.mp4',
    title: 'Bodyweight Squats — Frontal Demo',
    movement_type: 'squat',
    camera_perspective: 'front',
    description: 'Additional real human frontal-view squat demonstration recording.',
    file_size_bytes: 1552486,
  },
  {
    id: 'lunge_side_1',
    filename: 'lunge_side_1.mp4',
    title: 'Forward Lunges — Side View',
    movement_type: 'lunge',
    camera_perspective: 'side',
    description: 'Real human lunge recording capturing front and rear knee flexion and trunk inclination.',
    file_size_bytes: 2059571,
  },
  {
    id: 'jumping_jacks_front_1',
    filename: 'jumping_jacks_front_1.mp4',
    title: 'Jumping Jacks — Frontal View',
    movement_type: 'jumping_jack',
    camera_perspective: 'front',
    description: 'Frontal-view jumping jack recording for bilateral arm elevation and lower-limb abduction symmetry.',
    file_size_bytes: 401408,
  },
  {
    id: 'basketball_shot_side_1',
    filename: 'bball_jumpshot.mp4',
    title: 'Basketball Jump Shot — Side View',
    movement_type: 'basketball_shooting',
    camera_perspective: 'side',
    description:
      'Experimental basketball jump-shot recording for shooting-arm elbow/shoulder kinematics and release posture.',
    file_size_bytes: 464179,
  },
];

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

async function fetchWithRetry(
  url: string,
  options?: RequestInit,
  retries = 3,
  delayMs = 2500
): Promise<Response> {
  let lastErr: unknown;
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const res = await fetch(url, options);
      if (res.status === 502 || res.status === 503 || res.status === 504) {
        throw new Error(`Backend waking up (HTTP ${res.status})`);
      }
      return res;
    } catch (err) {
      lastErr = err;
      if (attempt < retries) {
        await new Promise((r) => setTimeout(r, delayMs));
      }
    }
  }
  throw lastErr instanceof Error ? lastErr : new Error('Unable to reach backend server.');
}

export function pingBackend(): void {
  fetch(`${API_BASE}/api/health`).catch(() => undefined);
}

export async function fetchMovementsAndGuidelines(): Promise<{
  movements: MovementInfo[];
  guidelines: Record<CameraPerspective, RecordingGuidelines>;
}> {
  try {
    const res = await fetch(`${API_BASE}/api/analysis/movements`);
    if (res.ok) {
      return (await res.json()) as {
        movements: MovementInfo[];
        guidelines: Record<CameraPerspective, RecordingGuidelines>;
      };
    }
  } catch {
    // Fallback to built-in catalog while cloud backend wakes up
  }
  return { movements: DEFAULT_MOVEMENTS, guidelines: DEFAULT_GUIDELINES };
}

export async function fetchSamples(): Promise<SampleVideoItem[]> {
  try {
    const res = await fetch(`${API_BASE}/api/analysis/samples`);
    if (res.ok) {
      const list = (await res.json()) as SampleVideoItem[];
      if (Array.isArray(list) && list.length > 0) return list;
    }
  } catch {
    // Fallback to built-in sample list
  }
  return DEFAULT_SAMPLES;
}

export async function fetchAnalyses(): Promise<AnalysisListItem[]> {
  try {
    const res = await fetchWithRetry(`${API_BASE}/api/analysis`, undefined, 1, 1500);
    return await handleResponse<AnalysisListItem[]>(res);
  } catch {
    return [];
  }
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
  const res = await fetchWithRetry(
    `${API_BASE}/api/analysis/upload`,
    {
      method: 'POST',
      body: form,
    },
    3,
    3000
  );
  return handleResponse(res);
}

export async function uploadSampleVideo(
  sampleId: string,
  movementType: MovementType,
  cameraPerspective: CameraPerspective,
  sampleFilename?: string
): Promise<UploadResponse> {
  try {
    const res = await fetchWithRetry(
      `${API_BASE}/api/analysis/upload-sample`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sample_id: sampleId,
          movement_type: movementType,
          camera_perspective: cameraPerspective,
        }),
      },
      2,
      2500
    );
    if (res.ok) {
      return (await res.json()) as UploadResponse;
    }
  } catch {
    // Fall back to uploading the static CDN sample file directly
  }

  // Fallback: fetch static sample from Vercel /samples/<filename> and upload as a standard File
  const fallbackName =
    sampleFilename || DEFAULT_SAMPLES.find((s) => s.id === sampleId)?.filename || 'squat_side_1.mp4';
  const assetRes = await fetch(`/samples/${fallbackName}`);
  if (!assetRes.ok) {
    throw new Error('Could not load sample video from server or static assets.');
  }
  const blob = await assetRes.blob();
  const file = new File([blob], fallbackName, { type: 'video/mp4' });
  return uploadVideoFile(file, movementType, cameraPerspective);
}

export async function startAnalysisProcess(params: {
  analysis_id: string;
  movement_type: MovementType;
  camera_perspective: CameraPerspective;
  confidence_threshold: number;
  criteria_overrides?: Record<string, number>;
}): Promise<AnalysisStatusResponse> {
  const res = await fetchWithRetry(
    `${API_BASE}/api/analysis/process`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    },
    3,
    2500
  );
  return handleResponse(res);
}

export async function fetchAnalysisStatus(analysisId: string): Promise<AnalysisStatusResponse> {
  const res = await fetchWithRetry(`${API_BASE}/api/analysis/${analysisId}`, undefined, 2, 1500);
  return handleResponse(res);
}

export async function fetchAnalysisResults(analysisId: string): Promise<AnalysisResults> {
  const res = await fetchWithRetry(`${API_BASE}/api/analysis/${analysisId}/results`, undefined, 2, 1500);
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
