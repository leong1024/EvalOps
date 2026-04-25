from pathlib import Path

from evalops.prompts import configure_template_paths, render_file


def test_configure_template_paths_uses_custom_template_directory(tmp_path):
    template = tmp_path / "custom.j2"
    template.write_text("Hello {{ name }}", encoding="utf-8")

    try:
        configure_template_paths([tmp_path])
        assert render_file("custom.j2", name="EvalOps") == "Hello EvalOps"
    finally:
        configure_template_paths([Path(__file__).resolve().parents[1] / "evalops" / "tpl"])
