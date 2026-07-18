"""設定ファイル(YAML)の読み込みとアクセスを提供するモジュール。"""

from __future__ import annotations

import functools
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "default.yaml"
TANK_MODEL_CONFIG_PATH = PROJECT_ROOT / "config" / "tank_model.yaml"


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


@dataclass
class AppConfig:
    """アプリ全体の設定を保持するコンテナ。"""

    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path | None = None, overrides: dict[str, Any] | None = None) -> "AppConfig":
        config_path = path or DEFAULT_CONFIG_PATH
        with open(config_path, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        if overrides:
            raw = _deep_merge(raw, overrides)
        return cls(raw=raw)

    def get(self, dotted_key: str, default: Any = None) -> Any:
        """"a.b.c" 形式のキーで設定値を取得する。"""
        node: Any = self.raw
        for part in dotted_key.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def resolved_path(self, dotted_key: str) -> Path:
        """設定内の相対パスをプロジェクトルート基準の絶対パスへ変換する。"""
        value = self.get(dotted_key)
        if value is None:
            raise KeyError(f"設定キーが見つかりません: {dotted_key}")
        p = Path(value)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        return p


@functools.lru_cache(maxsize=1)
def get_default_config() -> AppConfig:
    return AppConfig.load()


def load_tank_model_config(path: Path | None = None) -> dict[str, Any]:
    config_path = path or TANK_MODEL_CONFIG_PATH
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}
