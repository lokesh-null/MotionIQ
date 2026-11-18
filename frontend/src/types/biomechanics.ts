export type MovementType = 'squat' | 'lunge' | 'jumping_jack' | 'basketball_shooting';
export type CameraPerspective = 'side' | 'front';
export type AssessmentStatus = 'GOOD' | 'NEEDS IMPROVEMENT' | 'OUTSIDE REFERENCE RANGE' | 'INSUFFICIENT DATA';

export interface MovementInfo {
  id: MovementType;
  name: string;
  short_description: string;
  recommended_perspective: CameraPerspective;
  supported_perspectives: CameraPerspective[];
  status: 'primary' | 'core' | 'experimental';
}

export interface RecordingGuidelines {
  title: string;
  checklist: string[];
  suitable_for: string[];
}

export interface SampleVideoItem {
  id: string;
  filename: string;
  title: string;
  movement_type: MovementType;
  camera_perspective: CameraPerspective;
  description: string;
  file_size_bytes: number;
}

export interface VideoValidationResult {
  valid: boolean;
  errors: string[];
  warnings: string[];
  metadata: {
    filename?: string;
    extension?: string;
    file_size_bytes?: number;
    width?: number;
    height?: number;
    fps?: number;
    frame_count?: number;
    duration_sec?: number;
  };
}

export interface UploadResponse {
  analysis_id: string;
  filename: string;
  movement_type: MovementType;
  camera_perspective: CameraPerspective;
  validation: VideoValidationResult;
}

export interface AnalysisStatusResponse {
  analysis_id: string;
  status: 'uploaded' | 'queued' | 'processing' | 'completed' | 'failed';
  stage: string;
  frames_processed: number;
  total_frames: number;
  progress_percent: number;
  current_operation: string;
  movement_type: MovementType;
  camera_perspective: CameraPerspective;
  filename: string;
  created_at: string;
  completed_at: string | null;
  error_message: string | null;
  has_video: boolean;
  has_report: boolean;
}

export interface AnalysisListItem {
  analysis_id: string;
  status: string;
  movement_type: MovementType;
  camera_perspective: CameraPerspective;
  filename: string;
  created_at: string;
  completed_at: string | null;
  rep_count: number | null;
  composite_score: number | null;
  quality_status: string | null;
}

export interface JointSummary {
  label: string;
  convention_key: string;
  definition: string;
  landmarks: string;
  valid_frames: number;
  total_frames: number;
  valid_ratio: number;
  mean_confidence: number;
  sufficient_data: boolean;
  mean_deg: number | null;
  min_deg: number | null;
  max_deg: number | null;
  std_deg: number | null;
  rom_deg: number | null;
  peak_angular_velocity_deg_s: number | null;
}

export interface SymmetryInfo {
  joint: string;
  is_valid_comparison: boolean;
  paired_frames: number;
  paired_ratio: number;
  mean_abs_diff_deg: number | null;
  max_abs_diff_deg: number | null;
  correlation: number | null;
  difference_series_deg: (number | null)[];
  reason: string;
}

export interface RepetitionDetail {
  rep_number: number;
  start_frame: number;
  bottom_frame?: number;
  peak_frame?: number;
  release_frame?: number;
  end_frame: number;
  start_time_sec: number;
  bottom_time_sec?: number;
  peak_time_sec?: number;
  release_time_sec?: number;
  end_time_sec: number;
  duration_sec: number;
  descent_duration_sec?: number;
  bottom_hold_sec?: number;
  ascent_duration_sec?: number;
  descent_ascent_ratio?: number | null;
  max_knee_flexion_deg?: number | null;
  min_knee_internal_deg?: number | null;
  max_hip_flexion_deg?: number | null;
  max_trunk_inclination_deg?: number | null;
  trunk_inclination_delta_deg?: number | null;
  hip_depth_ratio_at_bottom?: number | null;
  bilateral_knee_diff_at_bottom_deg?: number | null;
  front_leg?: string;
  front_knee_max_flexion_deg?: number | null;
  rear_knee_max_flexion_deg?: number | null;
  front_knee_rom_deg?: number | null;
  max_left_shoulder_deg?: number | null;
  max_right_shoulder_deg?: number | null;
  max_mean_shoulder_deg?: number | null;
  shoulder_peak_diff_deg?: number | null;
  hip_abduction_rom_deg?: number | null;
  max_ankle_spread_ratio?: number | null;
  max_arm_elevation_ratio?: number | null;
  shooting_arm?: string;
  elbow_angle_at_dip_deg?: number | null;
  elbow_angle_at_release_deg?: number | null;
  shoulder_angle_at_release_deg?: number | null;
  trunk_inclination_at_release_deg?: number | null;
  peak_arm_elevation_ratio?: number | null;
  peak_elbow_extension_vel_deg_s?: number | null;
  normalized_primary_curve: (number | null)[];
}

export interface AssessmentParameter {
  parameter_name: string;
  measured_value: number | null;
  unit: string;
  reference_range: string;
  criteria_source: string;
  status: AssessmentStatus;
  explanation: string;
  confidence: number;
  weight: number;
  recommendation: string | null;
}

export interface AnalysisResults {
  analysis_id: string;
  movement_type: MovementType;
  movement_label: string;
  completed_at: string;
  video_metadata: {
    filename: string;
    extension: string;
    file_size_bytes: number;
    width: number;
    height: number;
    fps: number;
    frame_count: number;
    duration_sec: number;
  };
  processing_details: {
    model_used: string;
    confidence_threshold: number;
    source_fps: number;
    effective_fps: number;
    sample_stride: number;
    processed_width: number;
    processed_height: number;
    processing_time_sec: number;
  };
  data_quality: {
    total_frames: number;
    frames_processed: number;
    pose_detected_frames: number;
    valid_landmark_frames: number;
    valid_frame_ratio: number;
    full_body_visible_ratio: number;
    mean_landmark_confidence: number;
    multi_person_frames: number;
    multi_person_detected: boolean;
    inferred_perspective: string;
    selected_perspective: CameraPerspective;
    perspective_compatible: boolean;
    camera_stability_score: number;
    quality_status: 'GOOD' | 'LIMITED' | 'INSUFFICIENT';
    landmark_visibility: Record<string, { mean_confidence: number; reliable_ratio: number }>;
    warnings: string[];
    camera_limitations: string[];
  };
  biomechanics: {
    timestamps_sec: number[];
    angles_deg: Record<string, (number | null)[]>;
    angular_velocities_deg_s: Record<string, (number | null)[]>;
    joint_summaries: Record<string, JointSummary>;
    kinematic_ratios: Record<string, (number | null)[]>;
    trajectories: Record<string, { t: number; x: number | null; y: number | null }[]>;
    symmetry: Record<string, SymmetryInfo>;
    angle_conventions: Record<string, Record<string, string>>;
  };
  movement_analysis: {
    movement_type: MovementType;
    experimental?: boolean;
    primary_side_tracked: string;
    primary_signal_label: string;
    primary_signal_deg: (number | null)[];
    rep_count: number;
    total_movement_duration_sec: number;
    standing_trunk_baseline_deg?: number | null;
    lead_side_knee_diff_deg?: number | null;
    ball_velocity_disclaimer?: string;
    frame_phases: string[];
    repetitions: RepetitionDetail[];
    consistency: Record<string, { mean: number | null; std: number | null; min: number | null; max: number | null; cv_percent: number | null } | boolean>;
    summary_metrics: Record<string, number | boolean | null>;
  };
  assessment: {
    parameters: AssessmentParameter[];
    positive_observations: string[];
    areas_for_improvement: string[];
    technique_adjustments: { parameter: string; status: string; suggestion: string }[];
    composite_score: number | null;
    composite_status: AssessmentStatus;
    composite_methodology: {
      computed: boolean;
      composite_score: number | null;
      composite_status: AssessmentStatus;
      valid_weight_coverage: number;
      minimum_coverage_required: number;
      included_parameters: { name: string; weight: number; status: string }[];
      excluded_parameters: { name: string; weight: number; reason: string }[];
      normalization_method: string;
      missing_data_handling: string;
    };
    prototype_disclaimer: string;
  };
}
