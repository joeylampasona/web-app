"""meta.json is the contract between the pipeline and the web app."""
from __future__ import annotations

from typing import Any

META_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "meta.json",
    "type": "object",
    "required": ["version", "generated_at", "as_of", "provider", "data_source",
                 "universe_count", "survivorship_safe", "screens", "themes",
                 "benchmark", "disclaimer"],
    "additionalProperties": True,
    "properties": {
        "version": {"type": "integer", "minimum": 1},
        "generated_at": {"type": "string"},
        "as_of": {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$"},
        "provider": {"type": "string"},
        "data_source": {"type": "string", "enum": ["live", "synthetic_demo"]},
        "universe_count": {"type": "integer", "minimum": 0},
        "survivorship_safe": {"type": "boolean"},
        "benchmark": {"type": "string"},
        "market_wide_breakouts": {"type": "integer", "minimum": 0},
        "screens": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["key", "name", "total", "stages"],
                "properties": {
                    "key": {"type": "string"},
                    "name": {"type": "string"},
                    "total": {"type": "integer", "minimum": 0},
                    "stages": {"type": "object"},
                },
            },
        },
        "themes": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["slug", "name"],
                "properties": {"slug": {"type": "string"}, "name": {"type": "string"}},
            },
        },
        "disclaimer": {"type": "string"},
    },
}


def validate(meta: dict) -> list[str]:
    """Returns a list of problems. Empty means it validates."""
    try:
        import jsonschema
    except Exception:                             # noqa: BLE001
        return ["jsonschema is not installed — cannot validate meta.json"]
    validator = jsonschema.Draft202012Validator(META_SCHEMA)
    return [f"{'/'.join(str(p) for p in e.path) or '(root)'}: {e.message}"
            for e in sorted(validator.iter_errors(meta), key=lambda e: list(e.path))]
