from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]




def test_browser_script_records_webm_and_webp_keyframes():
    p = ROOT / "scripts" / "browser_compare_plain_hybrid.py"
    text = p.read_text(encoding="utf-8")
    assert "record_video_dir" in text
    assert "type=\"webp\"" in text
    assert "WebM" in text


def test_eval_override_is_disabled_by_default():
    text = (ROOT / "src" / "core" / "config.py").read_text(encoding="utf-8")
    assert "enable_eval_mode_override" in text
    assert "default=False" in text


def test_eval_override_header_is_guarded():
    text = (ROOT / "src" / "api" / "routes.py").read_text(encoding="utf-8")
    assert "X-GraphRAG-Eval-Mode" in text
    assert "enable_eval_mode_override" in text


def test_browser_comparison_disables_ui_cache_for_fairness():
    p = ROOT / "scripts" / "browser_compare_plain_hybrid.py"
    text = p.read_text(encoding="utf-8")
    assert 'cache-toggle' in text
    assert 'uncheck()' in text
