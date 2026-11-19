"""Downloadable PDF assessment report generator using ReportLab and Matplotlib."""

from __future__ import annotations

import io
import math
from pathlib import Path
from typing import Any, Dict, List, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

STATUS_COLORS = {
    "GOOD": colors.HexColor("#10B981"),
    "NEEDS IMPROVEMENT": colors.HexColor("#D97706"),
    "OUTSIDE REFERENCE RANGE": colors.HexColor("#DC2626"),
    "INSUFFICIENT DATA": colors.HexColor("#64748B"),
}


def _render_angle_chart_png(results: Dict[str, Any]) -> Optional[io.BytesIO]:
    """Generate a publication-grade joint-angle & angular-velocity chart image from actual results."""
    bio = results.get("biomechanics") or {}
    timestamps = bio.get("timestamps_sec") or []
    angles = bio.get("angles_deg") or {}
    vels = bio.get("angular_velocities_deg_s") or {}
    movement_type = results.get("movement_type", "squat")

    if len(timestamps) < 2 or not angles:
        return None

    # Choose 2-3 primary angle series to plot cleanly
    if movement_type in ("squat", "lunge"):
        candidate_keys = ["left_knee_flexion", "right_knee_flexion", "left_hip_flexion", "right_hip_flexion", "trunk_inclination"]
    elif movement_type == "jumping_jack":
        candidate_keys = ["left_shoulder_angle", "right_shoulder_angle", "left_hip_internal", "right_hip_internal"]
    else:
        candidate_keys = ["right_elbow_internal", "left_elbow_internal", "right_shoulder_angle", "trunk_inclination"]

    plot_keys = [k for k in candidate_keys if k in angles and any(v is not None for v in angles[k])][:4]
    if not plot_keys:
        plot_keys = [k for k, ser in angles.items() if any(v is not None for v in ser)][:3]
    if not plot_keys:
        return None

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(7.2, 4.4), dpi=120, sharex=True)
    fig.patch.set_facecolor("#FFFFFF")
    palette = ["#0D9488", "#2563EB", "#D97706", "#DC2626"]

    for idx, key in enumerate(plot_keys):
        y_vals = [float(v) if v is not None else float("nan") for v in angles[key]]
        label = (bio.get("joint_summaries", {}).get(key, {}) or {}).get("label", key)
        ax1.plot(timestamps, y_vals, label=label, color=palette[idx % len(palette)], linewidth=1.6)

    ax1.set_ylabel("Angle (deg)", fontsize=9, fontweight="bold")
    ax1.set_title("Joint Angles Over Time", fontsize=10, fontweight="bold", pad=6)
    ax1.grid(True, linestyle="--", alpha=0.35)
    ax1.legend(loc="upper right", fontsize=7.5, framealpha=0.9)

    # Angular velocity plot for first 2 primary series
    vel_keys = [k for k in plot_keys[:2] if k in vels and any(v is not None for v in vels[k])]
    for idx, key in enumerate(vel_keys):
        y_vel = [float(v) if v is not None else float("nan") for v in vels[key]]
        label = (bio.get("joint_summaries", {}).get(key, {}) or {}).get("label", key)
        ax2.plot(timestamps, y_vel, label=f"{label} vel", color=palette[idx % len(palette)], linewidth=1.4)

    ax2.axhline(0.0, color="#94A3B8", linewidth=0.8)
    ax2.set_ylabel("Angular Vel (deg/s)", fontsize=9, fontweight="bold")
    ax2.set_xlabel("Time (seconds)", fontsize=9, fontweight="bold")
    ax2.set_title("Joint Angular Velocity Over Time", fontsize=10, fontweight="bold", pad=6)
    ax2.grid(True, linestyle="--", alpha=0.35)
    if vel_keys:
        ax2.legend(loc="upper right", fontsize=7.5, framealpha=0.9)

    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def generate_pdf_report(results: Dict[str, Any], output_pdf_path: str | Path) -> Path:
    """Generate a structured, evidence-based PDF assessment report using ReportLab."""
    out_path = Path(output_pdf_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=letter,
        leftMargin=0.6 * inch,
        rightMargin=0.6 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.55 * inch,
        title=f"MotionIQ Assessment Report - {results.get('analysis_id', '')}",
        author="MotionIQ Sports Biomechanics Platform",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "MotionTitle", parent=styles["Heading1"], fontSize=18, leading=22,
        textColor=colors.HexColor("#0F172A"), spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "MotionSubtitle", parent=styles["Normal"], fontSize=9.5, leading=13,
        textColor=colors.HexColor("#475569"), spaceAfter=10,
    )
    h2_style = ParagraphStyle(
        "MotionH2", parent=styles["Heading2"], fontSize=12.5, leading=16,
        textColor=colors.HexColor("#0F766E"), spaceBefore=12, spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "MotionBody", parent=styles["Normal"], fontSize=9, leading=12.5,
        textColor=colors.HexColor("#1E293B"), spaceAfter=4,
    )
    small_style = ParagraphStyle(
        "MotionSmall", parent=styles["Normal"], fontSize=8, leading=10.5,
        textColor=colors.HexColor("#334155"),
    )

    story: List[Any] = []

    analysis_id = results.get("analysis_id", "N/A")
    movement_label = results.get("movement_label", results.get("movement_type", "Movement"))
    video_meta = results.get("video_metadata") or {}
    proc_meta = results.get("processing_details") or {}
    quality = results.get("data_quality") or {}
    movement = results.get("movement_analysis") or {}
    assessment = results.get("assessment") or {}
    biomech = results.get("biomechanics") or {}

    # Header Banner Table
    header_table = Table(
        [[
            Paragraph("<b>MOTIONIQ</b> &nbsp;|&nbsp; Sports Biomechanics Assessment Report", ParagraphStyle("Hdr", fontSize=13, textColor=colors.white)),
            Paragraph(f"ID: {analysis_id[:12]}", ParagraphStyle("HdrR", fontSize=9, alignment=2, textColor=colors.HexColor("#36D6A0"))),
        ]],
        colWidths=[5.2 * inch, 2.1 * inch],
    )
    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#0B0F14")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 10))

    story.append(Paragraph(f"{movement_label} — Kinematic & Technique Report", title_style))
    story.append(
        Paragraph(
            f"Generated: {results.get('completed_at', 'N/A')} &nbsp;|&nbsp; "
            f"Selected Perspective: <b>{quality.get('selected_perspective', 'N/A').upper()}</b> "
            f"(Inferred: {quality.get('inferred_perspective', 'N/A').upper()}) &nbsp;|&nbsp; "
            f"Data Quality: <b>{quality.get('quality_status', 'N/A')}</b>",
            subtitle_style,
        )
    )

    # 1. Video & Processing Metadata
    story.append(Paragraph("1. Recording & Processing Telemetry", h2_style))
    meta_rows = [
        ["Source File", str(video_meta.get("filename", "N/A")), "Resolution", f"{video_meta.get('width', '?')} x {video_meta.get('height', '?')} px"],
        ["Source Frame Rate", f"{video_meta.get('fps', '?')} FPS", "Duration", f"{video_meta.get('duration_sec', '?')} s"],
        ["Total Video Frames", str(quality.get("total_frames", "?")), "Processed Frames", str(quality.get("frames_processed", "?"))],
        ["Valid Landmark Frames", f"{quality.get('valid_landmark_frames', 0)} ({quality.get('valid_frame_ratio', 0)*100:.1f}%)", "Mean Confidence", f"{quality.get('mean_landmark_confidence', 0)*100:.1f}%"],
        ["Pose Model", str(proc_meta.get("model_used", "MediaPipe Pose Landmarker")), "Confidence Threshold", str(proc_meta.get("confidence_threshold", 0.50))],
    ]
    meta_tbl = Table(meta_rows, colWidths=[1.5 * inch, 2.15 * inch, 1.5 * inch, 2.15 * inch])
    meta_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F1F5F9")),
        ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#F1F5F9")),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.2),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(meta_tbl)

    # 2. Executive Performance Summary
    story.append(Paragraph("2. Performance & Repetition Summary", h2_style))
    comp_score = assessment.get("composite_score")
    comp_text = f"{comp_score:.1f} / 100 ({assessment.get('composite_status')})" if comp_score is not None else "Withheld (Insufficient Data Coverage)"
    rep_count = movement.get("rep_count", 0)
    tot_dur = movement.get("total_movement_duration_sec", 0)

    story.append(
        Paragraph(
            f"<b>Detected Repetitions:</b> {rep_count} &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"<b>Active Movement Duration:</b> {tot_dur} s &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"<b>Composite Prototype Score:</b> {comp_text}",
            body_style,
        )
    )

    reps = movement.get("repetitions") or []
    if reps:
        rep_headers = ["Rep", "Window (s)", "Duration (s)", "Primary Peak", "Secondary Metric"]
        rep_rows = [rep_headers]
        for r in reps[:15]:
            if results.get("movement_type") == "squat":
                p1 = f"Knee Flex: {r.get('max_knee_flexion_deg', 'N/A')} deg"
                p2 = f"Trunk Peak: {r.get('max_trunk_inclination_deg', 'N/A')} deg"
            elif results.get("movement_type") == "lunge":
                p1 = f"Front Knee ({r.get('front_leg', '?')}): {r.get('front_knee_max_flexion_deg', 'N/A')} deg"
                p2 = f"Rear Knee: {r.get('rear_knee_max_flexion_deg', 'N/A')} deg"
            elif results.get("movement_type") == "jumping_jack":
                p1 = f"Mean Shoulder: {r.get('max_mean_shoulder_deg', 'N/A')} deg"
                p2 = f"Ankle Spread: {r.get('max_ankle_spread_ratio', 'N/A')}x torso"
            else:
                p1 = f"Release Elbow: {r.get('elbow_angle_at_release_deg', 'N/A')} deg"
                p2 = f"Release Shoulder: {r.get('shoulder_angle_at_release_deg', 'N/A')} deg"
            rep_rows.append([
                f"#{r.get('rep_number')}",
                f"{r.get('start_time_sec', 0):.2f} - {r.get('end_time_sec', 0):.2f}",
                f"{r.get('duration_sec', 0):.2f}",
                p1,
                p2,
            ])
        rep_tbl = Table(rep_rows, colWidths=[0.55 * inch, 1.35 * inch, 0.95 * inch, 2.2 * inch, 2.25 * inch])
        rep_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(Spacer(1, 4))
        story.append(rep_tbl)

    # 3. Joint Kinematics Table
    story.append(Paragraph("3. Joint Kinematics Summary", h2_style))
    summaries = biomech.get("joint_summaries") or {}
    if summaries:
        j_rows = [["Joint Metric", "Mean (deg)", "Min / Max (deg)", "ROM (deg)", "Peak Vel (deg/s)", "Valid Frames", "Conf."]]
        for key, js in summaries.items():
            if not js.get("sufficient_data"):
                j_rows.append([
                    js.get("label", key), "INSUFFICIENT", "-", "-", "-",
                    f"{js.get('valid_frames', 0)}/{js.get('total_frames', 0)}",
                    f"{js.get('mean_confidence', 0)*100:.0f}%",
                ])
            else:
                j_rows.append([
                    js.get("label", key),
                    f"{js.get('mean_deg')}",
                    f"{js.get('min_deg')} / {js.get('max_deg')}",
                    f"{js.get('rom_deg')}",
                    f"{js.get('peak_angular_velocity_deg_s') or '-'}",
                    f"{js.get('valid_frames')}/{js.get('total_frames')} ({js.get('valid_ratio', 0)*100:.0f}%)",
                    f"{js.get('mean_confidence', 0)*100:.0f}%",
                ])
        j_tbl = Table(j_rows, colWidths=[2.0 * inch, 0.75 * inch, 1.05 * inch, 0.7 * inch, 0.95 * inch, 1.15 * inch, 0.7 * inch])
        j_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7.6),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ("TOPPADDING", (0, 0), (-1, -1), 3.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ]))
        story.append(j_tbl)

    # 4. Joint-Angle & Velocity Charts
    chart_buf = _render_angle_chart_png(results)
    if chart_buf is not None:
        story.append(Paragraph("4. Biomechanical Time-Series Charts", h2_style))
        story.append(Image(chart_buf, width=7.1 * inch, height=4.4 * inch))

    story.append(PageBreak())

    # 5. Technique Assessment
    story.append(Paragraph("5. Evidence-Based Technique Assessment", h2_style))
    params = assessment.get("parameters") or []
    if params:
        a_rows = [["Parameter", "Measured", "Reference & Source", "Status", "Evidence & Explanation"]]
        for p in params:
            val_txt = f"{p['measured_value']} {p['unit']}" if p.get("measured_value") is not None else "N/A"
            ref_txt = f"{p.get('reference_range', '')}\n[{p.get('criteria_source', '').replace('_', ' ')}]"
            st = p.get("status", "INSUFFICIENT DATA")
            a_rows.append([
                Paragraph(f"<b>{p['parameter_name']}</b><br/>Conf: {p['confidence']*100:.0f}%", small_style),
                Paragraph(val_txt, small_style),
                Paragraph(ref_txt.replace("\n", "<br/>"), small_style),
                Paragraph(f"<b>{st}</b>", ParagraphStyle("St", parent=small_style, textColor=STATUS_COLORS.get(st, colors.black))),
                Paragraph(p.get("explanation", ""), small_style),
            ])
        a_tbl = Table(a_rows, colWidths=[1.45 * inch, 0.8 * inch, 1.4 * inch, 1.05 * inch, 2.6 * inch])
        a_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 8),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(a_tbl)

    # Composite methodology
    meth = assessment.get("composite_methodology") or {}
    if meth:
        story.append(Spacer(1, 6))
        story.append(
            Paragraph(
                f"<b>Composite Scoring Methodology:</b> {meth.get('normalization_method', '')} "
                f"{meth.get('missing_data_handling', '')}",
                small_style,
            )
        )

    # Suggestions
    adjs = assessment.get("technique_adjustments") or []
    if adjs:
        story.append(Paragraph("6. Suggested Technique & Recording Adjustments", h2_style))
        for adj in adjs:
            story.append(Paragraph(f"• <b>{adj['parameter']}:</b> {adj['suggestion']}", body_style))

    # 7. Data Quality, Limitations & Educational Disclaimer
    story.append(Paragraph("7. Data Quality, Limitations & Educational Disclaimer", h2_style))
    for w in quality.get("warnings") or []:
        story.append(Paragraph(f"• <b>Data Warning:</b> {w}", body_style))
    for lim in quality.get("camera_limitations") or []:
        story.append(Paragraph(f"• <b>Camera Limitation:</b> {lim}", body_style))
    if movement.get("ball_velocity_disclaimer"):
        story.append(Paragraph(f"• <b>Scope Note:</b> {movement['ball_velocity_disclaimer']}", body_style))

    story.append(Spacer(1, 8))
    disclaimer_box = Table(
        [[Paragraph(
            f"<b>EDUCATIONAL & PROTOTYPE DISCLAIMER:</b> {assessment.get('prototype_disclaimer', '')}",
            ParagraphStyle("Disc", fontSize=8.2, leading=11, textColor=colors.HexColor("#7F1D1D")),
        )]],
        colWidths=[7.3 * inch],
    )
    disclaimer_box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FEF2F2")),
        ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#FCA5A5")),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(disclaimer_box)

    doc.build(story)
    return out_path
