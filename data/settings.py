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


@functools.lru_cache(maxsize=1)
def settings() -> dict[str, Any]:
    return _read("settings.yaml")


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
    return os.environ.get(name, default)
