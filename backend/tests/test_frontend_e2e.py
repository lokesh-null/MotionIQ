"""End-to-end Playwright Chromium verification against live Vite frontend + FastAPI backend."""

from __future__ import annotations

from pathlib import Path
from playwright.sync_api import sync_playwright

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SAMPLE_SQUAT = PROJECT_ROOT / "sample_videos" / "squat_side_1.mp4"


def test_full_frontend_user_journey(tmp_path):
    assert SAMPLE_SQUAT.exists(), f"Missing sample video {SAMPLE_SQUAT}"

    page_errors: list[str] = []
    console_errors: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900}, accept_downloads=True)
        page = context.new_page()

        page.on("pageerror", lambda err: page_errors.append(str(err)))
        page.on(
            "console",
            lambda msg: console_errors.append(msg.text) if msg.type == "error" else None,
        )

        # 1. Dashboard honest empty state
        page.goto("http://127.0.0.1:5173/", wait_until="networkidle")
        page.get_by_text("No Movement Assessments Recorded Yet").wait_for(timeout=10_000)

        # 2. Navigate to New Analysis and upload real human squat video
        page.get_by_role("link", name="Start New Analysis").click()
        page.wait_for_url("**/new")
        page.get_by_text("Side-View Recording (Sagittal Plane)").wait_for(timeout=5_000)

        page.set_input_files('input[type="file"]', str(SAMPLE_SQUAT))
        page.get_by_text("READY FOR ANALYSIS").wait_for(timeout=15_000)
        page.get_by_text("608 × 1080").wait_for(timeout=5_000)
        page.get_by_text("29.97 FPS").wait_for(timeout=5_000)
        page.get_by_text("614").wait_for(timeout=5_000)

        # Verify preview video element is mounted
        preview_vid = page.locator("video").first
        preview_vid.wait_for(timeout=5_000)

        # 3. Start processing and watch live progress -> redirect to /results/:id
        page.get_by_role("button", name="Start Biomechanical Analysis").click()
        page.wait_for_url("**/processing/*", timeout=10_000)
        page.get_by_text("Pipeline Stage Telemetry").wait_for(timeout=5_000)

        page.wait_for_url("**/results/*", timeout=90_000)

        # 4. Verify Analysis Results Dashboard
        page.get_by_text("Performance Summary").wait_for(timeout=10_000)
        page.get_by_text("91.2/100").wait_for(timeout=10_000)
        page.get_by_text("QUALITY: GOOD").wait_for(timeout=10_000)

        # Verify annotated H.264 video loads metadata and plays
        ann_vid = page.locator("video").first
        ann_vid.wait_for(timeout=10_000)
        page.wait_for_function(
            """() => {
                const v = document.querySelector('video');
                return v && v.readyState >= 1 && v.videoWidth > 0 && v.duration > 10;
            }""",
            timeout=15_000,
        )
        vid_dims = page.evaluate(
            """() => {
                const v = document.querySelector('video');
                return { width: v.videoWidth, height: v.videoHeight, duration: v.duration };
            }"""
        )
        print(f"\n[E2E Video] width={vid_dims['width']}, height={vid_dims['height']}, duration={vid_dims['duration']:.2f}s")
        assert vid_dims["width"] > 0 and vid_dims["height"] > 0

        # Click Play button and verify currentTime advances
        page.get_by_role("button", name="Play").click()
        page.wait_for_timeout(800)
        cur_t = page.evaluate("() => document.querySelector('video').currentTime")
        print(f"[E2E Video Playback] currentTime after 0.8s play = {cur_t:.2f}s")
        assert cur_t > 0.1

        # Verify all 5 Recharts tabs render cleanly
        for tab_name in [
            "Joint Angles vs Time",
            "Angular Velocity",
            "Repetition Comparison",
            "Left-Right Symmetry",
            "Phases & Joint Trajectory",
        ]:
            page.get_by_role("button", name=tab_name).click()
            page.wait_for_timeout(200)
            if tab_name == "Left-Right Symmetry":
                page.get_by_text("Bilateral Symmetry Chart Withheld").wait_for(timeout=5_000)
            else:
                svg_count = page.locator(".recharts-surface").count()
                assert svg_count >= 1, f"Expected Recharts SVG for tab {tab_name}"

        # Open Report Summary preview and verify PDF download
        page.get_by_role("button", name="Report Summary").click()
        page.get_by_text("Download Full ReportLab PDF").wait_for(timeout=5_000)

        with page.expect_download(timeout=15_000) as dl_info:
            page.get_by_role("link", name="Download PDF").click()
        download = dl_info.value
        dl_dest = tmp_path / download.suggested_filename
        download.save_as(str(dl_dest))
        pdf_bytes = dl_dest.read_bytes()
        print(f"[E2E PDF Download] file={download.suggested_filename}, bytes={len(pdf_bytes)}")
        assert pdf_bytes[:5] == b"%PDF-"
        assert len(pdf_bytes) > 10_000

        # 5. Navigate back to Dashboard and verify Recent Assessments now shows the real record
        page.get_by_role("link", name="Dashboard").click()
        page.wait_for_url("http://127.0.0.1:5173/")
        page.get_by_text("Biomechanics Overview").wait_for(timeout=10_000)
        table = page.locator("table")
        table.wait_for(timeout=10_000)
        table.get_by_text("squat_side_1.mp4").first.wait_for(timeout=10_000)
        table.get_by_text("91.2/100").first.wait_for(timeout=5_000)

        assert page_errors == [], f"Uncaught JS page errors: {page_errors}"
        assert console_errors == [], f"Console errors: {console_errors}"
        browser.close()
