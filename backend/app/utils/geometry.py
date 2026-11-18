"""Biomechanical 2D geometry utilities and documented joint-angle conventions."""

from __future__ import annotations

import math
from typing import Dict, Optional, Tuple
import numpy as np

Point2D = Tuple[float, float]
NORM_EPS = 1e-6

ANGLE_CONVENTIONS: Dict[str, Dict[str, str]] = {
    "knee_internal": {
        "name": "Knee Internal Angle",
        "landmarks": "Hip (23/24) -> Knee (25/26) -> Ankle (27/28)",
        "definition": "2D sagittal/projected angle at the knee vertex between thigh vector (Hip - Knee) and shank vector (Ankle - Knee).",
        "anatomical_note": "Full standing extension approaches 180 deg; deeper knee bend produces smaller internal angles.",
        "recommended_plane": "Sagittal (side view) for accurate flexion measurement.",
    },
    "knee_flexion": {
        "name": "Knee Flexion Angle",
        "landmarks": "Hip (23/24) -> Knee (25/26) -> Ankle (27/28)",
        "definition": "Supplementary flexion angle computed as max(0, 180 - knee_internal_angle).",
        "anatomical_note": "0 deg represents straight standing extension; 90 deg corresponds to a right-angle bend; >100 deg indicates deep squat flexion.",
        "recommended_plane": "Sagittal (side view).",
    },
    "hip_internal": {
        "name": "Hip Internal (Trunk-Thigh) Angle",
        "landmarks": "Shoulder (11/12) -> Hip (23/24) -> Knee (25/26)",
        "definition": "2D projected angle at the hip vertex between torso vector (Shoulder - Hip) and thigh vector (Knee - Hip).",
        "anatomical_note": "Standing upright approaches 180 deg; hip flexion at squat/lunge bottom reduces the internal angle.",
        "recommended_plane": "Sagittal (side view).",
    },
    "hip_flexion": {
        "name": "Hip Flexion Angle",
        "landmarks": "Shoulder (11/12) -> Hip (23/24) -> Knee (25/26)",
        "definition": "Supplementary hip flexion angle computed as max(0, 180 - hip_internal_angle).",
        "anatomical_note": "0 deg represents neutral upright standing; larger values indicate greater torso-to-thigh closure.",
        "recommended_plane": "Sagittal (side view).",
    },
    "elbow_internal": {
        "name": "Elbow Internal Angle",
        "landmarks": "Shoulder (11/12) -> Elbow (13/14) -> Wrist (15/16)",
        "definition": "2D projected angle at the elbow vertex between upper-arm vector (Shoulder - Elbow) and forearm vector (Wrist - Elbow).",
        "anatomical_note": "Full arm extension approaches 180 deg; flexed arm positions yield smaller internal angles.",
        "recommended_plane": "Sagittal/plane of arm motion.",
    },
    "elbow_flexion": {
        "name": "Elbow Flexion Angle",
        "landmarks": "Shoulder (11/12) -> Elbow (13/14) -> Wrist (15/16)",
        "definition": "Supplementary elbow flexion angle computed as max(0, 180 - elbow_internal_angle).",
        "anatomical_note": "0 deg represents straight arm; ~90 deg represents a right-angle elbow cock.",
        "recommended_plane": "Sagittal/plane of arm motion.",
    },
    "shoulder_angle": {
        "name": "Shoulder Elevation / Abduction Angle",
        "landmarks": "Hip (23/24) -> Shoulder (11/12) -> Elbow (13/14)",
        "definition": "2D projected angle at the shoulder vertex between torso vector (Hip - Shoulder) and upper-arm vector (Elbow - Shoulder).",
        "anatomical_note": "Arms relaxed at sides (~0-20 deg); horizontal arm abduction (~90 deg); overhead elevation (~150-180 deg).",
        "recommended_plane": "Frontal plane for abduction (jumping jacks); sagittal plane for forward flexion (shooting).",
    },
    "trunk_inclination": {
        "name": "Trunk Inclination Angle",
        "landmarks": "Hip (23/24 or mid-hip) -> Shoulder (11/12 or mid-shoulder) vs Vertical Upward Vector (0, -1)",
        "definition": "Angle between the hip-to-shoulder trunk segment and the vertical axis in image pixel space.",
        "anatomical_note": "0 deg denotes an upright vertical torso; larger values indicate forward lean (side view) or lateral lean (front view).",
        "recommended_plane": "Sagittal (side view) for forward lean; frontal (front view) for lateral trunk sway.",
    },
}


def is_valid_point(pt: Optional[Point2D]) -> bool:
    """Return True if point is a finite 2D coordinate tuple."""
    if pt is None or len(pt) != 2:
        return False
    x, y = pt
    return math.isfinite(x) and math.isfinite(y)


def to_pixel_coords(x_norm: float, y_norm: float, width: int, height: int) -> Optional[Point2D]:
    """
    Convert normalized [0, 1] landmark coordinates to aspect-corrected pixel coordinates.

    Scaling by frame width and height prevents aspect-ratio distortion in angle calculations
    on rectangular video frames (e.g., 16:9 or 9:16).
    """
    if width <= 0 or height <= 0:
        return None
    if not (math.isfinite(x_norm) and math.isfinite(y_norm)):
        return None
    return (float(x_norm) * float(width), float(y_norm) * float(height))


def euclidean_distance(a: Optional[Point2D], b: Optional[Point2D]) -> Optional[float]:
    """Compute Euclidean distance between two 2D points with numerical safeguards."""
    if not (is_valid_point(a) and is_valid_point(b)):
        return None
    dx = float(a[0]) - float(b[0])
    dy = float(a[1]) - float(b[1])
    dist = math.hypot(dx, dy)
    return dist if math.isfinite(dist) else None


def calculate_angle_3pt(
    a: Optional[Point2D],
    b: Optional[Point2D],
    c: Optional[Point2D],
) -> Optional[float]:
    """
    Calculate the internal angle (in degrees, [0, 180]) at vertex `b` formed by points a-b-c.

    Uses:
        u = a - b
        v = c - b
        cos(theta) = (u . v) / (|u| * |v|)

    Returns None when any input point is missing, non-finite, or either segment length < 1e-6.
    """
    if not (is_valid_point(a) and is_valid_point(b) and is_valid_point(c)):
        return None

    u = np.array([float(a[0]) - float(b[0]), float(a[1]) - float(b[1])], dtype=np.float64)
    v = np.array([float(c[0]) - float(b[0]), float(c[1]) - float(b[1])], dtype=np.float64)

    norm_u = float(np.linalg.norm(u))
    norm_v = float(np.linalg.norm(v))
    if norm_u < NORM_EPS or norm_v < NORM_EPS:
        return None

    cos_theta = float(np.dot(u, v) / (norm_u * norm_v))
    cos_theta = float(np.clip(cos_theta, -1.0, 1.0))
    angle_deg = math.degrees(math.acos(cos_theta))
    return angle_deg if math.isfinite(angle_deg) else None


def internal_to_flexion_angle(internal_angle: Optional[float]) -> Optional[float]:
    """
    Convert an internal joint angle (where 180 deg = full extension) to flexion angle (0 deg = straight).
    """
    if internal_angle is None or not math.isfinite(internal_angle):
        return None
    return max(0.0, min(180.0, 180.0 - float(internal_angle)))


def calculate_trunk_inclination(
    hip_pt: Optional[Point2D],
    shoulder_pt: Optional[Point2D],
) -> Optional[float]:
    """
    Compute trunk inclination angle (degrees, [0, 180]) relative to the vertical upward axis.

    In image coordinates (+y downward), vertical upward is v_up = (0, -1).
    """
    if not (is_valid_point(hip_pt) and is_valid_point(shoulder_pt)):
        return None

    trunk_vec = np.array(
        [float(shoulder_pt[0]) - float(hip_pt[0]), float(shoulder_pt[1]) - float(hip_pt[1])],
        dtype=np.float64,
    )
    norm_t = float(np.linalg.norm(trunk_vec))
    if norm_t < NORM_EPS:
        return None

    v_up = np.array([0.0, -1.0], dtype=np.float64)
    cos_theta = float(np.dot(trunk_vec, v_up) / norm_t)
    cos_theta = float(np.clip(cos_theta, -1.0, 1.0))
    angle_deg = math.degrees(math.acos(cos_theta))
    return angle_deg if math.isfinite(angle_deg) else None


def midpoint(a: Optional[Point2D], b: Optional[Point2D]) -> Optional[Point2D]:
    """Compute midpoint between two valid 2D points."""
    if not (is_valid_point(a) and is_valid_point(b)):
        return None
    return (0.5 * (float(a[0]) + float(b[0])), 0.5 * (float(a[1]) + float(b[1])))
