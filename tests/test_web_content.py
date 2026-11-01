from pathlib import Path
import re


WEB_DIR = Path(__file__).resolve().parents[1] / "web"
PROJECT_ROOT = WEB_DIR.parent


def test_public_form_uses_correct_description_and_schedule_wording():
    app = (WEB_DIR / "app.js").read_text(encoding="utf-8")

    assert "Join the organizing committee as a volunteer guide, usher, or lab mentor." not in app
    assert "Schedule: ${esc(displayDateTime(form.open_time, \"Immediately\"))} to" in app
    assert 'json("/api/public/forms", { cache: "no-store" })' in app


def test_sidebar_labels_and_wrapping_rules_are_present():
    app = (WEB_DIR / "app.js").read_text(encoding="utf-8")
    styles = (WEB_DIR / "styles.css").read_text(encoding="utf-8")

    for label in ("Public Portal Mode", "Student Registration", "Cabinet & Admin Login"):
        assert label in app
    assert ".nav-button { width: 100%; min-width: 0;" in styles
    assert "white-space: normal;" in styles


def test_layout_has_safe_desktop_width_constraints():
    styles = (WEB_DIR / "styles.css").read_text(encoding="utf-8")

    assert "*, *::before, *::after { box-sizing: border-box; }" in styles
    assert "html, body { width: 100%; max-width: 100%; margin: 0; }" in styles
    assert ".page-shell { width: 100%; max-width: 1440px; min-width: 0;" in styles
    assert "grid-template-columns: minmax(0, 245px) minmax(0, 1fr);" in styles
    assert ".content { width: 100%; max-width: 100%; min-width: 0;" in styles
    assert ".form-grid { width: 100%; max-width: 100%; min-width: 0;" in styles
    assert "input, select, textarea { width: 100%; max-width: 100%; min-width: 0;" in styles
    assert "@media (max-width: 800px)" in styles
    assert ".form-grid, .split { grid-template-columns: 1fr; }" in styles


def test_public_sources_do_not_expose_default_credentials():
    public_sources = [
        WEB_DIR / "index.html",
        WEB_DIR / "app.js",
        PROJECT_ROOT / "README.md",
        PROJECT_ROOT / "run_all.py",
        PROJECT_ROOT / "frontend" / "app.py",
        PROJECT_ROOT / "frontend" / "admin_view.py",
        PROJECT_ROOT / "frontend" / "cabinet_view.py",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in public_sources)

    assert "View Default System Credentials" not in combined
    assert "Default Credentials" not in combined
    assert "Default Password" not in combined
    assert not re.search(
        r"""(?i)(?:password|passwd)\s*['"`]?\s*[:=]\s*['"`][^'"`\r\n]+['"`]""",
        combined,
    )
    assert "Username" in (WEB_DIR / "app.js").read_text(encoding="utf-8")
    assert "Password" in (WEB_DIR / "app.js").read_text(encoding="utf-8")
    assert "Sign In to Portal" in (WEB_DIR / "app.js").read_text(encoding="utf-8")
    assert "Invalid username or password." in (
        PROJECT_ROOT / "backend" / "main.py"
    ).read_text(encoding="utf-8")
