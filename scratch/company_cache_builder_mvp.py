"""
CacheBuilder MVP — Phase 11: Live API 최소 연동 검증
업체 Daily Cache 로컬 빌드 스크립트 (scratch용)

허용: page=1, size=5 단건 호출만 허용
금지: 전체 batch, 반복 호출, 서버 배포, cache_current 변경
Production deployment = HOLD
"""

import os
import json
import sqlite3
import hashlib
import hmac
import re
import time
import requests
from datetime import datetime, timezone

# ── .env 로딩 (dotenv 미설치 대비) ─────────────────────────────
WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILE = os.path.join(WORKSPACE_DIR, ".env")
if os.path.exists(ENV_FILE):
    with open(ENV_FILE, "r", encoding="utf-8") as _ef:
        for _line in _ef:
            _line = _line.strip()
            if not _line or _line.startswith("#") or "=" not in _line:
                continue
            _k, _v = _line.split("=", 1)
            _k = _k.strip()
            _v = _v.strip().strip('"').strip("'")
            if _k not in os.environ:
                os.environ[_k] = _v

# ── 환경변수 (기본값 없음) ──────────────────────────────────────
API_BASE_URL = os.getenv("MONITORING_API_BASE_URL")
API_KEY = os.getenv("MONITORING_API_KEY")
HASH_SECRET = os.getenv("COMPANY_HASH_SECRET")
MOCK_MODE = os.getenv("MOCK_MODE", "false").lower() == "true"

CACHE_DIR = os.path.join(WORKSPACE_DIR, "cache", "company", "cache_new")
MOCK_FILE = os.path.join(WORKSPACE_DIR, "scratch", "mock_company_records.json")


# ── 워크스페이스 준비 ──────────────────────────────────────────
def prepare_workspace():
    os.makedirs(CACHE_DIR, exist_ok=True)
    for fname in ["company_master_cache.sqlite", "manifest.json"]:
        p = os.path.join(CACHE_DIR, fname)
        if os.path.exists(p):
            os.remove(p)


# ── 데이터 수집 ────────────────────────────────────────────────
def fetch_page(page, size):
    """
    MOCK_MODE=true  → mock fixture 파일에서 로드
    MOCK_MODE=false → 실제 API 호출 (page=1, size=5 고정)

    반환: (data_dict, http_status, elapsed_ms)
    """
    if MOCK_MODE:
        with open(MOCK_FILE, "r", encoding="utf-8") as f:
            return json.load(f), 200, 0

    # ── Live API fetch ──
    if not API_BASE_URL:
        raise RuntimeError("MONITORING_API_BASE_URL is not set")
    if not API_KEY:
        raise RuntimeError("MONITORING_API_KEY is not set")

    url = f"{API_BASE_URL.rstrip('/')}/companies/busan"
    headers = {"X-API-KEY": API_KEY}
    params = {"page": page, "size": size}

    t0 = time.time()
    resp = requests.get(url, headers=headers, params=params, timeout=15)
    elapsed_ms = int((time.time() - t0) * 1000)

    resp.raise_for_status()
    return resp.json(), resp.status_code, elapsed_ms


def load_sources_limited():
    """page=1, size=5 단건 호출. 반복 호출 금지."""
    data, http_status, elapsed_ms = fetch_page(1, 5)
    return data, http_status, elapsed_ms


# ── businessNo canonicalization ────────────────────────────────
def canonicalize_business_no(raw_no: str):
    digits = re.sub(r"\D", "", raw_no or "")
    if not digits:
        return None
    if len(digits) != 10:
        raise ValueError(f"Invalid business number: expected 10 digits, got {len(digits)}")
    return digits


# ── HMAC (canonicalized value만 입력) ──────────────────────────
def make_internal_join_key(raw_no: str, secret: str):
    canonical_no = canonicalize_business_no(raw_no)
    if canonical_no is None:
        return None
    if not secret:
        raise RuntimeError("COMPANY_HASH_SECRET is required")
    return hmac.new(
        secret.encode("utf-8"),
        canonical_no.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


# ── normalize ──────────────────────────────────────────────────
def normalize_company_record(record):
    internal_join_key = make_internal_join_key(
        record.get("businessNo", ""), HASH_SECRET
    )
    if not internal_join_key:
        raise ValueError("Missing or invalid businessNo -> internal_join_key is None")

    return {
        "internal_join_key": internal_join_key,
        "company_name": record.get("companyName"),
        "location": record.get("address"),
        "address_region": record.get("regionCode"),
        "main_products_json": json.dumps(
            record.get("mainProducts", []), ensure_ascii=False
        ),
        "category_codes_json": json.dumps([], ensure_ascii=False),
        "license_or_business_type": json.dumps(
            record.get("bizTypes", []), ensure_ascii=False
        ),
        "procurement_registered": bool(record.get("registeredAt")),
        "business_status": record.get("status"),
        "source_refreshed_at": record.get("lastUpdatedAt"),
    }


# ── SQLite (NOT NULL) ──────────────────────────────────────────
def write_sqlite_cache(records):
    db_path = os.path.join(CACHE_DIR, "company_master_cache.sqlite")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE companies (
            internal_join_key TEXT PRIMARY KEY NOT NULL,
            company_name TEXT,
            location TEXT,
            address_region TEXT,
            main_products_json TEXT,
            category_codes_json TEXT,
            license_or_business_type TEXT,
            procurement_registered BOOLEAN,
            business_status TEXT,
            source_refreshed_at TEXT
        )
    """
    )
    cur.execute("CREATE INDEX idx_company_name ON companies(company_name)")
    cur.execute("CREATE INDEX idx_address_region ON companies(address_region)")
    cur.execute(
        "CREATE INDEX idx_license_or_business_type ON companies(license_or_business_type)"
    )

    inserted = 0
    for r in records:
        try:
            cur.execute(
                """
                INSERT INTO companies VALUES (
                    :internal_join_key, :company_name, :location, :address_region,
                    :main_products_json, :category_codes_json, :license_or_business_type,
                    :procurement_registered, :business_status, :source_refreshed_at
                )
            """,
                r,
            )
            inserted += 1
        except sqlite3.IntegrityError:
            raise ValueError("Duplicate internal_join_key detected")
    conn.commit()
    conn.close()
    return db_path, inserted


# ── validate_cache ─────────────────────────────────────────────
def validate_cache(db_path):
    errors = []
    if not os.path.exists(db_path):
        errors.append("SQLite file missing")
        return "FAIL", errors

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM companies")
    count = cur.fetchone()[0]
    if count == 0:
        errors.append("row_count is 0")

    cur.execute("PRAGMA table_info(companies)")
    cols = [c[1].lower() for c in cur.fetchall()]
    for fc in ["businessno", "biz_no", "representative", "phone", "email", "servicekey", "token"]:
        if fc in cols:
            errors.append(f"Forbidden column: {fc}")

    cur.execute("SELECT internal_join_key FROM companies LIMIT 10")
    for k in cur.fetchall():
        if not k[0] or len(k[0]) < 64:
            errors.append("invalid internal_join_key")

    conn.close()

    with open(db_path, "rb") as f:
        content_str = f.read().decode("utf-8", errors="ignore")

    if re.search(r"\d{3}-\d{2}-\d{5}", content_str):
        errors.append("Raw business number pattern (XXX-XX-XXXXX) in DB")
    if re.search(r"\b\d{10}\b", content_str):
        errors.append("Contiguous 10-digit number in DB")
    if "representative" in content_str.lower():
        errors.append("representative string in DB")
    if re.search(r"\b0\d{1,2}-\d{3,4}-\d{4}\b", content_str):
        errors.append("Phone pattern in DB")
    if re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", content_str):
        errors.append("Email pattern in DB")
    if API_KEY and len(API_KEY) > 3 and API_KEY in content_str:
        errors.append("API KEY value in DB")
    if HASH_SECRET and len(HASH_SECRET) > 3 and HASH_SECRET in content_str:
        errors.append("HASH_SECRET value in DB")

    return ("FAIL", errors) if errors else ("PASS", errors)


# ── manifest + 보안 스캔 ───────────────────────────────────────
def write_manifest(row_count, rejected_row_count, db_path, validation_status, validation_errors):
    manifest_path = os.path.join(CACHE_DIR, "manifest.json")

    db_hash = ""
    if os.path.exists(db_path):
        with open(db_path, "rb") as f:
            db_hash = hashlib.sha256(f.read()).hexdigest()

    endpoint_host_path = "mock-monitoring-api.local/api/v1"
    if not MOCK_MODE and API_BASE_URL:
        endpoint_host_path = API_BASE_URL.split("://")[-1].split("?")[0]

    manifest = {
        "cache_type": "company_daily_integrated",
        "cache_schema_version": "1.0.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "refreshed_at": datetime.now(timezone.utc).isoformat(),
        "row_count": row_count,
        "company_count": row_count,
        "rejected_row_count": rejected_row_count,
        "source_api_endpoints": [endpoint_host_path],
        "db_hash": db_hash,
        "validation_status": validation_status,
        "validation_errors": validation_errors,
    }

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    # manifest 보안 스캔
    with open(manifest_path, "r", encoding="utf-8") as f:
        content = f.read()

    for label, val in [("API_KEY", API_KEY), ("HASH_SECRET", HASH_SECRET), ("OC_KEY", os.getenv("OC_KEY"))]:
        if val and len(val) > 3 and val in content:
            raise RuntimeError(f"{label} value exposed in manifest")
    for kw in ["password", "serviceKey", "OC_KEY", "token"]:
        if kw in content:
            raise RuntimeError(f"Sensitive keyword '{kw}' in manifest")
    if re.search(r"\d{3}-\d{2}-\d{5}", content) or re.search(r"\b\d{10}\b", content):
        raise RuntimeError("Business number pattern in manifest")
    if "representative" in content.lower():
        raise RuntimeError("representative in manifest")
    if re.search(r"\b0\d{1,2}-\d{3,4}-\d{4}\b", content):
        raise RuntimeError("Phone pattern in manifest")
    if re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", content):
        raise RuntimeError("Email pattern in manifest")


# ── sample query ───────────────────────────────────────────────
def sample_query_smoke(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM companies WHERE company_name LIKE '%건설%'")
    c1 = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM companies WHERE license_or_business_type LIKE '%용역%'")
    c2 = cur.fetchone()[0]
    conn.close()
    return {"query_건설": c1, "query_용역": c2}


# ── main ───────────────────────────────────────────────────────
def run():
    print("=== CacheBuilder MVP Phase 11: Live API 최소 연동 ===")

    # 환경변수 사전 검증
    missing = []
    if not HASH_SECRET:
        missing.append("COMPANY_HASH_SECRET")
    if not MOCK_MODE:
        if not API_BASE_URL:
            missing.append("MONITORING_API_BASE_URL")
        if not API_KEY:
            missing.append("MONITORING_API_KEY")
    if missing:
        print(f"FAIL: Missing env vars: {missing}")
        return

    prepare_workspace()

    # 결과 수집용
    report = {
        "http_status": 0,
        "elapsed_ms": 0,
        "total_elements_present": False,
        "total_pages_present": False,
        "returned_row_count": 0,
        "field_presence_summary": [],
        "normalized_row_count": 0,
        "rejected_row_count": 0,
        "sqlite_row_count": 0,
        "validation_status": "FAIL",
        "validation_errors": [],
        "production_deployment": "HOLD",
    }

    try:
        # ── 1. fetch ──
        data, http_status, elapsed_ms = load_sources_limited()
        report["http_status"] = http_status
        report["elapsed_ms"] = elapsed_ms

        # content key 탐색 (API마다 다를 수 있음)
        content_key = None
        for candidate in ["content", "data", "items", "list", "results"]:
            if candidate in data:
                content_key = candidate
                break
        if content_key is None:
            # data 자체가 list일 수 있음
            if isinstance(data, list):
                raw_records = data
            else:
                report["validation_errors"].append(f"Cannot find content key. Top keys: {list(data.keys())[:10]}")
                raw_records = []
        else:
            raw_records = data[content_key]

        report["returned_row_count"] = len(raw_records)

        # total_elements / total_pages 존재 여부
        for te_key in ["total_elements", "totalCount", "totalElements", "total"]:
            if te_key in data:
                report["total_elements_present"] = True
                break
        for tp_key in ["total_pages", "totalPages"]:
            if tp_key in data:
                report["total_pages_present"] = True
                break

        # field presence summary (첫 레코드 기준, 값 출력 금지)
        if raw_records:
            report["field_presence_summary"] = sorted(raw_records[0].keys())

        print(f"HTTP {http_status}, {elapsed_ms}ms, rows={len(raw_records)}")
        print(f"Fields: {report['field_presence_summary']}")

        # ── 2. normalize ──
        normalized = []
        for r in raw_records:
            try:
                norm = normalize_company_record(r)
                normalized.append(norm)
            except Exception as e:
                report["rejected_row_count"] += 1
                report["validation_errors"].append(f"Reject: {str(e)}")

        report["normalized_row_count"] = len(normalized)
        print(f"Normalized: {len(normalized)}, Rejected: {report['rejected_row_count']}")

        # ── 3. SQLite ──
        if len(normalized) > 0:
            db_path, inserted = write_sqlite_cache(normalized)
            report["sqlite_row_count"] = inserted
            print(f"SQLite inserted: {inserted}")

            # ── 4. validate ──
            v_status, v_errors = validate_cache(db_path)
            report["validation_status"] = v_status
            report["validation_errors"].extend(v_errors)
        else:
            report["validation_errors"].append("No normalized records")
            db_path = os.path.join(CACHE_DIR, "company_master_cache.sqlite")

        # ── 5. smoke ──
        if report["validation_status"] == "PASS" and os.path.exists(db_path):
            smoke = sample_query_smoke(db_path)
            print(f"Smoke: {smoke}")

        # ── 6. manifest ──
        write_manifest(
            len(normalized), report["rejected_row_count"],
            db_path, report["validation_status"], report["validation_errors"],
        )

    except requests.exceptions.ConnectionError as e:
        report["validation_errors"].append(f"Connection failed: {type(e).__name__}")
    except requests.exceptions.HTTPError as e:
        report["http_status"] = e.response.status_code if e.response else 0
        report["validation_errors"].append(f"HTTP error: {report['http_status']}")
    except Exception as e:
        report["validation_errors"].append(f"Error: {type(e).__name__}: {str(e)}")

    # ── 최종 리포트 출력 (민감값 제외) ──
    print()
    print("=== Phase 11 Result ===")
    for k, v in report.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    run()
