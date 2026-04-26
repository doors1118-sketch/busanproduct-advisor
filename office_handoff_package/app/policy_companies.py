"""
정책기업(여성·사회적·장애인) 조달업체 DB 로드 + 태깅
- 3개 Excel → 사업자번호 기반 딕셔너리 통합
- company_api 검색 결과에 정책 태그 자동 부여
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
import json
import pandas as pd

BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
CACHE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "policy_companies.json")

# Excel 파일 경로
POLICY_FILES = [
    ("여성기업", os.path.join(BASE_DIR, "여성기업 조달업체 등록 내역(20260422).xlsx")),
    ("사회적기업", os.path.join(BASE_DIR, "사회적기업 조달업체 등록 내역.xlsx")),
    ("장애인기업", os.path.join(BASE_DIR, "장애인기업 조달업체 등록 내역.xlsx")),
]


def _parse_excel(filepath: str) -> pd.DataFrame:
    """조달청 엑셀 파싱 (헤더 Row 4, 데이터 Row 5~)"""
    df = pd.read_excel(filepath, header=None, skiprows=4)
    df.columns = df.iloc[0]
    df = df[1:].reset_index(drop=True)
    # NaN 행 제거
    df = df.dropna(subset=["사업자등록번호"])
    return df


def build_policy_db() -> dict:
    """
    3개 Excel → 사업자번호 기반 통합 딕셔너리.
    Returns: {사업자번호: {업체명, 소재지, tags: [여성기업, ...], 기업구분, 대표품명, ...}}
    """
    print("=" * 50)
    print("  Policy Companies DB Build")
    print("=" * 50)

    db = {}  # {사업자번호: {...}}

    for label, filepath in POLICY_FILES:
        if not os.path.exists(filepath):
            print(f"  [SKIP] {label}: file not found")
            continue

        df = _parse_excel(filepath)
        count = 0

        for _, row in df.iterrows():
            bno = str(row.get("사업자등록번호", "")).replace("-", "").strip()
            if len(bno) != 10:
                continue

            if bno not in db:
                db[bno] = {
                    "name": str(row.get("업체명", "")),
                    "location": str(row.get("업체소재시군구", "")),
                    "biz_type": str(row.get("기업구분", "")),
                    "industry": str(row.get("대표업종", "")),
                    "product": str(row.get("대표세부품명", "")),
                    "manufacturer": str(row.get("제조업체여부", "")),
                    "registered": str(row.get("나라장터등록일자", "")),
                    "tags": [],
                }

            # 태그 추가 (각 파일에서 해당 인증여부가 Y인 경우)
            if str(row.get("여성기업인증여부", "")).upper() == "Y":
                if "여성기업" not in db[bno]["tags"]:
                    db[bno]["tags"].append("여성기업")
            if str(row.get("장애인기업인증여부", "")).upper() == "Y":
                if "장애인기업" not in db[bno]["tags"]:
                    db[bno]["tags"].append("장애인기업")
            if str(row.get("사회적기업인증여부", "")).upper() == "Y":
                if "사회적기업" not in db[bno]["tags"]:
                    db[bno]["tags"].append("사회적기업")

            # 파일 출처도 태그에 추가 (인증여부 컬럼이 비어있을 수 있으므로)
            if label not in db[bno]["tags"]:
                db[bno]["tags"].append(label)

            count += 1

        print(f"  [OK] {label}: {count} entries")

    # JSON 캐시 저장
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)
    print(f"\n  Saved: {CACHE_PATH}")
    print(f"  Total unique companies: {len(db)}")

    # 통계
    tag_counts = {}
    for v in db.values():
        for t in v["tags"]:
            tag_counts[t] = tag_counts.get(t, 0) + 1
    print(f"\n  Tag distribution:")
    for tag, cnt in sorted(tag_counts.items(), key=lambda x: -x[1]):
        print(f"    {tag}: {cnt}")

    return db


# ─────────────────────────────────────────────
# 메모리 캐시 (앱 실행 시 1회 로드)
# ─────────────────────────────────────────────
_policy_db: dict = None


def _load_policy_db() -> dict:
    """JSON 캐시에서 정책기업 DB 로드 (없으면 빈 딕셔너리)"""
    global _policy_db
    if _policy_db is not None:
        return _policy_db

    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            _policy_db = json.load(f)
    else:
        _policy_db = {}

    return _policy_db


def get_policy_tags(biz_no: str) -> list[str]:
    """사업자번호로 정책기업 태그 조회. 예: ['여성기업', '사회적기업']"""
    db = _load_policy_db()
    bno = str(biz_no).replace("-", "").strip()
    entry = db.get(bno)
    return entry["tags"] if entry else []


def get_policy_info(biz_no: str) -> dict:
    """사업자번호로 정책기업 상세 정보 조회"""
    db = _load_policy_db()
    bno = str(biz_no).replace("-", "").strip()
    return db.get(bno, {})


def enrich_company_results(data: dict) -> dict:
    """
    busanproduct 검색 결과에 정책기업 태그 추가.
    company_api.filter_active_companies() 이후에 호출.
    """
    companies = data.get("업체목록", [])
    if not companies:
        return data

    for c in companies:
        bno = str(c.get("사업자번호", "")).replace("-", "").strip()
        tags = get_policy_tags(bno)
        if tags:
            c["_정책기업"] = tags

    return data


# ─────────────────────────────────────────
if __name__ == "__main__":
    build_policy_db()
