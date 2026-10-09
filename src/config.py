"""config/ 폴더의 YAML 설정 파일 로더."""

from __future__ import annotations

from pathlib import Path

import yaml

from src.utils import ROOT

CONFIG_DIR = ROOT / "config"


def load_yaml(name: str) -> dict:
    """config/<name> 파일을 읽어 dict로 반환. 파일이 없으면 빈 dict."""
    path = CONFIG_DIR / name
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_sources() -> dict:
    return load_yaml("sources.yaml")
