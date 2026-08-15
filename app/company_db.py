"""
Read-only local access to chatbot_company.db.

The monitoring system already builds a consolidated SQLite DB and exposes
chatbot_company_candidate_view. Advisor should use that local VIEW first and
fall back to HTTP only when the DB is missing or stale.
"""
from __future__ import annotations

import json
import os
import re
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
    "보안캠": ["CCTV", "영상감시장치", "보안용카메라", "CCTV카메라"],
    "보안용카메라": ["CCTV", "영상감시장치", "CCTV카메라"],
    "감시카메라": ["CCTV", "영상감시장치", "CCTV카메라"],
    "영상감시장치": ["CCTV", "영상감시장치", "CCTV카메라"],
    "비디오프로젝터": ["비디오프로젝터", "빔프로젝터", "빔프로젝트", "프로젝터", "슬라이드프로젝터"],
    "빔프로젝터": ["비디오프로젝터", "빔프로젝터", "빔프로젝트", "프로젝터", "슬라이드프로젝터"],
    "빔프로젝트": ["비디오프로젝터", "빔프로젝터", "빔프로젝트", "프로젝터", "슬라이드프로젝터"],
    "프로젝터": ["비디오프로젝터", "빔프로젝터", "빔프로젝트", "프로젝터", "슬라이드프로젝터"],
    "스텐밴드": ["스텐밴드", "스테인리스밴드", "스텐레스밴드", "스테인레스밴드", "스테인리스 밴드", "스텐 밴드"],
    "스테인리스밴드": ["스텐밴드", "스테인리스밴드", "스텐레스밴드", "스테인레스밴드", "스테인리스 밴드"],
    "스텐레스밴드": ["스텐밴드", "스테인리스밴드", "스텐레스밴드", "스테인레스밴드"],
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
    conn = sqlite3.connect(f"file:{path}?mode=ro&immutable=1", uri=True, timeout=1.0)
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


def _parse_construction_capacity_summary(raw: Any) -> list[dict[str, Any]]:
    rows = []
    for part in str(raw or "").split("|||"):
        if not part.strip():
            continue
        fields = part.split("^^")
        rows.append({
            "license_name": fields[0].strip() if len(fields) > 0 else "",
            "construction_capacity_amount": fields[1].strip() if len(fields) > 1 else "",
            "source": fields[2].strip() if len(fields) > 2 else "",
        })
    return rows


def _parse_venture_nara_product_summary(raw: Any) -> list[dict[str, Any]]:
    rows = []
    for part in str(raw or "").split("|||"):
        if not part.strip():
            continue
        fields = part.split("^^")
        rows.append({
            "product_name": fields[0].strip() if len(fields) > 0 else "",
            "category_name": fields[1].strip() if len(fields) > 1 else "",
            "valid_until": fields[2].strip() if len(fields) > 2 else "",
            "venture_company_marked": fields[3].strip() if len(fields) > 3 else "",
            "source": fields[4].strip() if len(fields) > 4 else "",
        })
    return rows


def _parse_venture_nara_order_summary(raw: Any) -> list[dict[str, Any]]:
    rows = []
    for part in str(raw or "").split("|||"):
        if not part.strip():
            continue
        fields = part.split("^^")
        rows.append({
            "detail_product_name": fields[0].strip() if len(fields) > 0 else "",
            "order_count": fields[1].strip() if len(fields) > 1 else "",
            "total_amount": fields[2].strip() if len(fields) > 2 else "",
            "last_order_date": fields[3].strip() if len(fields) > 3 else "",
            "source": fields[4].strip() if len(fields) > 4 else "",
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
    construction_capacity = _parse_construction_capacity_summary(d.get("construction_capacity_summary_raw"))
    venture_nara_products = _parse_venture_nara_product_summary(d.get("venture_nara_product_summary_raw"))
    venture_nara_orders = _parse_venture_nara_order_summary(d.get("venture_nara_order_summary_raw"))
    candidate_types = _json_or_list(d.get("candidate_types"), ["local_procurement_company"])
    if policy_tags and "policy_company" not in candidate_types:
        candidate_types.append("policy_company")
    if shopping_flags and "shopping_mall_supplier" not in candidate_types:
        candidate_types.append("shopping_mall_supplier")
    if certified_types and "certified_product" not in candidate_types:
        candidate_types.append("certified_product")
    if construction_capacity and "construction_capacity_verified" not in candidate_types:
        candidate_types.append("construction_capacity_verified")
    if venture_nara_products and "venture_nara_supplier" not in candidate_types:
        candidate_types.append("venture_nara_supplier")
    if venture_nara_orders and "venture_nara_order_history" not in candidate_types:
        candidate_types.append("venture_nara_order_history")

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
        "direct_production_summary": _parse_summary(d.get("direct_production_summary_raw")),
        "construction_capacity_summary": construction_capacity,
        "venture_nara_product_summary": venture_nara_products,
        "venture_nara_order_summary": venture_nara_orders,
        "direct_production_flags": _split_pipe(d.get("direct_production_flags_raw")),
        "procurement_attributes": _split_pipe(d.get("procurement_attributes_raw")),
        "general_certifications": _split_pipe(d.get("general_certifications_raw")),
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


def _object_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE name = ? AND type IN ('table', 'view') LIMIT 1",
        (name,),
    ).fetchone()
    return row is not None


def _preferred_object(conn: sqlite3.Connection, preferred: str, fallback: str) -> str | None:
    """Return a materialized search table when present, otherwise the canonical view.

    product_policy_summary and pps_shopping_mall_item_policy_summary are views
    backed by several aggregate joins. They are correct as canonical definitions,
    but too slow for interactive dashboard search. The monitoring pipeline can
    materialize *_fast tables in the same read-only snapshot; use them first and
    keep the view fallback for older DB snapshots.
    """
    if _object_exists(conn, preferred):
        return preferred
    if _object_exists(conn, fallback):
        return fallback
    return None


def _columns(conn: sqlite3.Connection, name: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({name})").fetchall()}


def _select_expr(column: str, available: set[str]) -> str:
    if column in available:
        return column
    return f"NULL AS {column}"


_PRODUCT_POLICY_COLUMNS = [
    "detail_product_code",
    "detail_product_name",
    "is_sme_competition_product",
    "is_construction_material_direct_purchase",
    "required_special_note",
    "construction_material_note",
    "eligible_coop_count",
    "busan_eligible_coop_count",
    "busan_eligible_coops",
    "coop_joint_product_count",
    "busan_coop_joint_product_count",
    "busan_coop_joint_product_coops",
    "mas_active_supplier_count",
    "shopping_mall_active_supplier_count",
    "busan_company_product_count",
    "direct_production_valid_supplier_count",
    "source_refs",
    "generated_at",
]

_SHOPPING_MALL_ITEM_POLICY_COLUMNS = [
    "detail_product_code",
    "detail_product_name",
    "product_class_code",
    "product_class_name",
    "active_registered_count",
    "active_third_party_count",
    "active_mas_count",
    "active_general_unit_price_count",
    "active_excellent_procurement_count",
    "active_sme_competition_count",
    "active_supplier_count",
    "active_busan_supplier_count",
    "active_min_price_amount",
    "active_max_price_amount",
    "active_contract_types",
    "source_refreshed_at",
]


def _compact_item_text(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "")).lower()


def _item_selection_display_name(row: dict[str, Any]) -> str:
    return str(row.get("detail_product_name") or row.get("product_class_name") or row.get("canonical_name") or "").strip()


def _item_selection_display_code(row: dict[str, Any]) -> str:
    return str(row.get("detail_product_code") or row.get("dtil_prdct_clsfc_no") or row.get("classification_no") or "").strip()


def search_item_selection_options(keyword: str, *, limit: int = 12) -> dict[str, Any] | None:
    """Return concrete item options when the query is broader than one detail item.

    The vendor UI must not silently decide a broad word such as "컴퓨터" or
    "의자". This helper uses the item alias table, the G2B classification tree,
    and the shopping-mall item summary to surface selectable detail names.
    """
    text = " ".join(str(keyword or "").split())
    compact = _compact_item_text(text)
    if not compact:
        return None
    conn = _connect()
    if conn is None:
        return None

    bounded_limit = max(2, min(int(limit or 12), 20))
    options: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add_option(payload: dict[str, Any]) -> None:
        name = _item_selection_display_name(payload)
        code = _item_selection_display_code(payload)
        if not name:
            return
        key = code or _compact_item_text(name)
        if not key or key in seen:
            return
        seen.add(key)
        option = {
            "detail_product_code": code,
            "detail_product_name": name,
            "selection_query": name,
            "matched_policy_source": str(payload.get("matched_policy_source") or ""),
            "product_class_code": str(payload.get("product_class_code") or payload.get("prdct_clsfc_no") or ""),
            "product_class_name": str(payload.get("product_class_name") or ""),
            "active_registered_count": payload.get("active_registered_count") or 0,
            "active_third_party_count": payload.get("active_third_party_count") or 0,
            "active_mas_count": payload.get("active_mas_count") or 0,
            "active_supplier_count": payload.get("active_supplier_count") or 0,
            "active_busan_supplier_count": payload.get("active_busan_supplier_count") or 0,
            "active_contract_types": str(payload.get("active_contract_types") or ""),
        }
        options.append(option)

    def enrich_with_mall(option: dict[str, Any]) -> dict[str, Any]:
        if not _object_exists(conn, "pps_shopping_mall_item_policy_summary_fast") and not _object_exists(conn, "pps_shopping_mall_item_policy_summary"):
            return option
        table = _preferred_object(conn, "pps_shopping_mall_item_policy_summary_fast", "pps_shopping_mall_item_policy_summary")
        if not table:
            return option
        code = _item_selection_display_code(option)
        class_code = str(option.get("product_class_code") or option.get("prdct_clsfc_no") or "")
        name = _item_selection_display_name(option)
        clauses: list[str] = []
        params: list[Any] = []
        if code:
            clauses.append("IFNULL(detail_product_code, '') = ?")
            params.append(code)
            clauses.append("IFNULL(product_class_code, '') = ?")
            params.append(code[:8] if len(code) >= 8 else code)
        if class_code:
            clauses.append("IFNULL(product_class_code, '') = ?")
            params.append(class_code)
        if name:
            clauses.append("REPLACE(LOWER(IFNULL(detail_product_name, '')), ' ', '') = ?")
            params.append(_compact_item_text(name))
            clauses.append("REPLACE(LOWER(IFNULL(product_class_name, '')), ' ', '') = ?")
            params.append(_compact_item_text(name))
        if not clauses:
            return option
        sql = f"""
            SELECT
                COALESCE(NULLIF(detail_product_name, ''), product_class_name) AS detail_product_name,
                COALESCE(NULLIF(detail_product_code, ''), product_class_code) AS detail_product_code,
                product_class_code,
                product_class_name,
                active_registered_count,
                active_third_party_count,
                active_mas_count,
                active_general_unit_price_count,
                active_supplier_count,
                active_busan_supplier_count,
                active_contract_types,
                source_refreshed_at
            FROM {table}
            WHERE {' OR '.join(f'({clause})' for clause in clauses)}
            ORDER BY
                CAST(IFNULL(active_busan_supplier_count, 0) AS INTEGER) DESC,
                CAST(IFNULL(active_registered_count, 0) AS INTEGER) DESC,
                detail_product_name
            LIMIT 1
        """
        row = conn.execute(sql, params).fetchone()
        if row:
            enriched = dict(option)
            enriched.update({key: row[key] for key in row.keys()})
            source = str(enriched.get("matched_policy_source") or "")
            if "pps_shopping_mall_item_policy_summary" not in source:
                enriched["matched_policy_source"] = "+".join(
                    part for part in (source, "pps_shopping_mall_item_policy_summary") if part
                )
            return enriched
        return option

    try:
        exact_item_exists = False
        mall_table = _preferred_object(conn, "pps_shopping_mall_item_policy_summary_fast", "pps_shopping_mall_item_policy_summary")
        if mall_table:
            exact_item_exists = conn.execute(
                f"""
                SELECT 1
                FROM {mall_table}
                WHERE REPLACE(LOWER(IFNULL(detail_product_name, '')), ' ', '') = ?
                   OR REPLACE(LOWER(IFNULL(product_class_name, '')), ' ', '') = ?
                LIMIT 1
                """,
                (compact, compact),
            ).fetchone() is not None

        if _object_exists(conn, "procurement_product_alias"):
            alias_rows = conn.execute(
                """
                SELECT
                    canonical_name,
                    dtil_prdct_clsfc_no,
                    prdct_clsfc_no,
                    domain,
                    MAX(priority) AS priority,
                    'procurement_product_alias' AS matched_policy_source
                FROM procurement_product_alias
                WHERE IFNULL(is_active, 1) = 1
                  AND (
                    alias_normalized = ?
                    OR REPLACE(LOWER(IFNULL(alias, '')), ' ', '') = ?
                  )
                GROUP BY canonical_name, dtil_prdct_clsfc_no, prdct_clsfc_no, domain
                ORDER BY CAST(MAX(priority) AS INTEGER) DESC, canonical_name
                LIMIT ?
                """,
                (compact, compact, bounded_limit * 2),
            ).fetchall()
            distinct_alias_names = {
                _compact_item_text(row["canonical_name"])
                for row in alias_rows
                if str(row["canonical_name"] or "").strip()
            }
            if len(distinct_alias_names) >= 2:
                for row in alias_rows:
                    add_option(enrich_with_mall(dict(row)))

        if len(options) < bounded_limit and _object_exists(conn, "procurement_product_classification"):
            parent_rows = conn.execute(
                """
                SELECT classification_no, classification_unit, classification_name
                FROM procurement_product_classification
                WHERE IFNULL(use_yn, 'Y') = 'Y'
                  AND classification_unit <= 6
                  AND REPLACE(LOWER(IFNULL(classification_name, '')), ' ', '') = ?
                ORDER BY classification_unit DESC, classification_no
                LIMIT 3
                """,
                (compact,),
            ).fetchall()
            for parent in parent_rows:
                child_rows = conn.execute(
                    """
                    SELECT
                        classification_no,
                        classification_name,
                        parent_classification_no,
                        'procurement_product_classification' AS matched_policy_source
                    FROM procurement_product_classification
                    WHERE IFNULL(use_yn, 'Y') = 'Y'
                      AND parent_classification_no = ?
                      AND classification_unit > ?
                    ORDER BY classification_unit, classification_name
                    LIMIT ?
                    """,
                    (parent["classification_no"], parent["classification_unit"], bounded_limit * 2),
                ).fetchall()
                for row in child_rows:
                    payload = dict(row)
                    payload["detail_product_code"] = payload.get("classification_no")
                    payload["detail_product_name"] = payload.get("classification_name")
                    payload["product_class_code"] = payload.get("classification_no")
                    payload["product_class_name"] = payload.get("classification_name")
                    add_option(enrich_with_mall(payload))
                    if len(options) >= bounded_limit:
                        break

        if len(options) < 2 and mall_table and not exact_item_exists:
            rows = conn.execute(
                f"""
                SELECT
                    COALESCE(NULLIF(detail_product_name, ''), product_class_name) AS detail_product_name,
                    COALESCE(NULLIF(detail_product_code, ''), product_class_code) AS detail_product_code,
                    product_class_code,
                    product_class_name,
                    active_registered_count,
                    active_third_party_count,
                    active_mas_count,
                    active_general_unit_price_count,
                    active_supplier_count,
                    active_busan_supplier_count,
                    active_contract_types,
                    source_refreshed_at,
                    'pps_shopping_mall_item_policy_summary' AS matched_policy_source
                FROM {mall_table}
                WHERE IFNULL(detail_product_name, '') LIKE ?
                   OR IFNULL(product_class_name, '') LIKE ?
                ORDER BY
                    CAST(IFNULL(active_busan_supplier_count, 0) AS INTEGER) DESC,
                    CAST(IFNULL(active_registered_count, 0) AS INTEGER) DESC,
                    detail_product_name
                LIMIT ?
                """,
                (f"%{text}%", f"%{text}%", bounded_limit),
            ).fetchall()
            for row in rows:
                add_option(dict(row))

        if len(options) < 2:
            return None
        return {
            "status": "needs_item_selection",
            "query": text,
            "selection_required": True,
            "selection_title": f"{text} 세부품명 선택 필요",
            "message": (
                f"'{text}'만으로는 세부품명을 하나로 확정할 수 없습니다. "
                "실제 구매하려는 세부품명을 선택한 뒤 품목정책과 부산업체 후보를 다시 판정해야 합니다."
            ),
            "selection_options": options[:bounded_limit],
            "meta": {
                "keyword": text,
                "source": "procurement_product_alias/procurement_product_classification/pps_shopping_mall_item_policy_summary",
                "cache_mode": "local_view_db",
            },
        }
    except Exception:
        return None
    finally:
        conn.close()


def search_facility_material_policy(keyword: str, *, limit: int = 5) -> dict[str, Any] | None:
    """Read facility material price dictionary facts.

    This table is a product/purchase-suitability signal, not a company
    candidate source. It helps the API explain that the item appears in the
    G2B facility material price-info file when product_policy_summary has no
    exact policy row.
    """
    text = " ".join(str(keyword or "").split())
    if not text:
        return None
    conn = _connect()
    if conn is None:
        return None
    try:
        table_name = "facility_material_item_dictionary"
        if not _object_exists(conn, table_name):
            return None
        available = _columns(conn, table_name)
        search_columns = [
            col
            for col in (
                "search_text",
                "korean_product_name",
                "product_classification_name",
                "product_classification_no",
                "product_identifier_no",
            )
            if col in available
        ]
        if "korean_product_name" not in available or not search_columns:
            return None
        terms = _terms(text, "product")
        where, params = _like_where(search_columns, terms)
        select_sql = """
            product_classification_no AS detail_product_code,
            korean_product_name AS detail_product_name,
            product_identifier_no AS product_identifier_no,
            product_classification_name AS product_classification_name,
            portal_price_business_types AS facility_material_categories,
            units AS facility_material_units,
            active_price_count AS facility_material_active_price_count,
            historical_row_count AS facility_material_historical_row_count,
            latest_posted_date AS facility_material_latest_posted_date,
            min_active_price_amount AS facility_material_min_price_amount,
            max_active_price_amount AS facility_material_max_price_amount,
            'facility_material_price_file' AS matched_policy_source,
            1 AS is_facility_material_price_item,
            '시설공통자재 가격정보 파일에 등록된 품목입니다. 현재 가격 유효 여부와 조달 구매수단은 공고 또는 계약 전 별도 확인이 필요합니다.' AS required_special_note
        """
        sql = f"""
            SELECT {select_sql}
            FROM {table_name}
            WHERE {where}
            ORDER BY
                CASE
                    WHEN IFNULL(korean_product_name, '') = ? THEN 0
                    WHEN IFNULL(korean_product_name, '') LIKE ? THEN 1
                    ELSE 2
                END,
                CAST(IFNULL(active_price_count, 0) AS INTEGER) DESC,
                IFNULL(latest_posted_date, '') DESC,
                korean_product_name
            LIMIT ?
        """
        rows = conn.execute(sql, [*params, text, f"{text}%", max(1, min(int(limit or 5), 20))]).fetchall()
        return {
            "meta": {
                "keyword": text,
                "limit": max(1, min(int(limit or 5), 20)),
                "source": table_name,
                "cache_mode": "local_view_db",
            },
            "candidates": [dict(row) for row in rows],
            "company_cache_used": True,
            "company_cache_mode": "local_view_db",
            "company_search_status": "success",
        }
    except Exception:
        return None
    finally:
        conn.close()


def _company_item_evidence_terms(terms: list[str]) -> list[str]:
    cleaned: list[str] = []
    for term in terms or []:
        text = " ".join(str(term or "").split())
        if not text:
            continue
        if len(text) > 80:
            continue
        if text not in cleaned:
            cleaned.append(text)
    return cleaned[:20]


def _company_item_evidence_code_term(term: str) -> bool:
    return bool(re.fullmatch(r"[0-9A-Za-z][0-9A-Za-z\-]{3,24}", str(term or "").strip()))


def _company_item_evidence_where(columns: list[str], terms: list[str]) -> tuple[str, list[Any]]:
    parts: list[str] = []
    params: list[Any] = []
    for term in terms:
        code_like = _company_item_evidence_code_term(term)
        if code_like:
            target_columns = [col for col in columns if "code" in col.lower()]
            if not target_columns:
                target_columns = columns
        else:
            target_columns = columns
        like = f"%{term}%"
        term_parts: list[str] = []
        for col in target_columns:
            if code_like and len(str(term).strip()) >= 9:
                term_parts.append(f"IFNULL({col}, '') = ?")
                params.append(term)
            else:
                term_parts.append(f"IFNULL({col}, '') LIKE ?")
                params.append(like)
        parts.append("(" + " OR ".join(term_parts) + ")")
    if not parts:
        return "1=0", []
    return "(" + " OR ".join(parts) + ")", params


def search_company_item_evidence(
    company_ids: list[str],
    terms: list[str],
    *,
    limit_per_company: int = 5,
) -> dict[str, dict[str, list[dict[str, Any]]]] | None:
    """Return row-level procurement evidence for requested companies/items.

    Candidate rows come from chatbot_company_candidate_view, but direct
    production certificates are stored in a separate table and MAS/shopping
    rows have richer per-item fields than the view summaries. This helper joins
    those source tables back by company_id and requested item terms.
    """
    ids = [str(company_id).strip() for company_id in company_ids or [] if str(company_id).strip()]
    ids = list(dict.fromkeys(ids))[:100]
    search_terms = _company_item_evidence_terms(terms)
    if not ids or not search_terms:
        return {}
    conn = _connect()
    if conn is None:
        return None
    result: dict[str, dict[str, list[dict[str, Any]]]] = {
        company_id: {"direct_production": [], "shopping_mall": [], "mas": []}
        for company_id in ids
    }
    try:
        id_placeholders = ",".join("?" for _ in ids)

        def add_rows(source_key: str, sql: str, params: list[Any]) -> None:
            per_company_counts: dict[str, int] = {}
            for row in conn.execute(sql, params):
                item = dict(row)
                company_id = str(item.pop("company_id", "") or "")
                if not company_id or company_id not in result:
                    continue
                count = per_company_counts.get(company_id, 0)
                if count >= max(1, min(int(limit_per_company or 5), 20)):
                    continue
                per_company_counts[company_id] = count + 1
                result[company_id][source_key].append(item)

        if _object_exists(conn, "company_identity") and _object_exists(conn, "direct_production_certificate"):
            where, where_params = _company_item_evidence_where(
                ["d.detail_product_name", "d.detail_product_name_normalized", "d.detail_product_code"],
                search_terms,
            )
            sql = f"""
                SELECT
                    ci.company_id,
                    d.detail_product_name AS product_name,
                    d.detail_product_code AS detail_product_code,
                    d.validity_status AS status,
                    d.valid_from AS valid_from,
                    d.valid_to AS valid_to,
                    d.source_name AS source,
                    d.source_refreshed_at AS source_refreshed_at
                FROM direct_production_certificate d
                JOIN company_identity ci ON ci.company_internal_id = d.company_internal_id
                WHERE ci.company_id IN ({id_placeholders})
                  AND ({where})
                  AND IFNULL(d.validity_status, '') IN ('valid', 'unknown', '')
                ORDER BY
                    ci.company_id,
                    CASE WHEN IFNULL(d.validity_status, '') = 'valid' THEN 0 ELSE 1 END,
                    IFNULL(d.valid_to, '') DESC,
                    d.detail_product_name
            """
            add_rows("direct_production", sql, [*ids, *where_params])

        if _object_exists(conn, "company_identity") and _object_exists(conn, "shopping_mall_product"):
            where, where_params = _company_item_evidence_where(
                ["s.product_name", "s.product_name_normalized", "s.detail_product_name", "s.product_code", "s.detail_product_code"],
                search_terms,
            )
            sql = f"""
                SELECT
                    ci.company_id,
                    s.product_name AS product_name,
                    s.detail_product_name AS detail_product_name,
                    s.product_code AS product_code,
                    s.detail_product_code AS detail_product_code,
                    s.shopping_mall_contract_type AS contract_type,
                    s.contract_status AS status,
                    s.contract_start_date AS contract_start_date,
                    s.contract_end_date AS contract_end_date,
                    s.order_path_available AS order_path_available,
                    s.price_amount AS price_amount,
                    s.price_unit AS price_unit,
                    s.source_name AS source,
                    s.source_refreshed_at AS source_refreshed_at
                FROM shopping_mall_product s
                JOIN company_identity ci ON ci.company_internal_id = s.company_internal_id
                WHERE ci.company_id IN ({id_placeholders})
                  AND ({where})
                  AND IFNULL(s.contract_status, '') IN ('active', 'unknown', '')
                ORDER BY
                    ci.company_id,
                    CASE WHEN IFNULL(s.contract_status, '') = 'active' THEN 0 ELSE 1 END,
                    IFNULL(s.contract_end_date, '') DESC,
                    s.detail_product_name,
                    s.product_name
            """
            add_rows("shopping_mall", sql, [*ids, *where_params])

        if _object_exists(conn, "company_identity") and _object_exists(conn, "mas_product"):
            where, where_params = _company_item_evidence_where(
                ["m.product_name", "m.product_name_normalized", "m.detail_product_name", "m.product_code", "m.detail_product_code"],
                search_terms,
            )
            sql = f"""
                SELECT
                    ci.company_id,
                    m.product_name AS product_name,
                    m.detail_product_name AS detail_product_name,
                    m.product_code AS product_code,
                    m.detail_product_code AS detail_product_code,
                    m.contract_status AS status,
                    m.contract_start_date AS contract_start_date,
                    m.contract_end_date AS contract_end_date,
                    m.price_amount AS price_amount,
                    m.price_unit AS price_unit,
                    m.source_name AS source,
                    m.source_refreshed_at AS source_refreshed_at
                FROM mas_product m
                JOIN company_identity ci ON ci.company_internal_id = m.company_internal_id
                WHERE ci.company_id IN ({id_placeholders})
                  AND ({where})
                  AND IFNULL(m.contract_status, '') IN ('active', 'unknown', '')
                ORDER BY
                    ci.company_id,
                    CASE WHEN IFNULL(m.contract_status, '') = 'active' THEN 0 ELSE 1 END,
                    IFNULL(m.contract_end_date, '') DESC,
                    m.detail_product_name,
                    m.product_name
            """
            add_rows("mas", sql, [*ids, *where_params])

        return result
    except Exception:
        return None
    finally:
        conn.close()


def search_product_policy(keyword: str, *, limit: int = 5) -> dict[str, Any] | None:
    """Read product policy facts from product_policy_summary only.

    This is intentionally limited to the fixed product_policy_summary table/view.
    It returns None when the DB, object, or required columns are unavailable so
    callers can decide whether to use a fallback API.
    """
    text = " ".join(str(keyword or "").split())
    if not text:
        return None
    conn = _connect()
    if conn is None:
        return None
    try:
        view_name = _preferred_object(conn, "product_policy_summary_fast", "product_policy_summary")
        if not view_name:
            return None
        available = _columns(conn, view_name)
        search_columns = [
            col
            for col in ("detail_product_name", "detail_product_code", "required_special_note")
            if col in available
        ]
        if "detail_product_name" not in available or not search_columns:
            return None
        terms = _terms(text, "product")
        where, params = _like_where(search_columns, terms)
        select_sql = ", ".join(_select_expr(col, available) for col in _PRODUCT_POLICY_COLUMNS)
        order_parts = [
            "CASE WHEN IFNULL(detail_product_name, '') = ? THEN 0 WHEN IFNULL(detail_product_name, '') LIKE ? THEN 1 ELSE 2 END",
        ]
        order_params: list[Any] = [text, f"{text}%"]
        if "is_sme_competition_product" in available:
            order_parts.append("CAST(IFNULL(is_sme_competition_product, 0) AS INTEGER) DESC")
        if "direct_production_valid_supplier_count" in available:
            order_parts.append("CAST(IFNULL(direct_production_valid_supplier_count, 0) AS INTEGER) DESC")
        if "busan_company_product_count" in available:
            order_parts.append("CAST(IFNULL(busan_company_product_count, 0) AS INTEGER) DESC")
        order_parts.append("detail_product_name")
        sql = f"""
            SELECT {select_sql}
            FROM {view_name}
            WHERE {where}
            ORDER BY {', '.join(order_parts)}
            LIMIT ?
        """
        rows = conn.execute(sql, [*params, *order_params, max(1, min(int(limit or 5), 20))]).fetchall()
        return {
            "meta": {
                "keyword": text,
                "limit": max(1, min(int(limit or 5), 20)),
                "source": view_name,
                "cache_mode": "local_view_db",
            },
            "candidates": [dict(row) for row in rows],
            "company_cache_used": True,
            "company_cache_mode": "local_view_db",
            "company_search_status": "success",
        }
    except Exception:
        return None
    finally:
        conn.close()


def search_shopping_mall_item_policy(keyword: str, *, limit: int = 5) -> dict[str, Any] | None:
    """Read national shopping-mall item contract facts.

    This is item-level evidence. It answers whether the product itself appears
    in the G2B shopping-mall contract master as third-party unit price, MAS, or
    general unit price. It is intentionally separate from Busan supplier rows.
    """
    text = " ".join(str(keyword or "").split())
    if not text:
        return None
    conn = _connect()
    if conn is None:
        return None
    try:
        view_name = _preferred_object(conn, "pps_shopping_mall_item_policy_summary_fast", "pps_shopping_mall_item_policy_summary")
        if not view_name:
            return None
        available = _columns(conn, view_name)
        search_columns = [
            col
            for col in (
                "detail_product_name",
                "detail_product_code",
                "product_class_name",
                "product_class_code",
                "active_contract_types",
            )
            if col in available
        ]
        if "detail_product_name" not in available or not search_columns:
            return None
        terms = _terms(text, "shopping_mall")
        where, params = _like_where(search_columns, terms)
        select_parts: list[str] = []
        for col in _SHOPPING_MALL_ITEM_POLICY_COLUMNS:
            if col == "detail_product_name" and "detail_product_name" in available and "product_class_name" in available:
                select_parts.append("COALESCE(NULLIF(detail_product_name, ''), product_class_name) AS detail_product_name")
            else:
                select_parts.append(_select_expr(col, available))
        select_sql = ", ".join(select_parts)
        if "product_class_name" in available:
            order_parts = [
                """
                CASE
                    WHEN IFNULL(detail_product_name, '') = ? OR IFNULL(product_class_name, '') = ? THEN 0
                    WHEN IFNULL(detail_product_name, '') LIKE ? OR IFNULL(product_class_name, '') LIKE ? THEN 1
                    ELSE 2
                END
                """,
            ]
            order_params: list[Any] = [text, text, f"{text}%", f"{text}%"]
        else:
            order_parts = [
                "CASE WHEN IFNULL(detail_product_name, '') = ? THEN 0 WHEN IFNULL(detail_product_name, '') LIKE ? THEN 1 ELSE 2 END",
            ]
            order_params = [text, f"{text}%"]
        for count_col in (
            "active_third_party_count",
            "active_mas_count",
            "active_registered_count",
            "active_busan_supplier_count",
            "active_supplier_count",
        ):
            if count_col in available:
                order_parts.append(f"CAST(IFNULL({count_col}, 0) AS INTEGER) DESC")
        order_parts.append("detail_product_name")
        sql = f"""
            SELECT {select_sql}
            FROM {view_name}
            WHERE {where}
            ORDER BY {', '.join(order_parts)}
            LIMIT ?
        """
        bounded_limit = max(1, min(int(limit or 5), 20))
        rows = conn.execute(sql, [*params, *order_params, bounded_limit]).fetchall()
        return {
            "meta": {
                "keyword": text,
                "limit": bounded_limit,
                "source": view_name,
                "cache_mode": "local_view_db",
            },
            "candidates": [dict(row) for row in rows],
            "company_cache_used": True,
            "company_cache_mode": "local_view_db",
            "company_search_status": "success",
        }
    except Exception:
        return None
    finally:
        conn.close()


def search_by_product(query: str, *, limit: int = 20) -> dict[str, Any] | None:
    terms = _terms(query, "product")
    where, params = _like_where(
        [
            "main_products",
            "shopping_mall_product_summary_raw",
            "mas_product_summary_raw",
            "certified_product_summary_raw",
            "venture_nara_product_summary_raw",
            "venture_nara_order_summary_raw",
        ],
        terms,
    )
    return _run_search(where, params, limit=limit, query={"product_name": query, "limit": limit}, source="local_view_product")


def search_by_direct_production(query: str, *, limit: int = 20) -> dict[str, Any] | None:
    terms = _terms(query, "product")
    conn = _connect()
    if conn is None:
        return None
    try:
        if not (
            _object_exists(conn, "direct_production_certificate")
            and _object_exists(conn, "company_identity")
            and _object_exists(conn, "chatbot_company_candidate_view")
        ):
            return None
        where, params = _like_where(["d.detail_product_name"], terms)
        sql = f"""
            SELECT
                v.*,
                GROUP_CONCAT(
                    d.detail_product_name || '^^' ||
                    IFNULL(d.detail_product_code, '') || '^^direct_production^^' ||
                    IFNULL(d.validity_status, '') || '^^' ||
                    IFNULL(d.valid_to, '') || '^^' ||
                    IFNULL(d.source_name, ''),
                    '|||'
                ) AS direct_production_summary_raw
            FROM direct_production_certificate d
            JOIN company_identity ci
              ON ci.company_internal_id = d.company_internal_id
            JOIN chatbot_company_candidate_view v
              ON v.company_id = ci.company_id
            WHERE ({where})
              AND IFNULL(d.validity_status, '') IN ('valid', 'unknown', '')
              AND COALESCE(NULLIF(TRIM(LOWER(v.business_status)), ''), 'unknown')
                  NOT IN ('inactive', 'closed', 'suspended', '폐업', '휴업', '종료', 'cancelled', 'canceled')
            GROUP BY v.company_id
            ORDER BY
                CASE WHEN v.business_status = 'active' THEN 0 ELSE 1 END,
                COUNT(*) DESC,
                v.company_name
            LIMIT ?
        """
        rows = conn.execute(sql, [*params, int(limit)]).fetchall()
        return _response(rows, query={"product_name": query, "limit": limit}, source="local_view_direct_production")
    except Exception:
        return None
    finally:
        conn.close()


def search_by_license(query: str, *, limit: int = 20) -> dict[str, Any] | None:
    terms = _terms(query, "license")
    where, params = _like_where(["license_or_business_type", "construction_capacity_summary_raw", "main_products"], terms)
    return _run_search(where, params, limit=limit, query={"license_name": query, "limit": limit}, source="local_view_license")


def search_by_policy(policy_subtype: str, *, limit: int = 20) -> dict[str, Any] | None:
    mapped = _POLICY_ALIASES.get(policy_subtype, _POLICY_ALIASES.get(str(policy_subtype).replace(" ", "").lower(), policy_subtype))
    where = "IFNULL(policy_subtypes_raw, '') LIKE ?"
    return _run_search(where, [f"%{mapped}%"], limit=limit, query={"policy_subtype": mapped, "limit": limit}, source="local_view_policy")


def search_by_company_name(company_keyword: str, *, limit: int = 20) -> dict[str, Any] | None:
    where, params = _like_where(["company_name"], _terms(company_keyword, "supplier"))
    return _run_search(where, params, limit=limit, query={"company_keyword": company_keyword, "limit": limit}, source="local_view_company_name")


def search_shopping_mall_product(product_name: str, *, limit: int = 20) -> dict[str, Any] | None:
    terms = _terms(product_name, "shopping_mall")
    where, params = _like_where(["shopping_mall_product_summary_raw", "mas_product_summary_raw", "main_products"], terms)
    where = f"({where}) AND IFNULL(shopping_mall_flags_raw, '') != ''"
    primary = _run_search(where, params, limit=limit, query={"product_name": product_name, "limit": limit}, source="local_view_shopping_mall")
    primary_candidates = list((primary or {}).get("candidates") or [])
    source_candidates: list[dict[str, Any]] = []

    conn = _connect()
    if conn is None:
        return primary
    try:
        if not (
            _object_exists(conn, "chatbot_company_candidate_view")
            and _object_exists(conn, "company_identity")
            and (_object_exists(conn, "shopping_mall_product") or _object_exists(conn, "mas_product"))
        ):
            return primary

        seen: set[str] = set()
        source_sql_parts: list[str] = []
        source_params: list[Any] = []

        def add_source(table: str, alias: str, source_rank: int) -> None:
            if not _object_exists(conn, table):
                return
            source_where, source_where_params = _like_where(
                [
                    f"{alias}.product_name",
                    f"{alias}.product_name_normalized",
                    f"{alias}.detail_product_name",
                    f"{alias}.product_code",
                    f"{alias}.detail_product_code",
                ],
                terms,
            )
            source_sql_parts.append(
                f"""
                SELECT
                    ci.company_id,
                    {source_rank} AS source_rank,
                    CASE WHEN IFNULL({alias}.contract_status, '') = 'active' THEN 0 ELSE 1 END AS status_rank,
                    IFNULL({alias}.contract_end_date, '') AS contract_end_date,
                    IFNULL({alias}.detail_product_name, {alias}.product_name) AS matched_product_name
                FROM {table} {alias}
                JOIN company_identity ci ON ci.company_internal_id = {alias}.company_internal_id
                WHERE ({source_where})
                  AND IFNULL({alias}.contract_status, '') IN ('active', 'unknown', '')
                """
            )
            source_params.extend(source_where_params)

        add_source("shopping_mall_product", "s", 0)
        add_source("mas_product", "m", 1)
        if not source_sql_parts:
            return primary

        source_sql = " UNION ALL ".join(source_sql_parts)
        sql = f"""
            WITH source_matches AS (
                {source_sql}
            ),
            ranked AS (
                SELECT
                    company_id,
                    MIN(source_rank) AS source_rank,
                    MIN(status_rank) AS status_rank,
                    MAX(contract_end_date) AS contract_end_date,
                    COUNT(*) AS match_count
                FROM source_matches
                GROUP BY company_id
            )
            SELECT v.*
            FROM ranked r
            JOIN chatbot_company_candidate_view v ON v.company_id = r.company_id
            WHERE COALESCE(NULLIF(TRIM(LOWER(v.business_status)), ''), 'unknown')
                NOT IN ('inactive', 'closed', 'suspended', '폐업', '휴업', '종료', 'cancelled', 'canceled')
            ORDER BY
                r.source_rank,
                r.status_rank,
                r.match_count DESC,
                r.contract_end_date DESC,
                CASE WHEN v.business_status = 'active' THEN 0 ELSE 1 END,
                v.company_name
            LIMIT ?
        """
        rows = conn.execute(sql, [*source_params, max(1, min(int(limit or 20), 100))]).fetchall()
        for row in rows:
            candidate = _row_to_candidate(row)
            company_id = str(candidate.get("company_id") or "")
            if not company_id or company_id in seen:
                continue
            seen.add(company_id)
            source_candidates.append(candidate)
            if len(source_candidates) >= max(1, int(limit or 20)):
                break
        candidates = list(source_candidates)
        for candidate in primary_candidates:
            company_id = str(candidate.get("company_id") or "")
            if not company_id or company_id in seen:
                continue
            seen.add(company_id)
            candidates.append(candidate)
            if len(candidates) >= max(1, int(limit or 20)):
                break
        if not candidates:
            return primary
        response = primary or {
            "query": {"product_name": product_name, "limit": limit},
            "candidates": [],
            "company_source_status": "cached_daily",
            "company_source_status_user_label": "내부 업체 DB VIEW 직접 조회",
            "company_cache_mode": "local_view_db",
            "company_cache_used": True,
            "company_search_status": "success",
        }
        response["candidates"] = candidates[: max(1, int(limit or 20))]
        response["company_cache_used"] = True
        response["company_cache_mode"] = "local_view_db"
        response["company_search_status"] = "success"
        return response
    except Exception:
        return primary
    finally:
        conn.close()


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
