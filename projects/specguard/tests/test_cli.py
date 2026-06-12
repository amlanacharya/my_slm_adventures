from pathlib import Path

from click.testing import CliRunner

from specguard import cli


def test_models_check_prints_config(monkeypatch):
    monkeypatch.setenv("SPECGUARD_PROVIDER", "ollama")
    monkeypatch.setenv("SPECGUARD_MODEL", "gemma3:4b")
    runner = CliRunner()

    result = runner.invoke(cli.main, ["models", "check"])

    assert result.exit_code == 0
    assert "provider: ollama" in result.output
    assert "model: gemma3:4b" in result.output


def test_generate_writes_output_with_fake_pipeline(monkeypatch, tmp_path: Path):
    def fake_generate_document(request):
        out = tmp_path / "prd" / "fake.md"
        out.parent.mkdir(parents=True)
        out.write_text("# Product Requirements Document\n", encoding="utf-8")
        return type(
            "Result",
            (),
            {
                "output_path": out,
                "validation": type("Validation", (), {"ok": True, "missing_sections": ()})(),
            },
        )()

    monkeypatch.setattr(cli, "generate_document", fake_generate_document)
    runner = CliRunner()

    result = runner.invoke(cli.main, ["generate", "Build an app", "--mode", "prd", "--output-dir", str(tmp_path)])

    assert result.exit_code == 0
    assert "wrote:" in result.output
