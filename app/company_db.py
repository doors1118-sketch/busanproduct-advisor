"""
Read-only local access to chatbot_company.db.

The monitoring system already builds a consolidated SQLite DB and exposes
chatbot_company_candidate_view. Advisor should use that local VIEW first and
fall back to HTTP only when the DB is missing or stale.
"""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]

_PRODUCT_ALIASES = {
    "led": ["LED", "LED조명", "LED실내조명등", "LED램프"],
    "led조명": ["LED", "LED조명", "LED실내조명등", "LED램프"],
    "led등": ["LED", "LED조명", "LED실내조명등", "LED램프"],
    "엘이디": ["LED", "LED조명", "LED실내조명등", "LED램프"],
    "엘이디등": ["LED", "LED조명", "LED실내조명등", "LED램프"],
    "엘이디조명": ["LED", "LED조명", "LED실내조명등", "LED램프"],
    "씨씨티비": ["CCTV", "영상감시장치"],
    "cctv": ["CCTV", "영상감시장치"],
}

_POLICY_ALIASES = {
    "여성기업": "women_company",
    "장애인기업": "disabled_company",
    "사회적기업": "social_enterprise",
    "중소기업": "sme",
    "소상공인": "small_business",
    "창업기업": "startup",
    "청년창업기업": "youth_startup",
    "벤처기업": "venture_company",
}


def _candidate_db_paths() -> list[Path]:
    paths: list[Path] = []
    env_path = os.getenv("CHATBOT_COMPANY_DB_PATH") or os.getenv("COMPANY_VIEW_DB_PATH")
    if env_path:
        paths.append(Path(env_path))
    paths.extend([
        PROJECT_ROOT / "cache" / "company" / "cache_current" / "chatbot_company.db",
        Path("/opt/busan/chatbot_company.db"),
        Path("C:/dev/busan-city-local-products/staging_chatbot_company.db"),
        Path("C:/dev/busan-city-local-products/chatbot_company.db"),
    ])
    return paths


def get_db_path() -> Path | None:
    if os.getenv("COMPANY_VIEW_DB_ENABLED", "true").lower() not in {"1", "true", "yes", "on"}:
        return None
    for path in _candidate_db_paths():
        if path.exists() and path.stat().st_size > 0:
            return path
    return None


def _connect() -> sqlite3.Connection | None:
    path = get_db_path()
    if not path:
        return None
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=1.0)
    conn.row_factory = sqlite3.Row
    return conn


def _split_pipe(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [p.strip() for p in str(value).split("|") if p.strip()]


def _json_or_list(value: Any, fallback: list[str] | None = None) -> list[str]:
    if not value:
        return fallback or []
    if isinstance(value, list):
        return value
    try:
        parsed = json.loads(str(value))
        if isinstance(parsed, list):
            return parsed
    except Exception:
        pass
    return fallback or _split_pipe(value)


def _parse_policy(raw: Any, validity_filter: str = "valid_only") -> tuple[list[str], dict[str, str]]:
    tags: list[str] = []
    summary: dict[str, str] = {}
    for part in _split_pipe(raw):
        if ":" in part:
            subtype, status = part.split(":", 1)
        else:
            subtype, status = part, "unknown"
        subtype = subtype.strip()
        status = status.strip() or "unknown"
        if not subtype:
            continue
        summary[subtype] = status
        if validity_filter == "valid_only" and status not in {"valid", "unknown", ""}:
            continue
        tags.append(subtype)
    return sorted(set(tags)), summary


def _parse_certified_types(raw: Any, validity_filter: str = "valid_only") -> list[str]:
    result: set[str] = set()
    for part in _split_pipe(raw):
        fields = part.split(":")
        cert_type = fields[0].strip() if fields else ""
        validity = fields[4].strip() if len(fields) >= 5 else "unknown"
        if not cert_type:
            continue
        if validity_filter == "valid_only" and validity not in {"valid", "unknown", ""}:
            continue
        result.add(cert_type)
        if len(fields) >= 4:
            if fields[1] == "1":
                result.add("priority_purchase_product")
            if fields[2] == "1":
                result.add("innovation_product")
            if fields[3] == "1":
                result.add("excellent_procurement_product")
    return sorted(result)


def _parse_summary(raw: Any) -> list[dict[str, Any]]:
    rows = []
    for part in str(raw or "").split("|||"):
        if not part.strip():
            continue
        fields = part.split("^^")
        rows.append({
            "product_name": fields[0].strip() if len(fields) > 0 else "",
            "detail_product_code": fields[1].strip() if len(fields) > 1 else "",
            "type": fields[2].strip() if len(fields) > 2 else "",
            "status": fields[3].strip() if len(fields) > 3 else "",
            "valid_until": fields[4].strip() if len(fields) > 4 else "",
            "source": fields[-1].strip() if fields else "",
        })
    return rows


def _parse_shopping_flags(raw: Any) -> list[str]:
    flags = set()
    for group in str(raw or "").split(","):
        for flag in group.split("|"):
            flag = flag.strip()
            if flag:
                flags.add(flag)
    return sorted(flags)


def _row_to_candidate(row: sqlite3.Row, *, validity_filter: str = "valid_only") -> dict[str, Any]:
    d = dict(row)
    policy_tags, policy_summary = _parse_policy(d.get("policy_subtypes_raw"), validity_filter)
    certified_types = _parse_certified_types(d.get("certified_product_types_raw"), validity_filter)
    shopping_flags = _parse_shopping_flags(d.get("shopping_mall_flags_raw"))
    candidate_types = _json_or_list(d.get("candidate_types"), ["local_procurement_company"])
    if policy_tags and "policy_company" not in candidate_types:
        candidate_types.append("policy_company")
    if shopping_flags and "shopping_mall_supplier" not in candidate_types:
        candidate_types.append("shopping_mall_supplier")
    if certified_types and "certified_product" not in candidate_types:
        candidate_types.append("certified_product")

    return {
        "company_id": d.get("company_id", "unknown"),
        "company_name": d.get("company_name", ""),
        "location": d.get("location", ""),
        "detail_address": d.get("detail_address", ""),
        "is_busan_company": d.get("is_busan_company"),
        "is_headquarters": d.get("is_headquarters"),
        "license_or_business_type": _split_pipe(d.get("license_or_business_type")),
        "main_products": _split_pipe(d.get("main_products")),
        "candidate_types": candidate_types,
        "primary_candidate_type": d.get("primary_candidate_type", "local_procurement_company"),
        "policy_subtypes": policy_tags,
        "policy_validity_summary": policy_summary,
        "certified_product_types": certified_types,
        "certified_product_summary": _parse_summary(d.get("certified_product_summary_raw")),
        "shopping_mall_flags": shopping_flags,
        "shopping_mall_product_summary": _parse_summary(d.get("shopping_mall_product_summary_raw")),
        "mas_product_summary": _parse_summary(d.get("mas_product_summary_raw")),
        "sme_competition_product": bool(d.get("is_sme_competition_product")),
        "manufacturer_type": d.get("manufacturer_type") or "unknown",
        "business_status": d.get("business_status") or "unknown",
        "business_status_freshness": d.get("business_status_freshness") or "unknown",
        "display_status": d.get("display_status") or "후보",
        "contract_possible_auto_promoted": False,
        "source_refs": _json_or_list(d.get("source_refs"), ["company_master"]),
        "source_refreshed_at": d.get("source_refreshed_at"),
    }


def _terms(query: str, search_type: str) -> list[str]:
    text = " ".join(str(query or "").strip().split())
    compact = text.replace(" ", "").lower()
    terms = [text] if text else []
    if search_type in {"product", "shopping_mall", "certified_product", "innovation_product", "excellent_procurement_product"}:
        terms.extend(_PRODUCT_ALIASES.get(compact, []))
    seen = []
    for term in terms:
        if term and term not in seen:
            seen.append(term)
    return seen


def _response(rows: list[sqlite3.Row], *, query: dict[str, Any], source: str, validity_filter: str = "valid_only") -> dict[str, Any]:
    candidates = [_row_to_candidate(row, validity_filter=validity_filter) for row in rows]
    counts: dict[str, int] = {}
    source_refreshed_at: dict[str, str] = {}
    for c in candidates:
        for typ in c.get("candidate_types", []):
            counts[typ] = counts.get(typ, 0) + 1
        for ref in c.get("source_refs", []):
            if c.get("source_refreshed_at"):
                source_refreshed_at[str(ref)] = str(c["source_refreshed_at"])
    return {
        "meta": {
            "query": query,
            "candidate_counts_by_type": counts,
            "source_refreshed_at": source_refreshed_at,
            "source": source,
        },
        "candidates": candidates,
        "company_source_status": "cached_daily",
        "company_source_status_user_label": "내부 업체 DB VIEW 직접 조회",
        "company_cache_mode": "local_view_db",
        "company_cache_used": True,
        "company_search_status": "success",
    }


def _like_where(columns: list[str], terms: list[str]) -> tuple[str, list[str]]:
    clauses = []
    params: list[str] = []
    for term in terms:
        like = f"%{term}%"
        sub = []
        for col in columns:
            sub.append(f"IFNULL({col}, '') LIKE ?")
            params.append(like)
        clauses.append("(" + " OR ".join(sub) + ")")
    if not clauses:
        return "1=0", []
    return "(" + " OR ".join(clauses) + ")", params


def _run_search(where: str, params: list[Any], *, limit: int = 20, validity_filter: str = "valid_only", query: dict[str, Any], source: str) -> dict[str, Any] | None:
    conn = _connect()
    if conn is None:
        return None
    try:
        sql = f"""
            SELECT *
            FROM chatbot_company_candidate_view
            WHERE {where}
            ORDER BY
                CASE WHEN business_status = 'active' THEN 0 ELSE 1 END,
                CASE WHEN shopping_mall_flags_raw IS NOT NULL AND shopping_mall_flags_raw != '' THEN 0 ELSE 1 END,
                company_name
            LIMIT ?
        """
        rows = conn.execute(sql, [*params, int(limit)]).fetchall()
        return _response(rows, query=query, source=source, validity_filter=validity_filter)
    except Exception:
        return None
    finally:
        conn.close()


def search_by_product(query: str, *, limit: int = 20) -> dict[str, Any] | None:
    terms = _terms(query, "product")
    where, params = _like_where(
        ["main_products", "shopping_mall_product_summary_raw", "mas_product_summary_raw", "certified_product_summary_raw"],
        terms,
    )
    return _run_search(where, params, limit=limit, query={"product_name": query, "limit": limit}, source="local_view_product")


def search_by_license(query: str, *, limit: int = 20) -> dict[str, Any] | None:
    terms = _terms(query, "license")
    where, params = _like_where(["license_or_business_type", "main_products"], terms)
    return _run_search(where, params, limit=limit, query={"license_name": query, "limit": limit}, source="local_view_license")


def search_by_policy(policy_subtype: str, *, limit: int = 20) -> dict[str, Any] | None:
    mapped = _POLICY_ALIASES.get(policy_subtype, _POLICY_ALIASES.get(str(policy_subtype).replace(" ", "").lower(), policy_subtype))
    where = "IFNULL(policy_subtypes_raw, '') LIKE ?"
    return _run_search(where, [f"%{mapped}%"], limit=limit, query={"policy_subtype": mapped, "limit": limit}, source="local_view_policy")


def search_shopping_mall_product(product_name: str, *, limit: int = 20) -> dict[str, Any] | None:
    terms = _terms(product_name, "shopping_mall")
    where, params = _like_where(["shopping_mall_product_summary_raw", "mas_product_summary_raw", "main_products"], terms)
    where = f"({where}) AND IFNULL(shopping_mall_flags_raw, '') != ''"
    return _run_search(where, params, limit=limit, query={"product_name": product_name, "limit": limit}, source="local_view_shopping_mall")


def search_shopping_mall_supplier(company_keyword: str, *, limit: int = 20) -> dict[str, Any] | None:
    where, params = _like_where(["company_name"], _terms(company_keyword, "supplier"))
    where = f"({where}) AND IFNULL(shopping_mall_flags_raw, '') != ''"
    return _run_search(where, params, limit=limit, query={"company_keyword": company_keyword, "limit": limit}, source="local_view_shopping_mall_supplier")


def search_certified_product(product_name: str, *, certification_type: str = "", limit: int = 20) -> dict[str, Any] | None:
    terms = _terms(product_name, "certified_product")
    where, params = _like_where(["certified_product_summary_raw", "certified_product_types_raw", "main_products"], terms)
    if certification_type:
        where = f"({where}) AND IFNULL(certified_product_types_raw, '') LIKE ?"
        params.append(f"%{certification_type}%")
    return _run_search(where, params, limit=limit, query={"product_name": product_name, "certification_type": certification_type, "limit": limit}, source="local_view_certified")


def search_innovation_product(product_name: str, *, limit: int = 20) -> dict[str, Any] | None:
    terms = _terms(product_name, "innovation_product")
    where, params = _like_where(["certified_product_summary_raw", "main_products"], terms)
    where = f"({where}) AND IFNULL(certified_product_types_raw, '') LIKE '%innovation%'"
    return _run_search(where, params, limit=limit, query={"product_name": product_name, "limit": limit}, source="local_view_innovation")


def search_excellent_procurement_product(product_name: str, *, limit: int = 20) -> dict[str, Any] | None:
    terms = _terms(product_name, "excellent_procurement_product")
    where, params = _like_where(["certified_product_summary_raw", "shopping_mall_product_summary_raw", "main_products"], terms)
    where = f"({where}) AND (IFNULL(certified_product_types_raw, '') LIKE '%excellent%' OR IFNULL(shopping_mall_flags_raw, '') LIKE '%excellent%')"
    return _run_search(where, params, limit=limit, query={"product_name": product_name, "limit": limit}, source="local_view_excellent")


def get_company_detail(company_id: str) -> dict[str, Any] | None:
    conn = _connect()
    if conn is None:
        return None
    try:
        row = conn.execute(
            "SELECT * FROM chatbot_company_candidate_view WHERE company_id = ? LIMIT 1",
            (company_id,),
        ).fetchone()
        if not row:
            return None
        return _response([row], query={"company_id": company_id}, source="local_view_detail")
    except Exception:
        return None
    finally:
        conn.close()
