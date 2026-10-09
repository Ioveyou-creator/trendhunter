"""공통 유틸리티: HTTP 요청, JSON 저장, 시간."""

from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# 프로젝트 루트 / 데이터 폴더
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "docs" / "data"

USER_AGENT = "Mozilla/5.0 (compatible; TrendHunter/0.1; +https://github.com/Ioveyou-creator/trendhunter)"


def now_iso() -> str:
    """현재 시각(UTC)을 ISO 8601 문자열로 반환."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def http_get(url: str, timeout: int = 20) -> bytes:
    """URL을 GET 요청해 본문(bytes)을 반환. 실패 시 예외 발생."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def save_json(data: dict, filename: str) -> Path:
    """docs/data/ 아래에 JSON 파일 저장 (한글 그대로, 들여쓰기)."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / filename
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def source_result(source: str, items: list, error: str | None = None) -> dict:
    """모든 수집기가 같은 형태로 결과를 반환하도록 하는 공통 포맷."""
    return {
        "source": source,
        "fetched_at": now_iso(),
        "ok": error is None,
        "error": error,
        "count": len(items),
        "items": items,
    }
