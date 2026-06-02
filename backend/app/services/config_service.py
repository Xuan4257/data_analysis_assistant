import json
from typing import Any

from ..settings import CONFIG_PATH, ensure_runtime_dirs


DEFAULT_CONFIG = {
    "base_url": "",
    "api_key": "",
    "model": "",
    "enabled": True,
}


def load_config() -> dict[str, Any]:
    ensure_runtime_dirs()
    if not CONFIG_PATH.exists():
        return DEFAULT_CONFIG.copy()
    try:
        return {**DEFAULT_CONFIG, **json.loads(CONFIG_PATH.read_text(encoding="utf-8"))}
    except (json.JSONDecodeError, OSError):
        return DEFAULT_CONFIG.copy()


def save_config(config: dict[str, Any]) -> dict[str, Any]:
    ensure_runtime_dirs()
    current = load_config()
    if not config.get("api_key"):
        config["api_key"] = current.get("api_key", "")
    merged = {**DEFAULT_CONFIG, **config}
    CONFIG_PATH.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    return public_config(merged)


def public_config(config: dict[str, Any] | None = None) -> dict[str, Any]:
    config = config or load_config()
    return {
        "base_url": config["base_url"],
        "model": config["model"],
        "enabled": config["enabled"],
        "has_api_key": bool(config.get("api_key")),
        "api_key": "",
    }
