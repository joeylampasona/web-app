"""Loads config/settings.yaml and config/themes.yaml once, for everyone."""
from __future__ import annotations

import functools
import os
import pathlib
from typing import Any

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"


def _read(name: str) -> dict[str, Any]:
    with open(CONFIG_DIR / name, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in (overlay or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


@functools.lru_cache(maxsize=1)
def settings() -> dict[str, Any]:
    """settings.yaml, with settings.local.yaml layered on top if it exists.

    The local file is gitignored. Machine-specific choices — which provider,
    how much history — belong there, so pulling a change to the tracked file
    never collides with them.
    """
    base = _read("settings.yaml")
    local_path = CONFIG_DIR / "settings.local.yaml"
    if local_path.exists():
        base = _merge(base, _read("settings.local.yaml"))
    return _apply_env(base)


# CI has no settings.local.yaml — it is gitignored, which is the whole point of
# it — so the few settings that differ between a laptop and the nightly job are
# also readable from the environment.
_ENV_OVERRIDES = {
    "DATA_PROVIDER": ("data", "provider", str),
    "BACKFILL_DAYS": ("data", "backfill_days", int),
    "OUT_DIR": ("publish", "out_dir", str),
}


def _apply_env(config: dict[str, Any]) -> dict[str, Any]:
    for name, (section, key, cast) in _ENV_OVERRIDES.items():
        raw = os.environ.get(name)
        if raw is None or raw == "":
            continue
        try:
            config.setdefault(section, {})[key] = cast(raw)
        except (TypeError, ValueError):
            continue
    return config


@functools.lru_cache(maxsize=1)
def themes() -> list[dict[str, Any]]:
    return _read("themes.yaml").get("themes", [])


def get(path: str, default: Any = None) -> Any:
    """Dotted lookup: get('universe.min_price')."""
    node: Any = settings()
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def db_path() -> pathlib.Path:
    p = ROOT / get("data.db_path", "var/market.db")
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def out_dir() -> pathlib.Path:
    p = ROOT / get("publish.out_dir", "out")
    p.mkdir(parents=True, exist_ok=True)
    return p


def env(name: str, default: str = "") -> str:
    """A credential, from the environment or from the gitignored local settings.

    The environment wins, because that is how CI supplies these. But a shell
    export only lasts as long as the tab it was typed into, and losing a key by
    opening a new terminal is a trap rather than a security measure. So a
    `secrets:` block in config/settings.local.yaml — which is gitignored, and is
    where a laptop's overrides already live — works too, and survives.

    Whitespace is stripped from whatever is found. A credential never
    legitimately begins or ends with a space, and pasting one into a secret box
    picks up a trailing space or newline easily — GitHub stores it verbatim and
    masks only the key itself, so the stray character is invisible in the logs
    and in the box. FRED_API_KEY arrived that way and answered every nightly
    with "the value for variable api_key is not a 32 character alpha-numeric
    lower-case string", while the site published `configured: true` and an
    empty calendar for weeks.
    """
    from_env = os.environ.get(name)
    if from_env and from_env.strip():
        return from_env.strip()
    stored = (get("secrets", {}) or {}).get(name)
    return str(stored).strip() if stored and str(stored).strip() else default
