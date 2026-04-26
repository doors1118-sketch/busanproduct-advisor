"""
Keyword Dictionary — YAML 기반 키워드 사전 로드/저장
분류 실패 로그 기반 주 1회 업데이트 대상.
"""
import os
import yaml

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_YAML_PATH = os.path.join(_BASE_DIR, "config", "keyword_routes.yaml")

_cached_dict: dict = {}


def load_keyword_dict() -> dict:
    global _cached_dict
    if _cached_dict:
        return _cached_dict
    with open(_YAML_PATH, "r", encoding="utf-8") as f:
        _cached_dict = yaml.safe_load(f) or {}
    return _cached_dict


def save_keyword_dict(data: dict) -> None:
    global _cached_dict
    with open(_YAML_PATH, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
    _cached_dict = data


def add_keyword(category: str, keyword: str) -> None:
    d = load_keyword_dict()
    if category not in d:
        d[category] = []
    if keyword not in d[category]:
        d[category].append(keyword)
        save_keyword_dict(d)
