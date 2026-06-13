"""Persistent settings store.

User-controlled settings (provider, model, ollama URL) live in a JSON file at
the project root (`settings.json`, gitignored). API keys live in `.env` because
that's where LangChain and the OS env already read them. The two stores are
deliberately separate: anyone who shares `settings.json` (e.g. via a git
checkout on a colleague's machine) doesn't accidentally leak their OpenAI key.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from .config import SUPPORTED_PROVIDERS, Settings

ENV_PATH = Path(".env")


@dataclass
class PersistedSettings:
    provider: str = "ollama"
    model: str = "gemma4:latest"
    ollama_base_url: str = "http://localhost:11434"
    minimax_base_url: str = "https://api.minimax.io/v1"
    # API keys are *only* stored in .env. The settings.json knows which keys
    # are *set* (not the values) so the UI can show a filled/empty indicator.
    has_openai_key: bool = False
    has_anthropic_key: bool = False
    has_minimax_key: bool = False

    @classmethod
    def load(cls) -> "PersistedSettings":
        path = _settings_path()
        if not path.exists():
            return cls()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return cls()
        # Validate provider; fall back to default if someone hand-edited a bad value.
        provider = str(raw.get("provider", "ollama")).lower()
        if provider not in SUPPORTED_PROVIDERS:
            provider = "ollama"
        return cls(
            provider=provider,
            model=str(raw.get("model", cls.model)),
            ollama_base_url=str(raw.get("ollama_base_url", cls.ollama_base_url)),
            minimax_base_url=str(raw.get("minimax_base_url", cls.minimax_base_url)),
            has_openai_key=bool(raw.get("has_openai_key", False)),
            has_anthropic_key=bool(raw.get("has_anthropic_key", False)),
            has_minimax_key=bool(raw.get("has_minimax_key", False)),
        )

    def save(self) -> None:
        path = _settings_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(asdict(self), indent=2) + "\n",
            encoding="utf-8",
        )

    def to_settings(self) -> Settings:
        """Convert to the legacy Settings dataclass for the gateway."""
        return Settings(
            provider=self.provider,
            model=self.model,
            ollama_base_url=self.ollama_base_url,
            minimax_base_url=self.minimax_base_url,
        )


def _settings_path() -> Path:
    override = os.environ.get("SPECGUARD_SETTINGS_FILE")
    if override:
        return Path(override)
    # Project root: walk up from this file until we find pyproject.toml.
    here = Path(__file__).resolve().parent
    for candidate in (here, *here.parents):
        if (candidate / "pyproject.toml").exists() and (candidate / "src" / "specguard").exists():
            return candidate / "settings.json"
    return Path("settings.json").resolve()


# ---------------------------------------------------------------------------
# .env helpers
# ---------------------------------------------------------------------------


def read_env_var(name: str) -> Optional[str]:
    """Read a single variable from .env if present; do not return empty values."""
    path = ENV_PATH
    if not path.exists():
        return os.environ.get(name)
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        if k.strip() == name:
            v = v.strip()
            if v:
                return v
            return None
    return os.environ.get(name)


def write_env_var(name: str, value: str) -> None:
    """Idempotently set a key in .env. Creates the file if missing."""
    path = ENV_PATH
    lines: list[str] = []
    if path.exists():
        lines = path.read_text(encoding="utf-8").splitlines()
    found = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("#") or "=" not in stripped:
            continue
        k, _, _ = stripped.partition("=")
        if k.strip() == name:
            lines[i] = f"{name}={value}"
            found = True
            break
    if not found:
        lines.append(f"{name}={value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    # Also update the in-process env so the running server sees the new key
    # without needing a restart.
    os.environ[name] = value


def clear_env_var(name: str) -> None:
    path = ENV_PATH
    if not path.exists():
        os.environ.pop(name, None)
        return
    lines = path.read_text(encoding="utf-8").splitlines()
    lines = [
        line
        for line in lines
        if not (
            line.strip().startswith(name + "=")
            and not line.strip().startswith("#")
        )
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.environ.pop(name, None)
