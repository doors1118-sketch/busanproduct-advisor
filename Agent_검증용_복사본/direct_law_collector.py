"""
Phase 7-B 법령DB 직접 수집 — 법제처 Open API 직접 호출
NCP MCP 서버 우회용. 사무실 PC에서 실행.

사용법:
    python direct_law_collector.py                # 전체 수집
    python direct_law_collector.py --group A      # Group A만
    python direct_law_collector.py --resume       # 체크포인트에서 재개
    python direct_law_collector.py --dry-run      # 호출 없이 목록만

산출물:
    app/data/legal_source_registry.json
    app/data/legal_source_candidate.json
    app/data/_direct_checkpoint.json
"""
import os, sys, json, time, re, argparse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
import requests

# ─── 설정 ───
_root = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(_root, "data")
os.makedirs(DATA_DIR, exist_ok=True)

REGISTRY_PATH = os.path.join(DATA_DIR, "legal_source_registry.json")
CANDIDATE_PATH = os.path.join(DATA_DIR, "legal_source_candidate.json")
CHECKPOINT_PATH = os.path.join(DATA_DIR, "_direct_checkpoint.json")

BASE_URL = "http://www.law.go.kr/DRF"
OC = "busanproduct1"
SLEEP_BETWEEN = 1.0   # 호출 간 대기 (초)
TIMEOUT = 15           # HTTP 타임아웃 (초)
MAX_RETRY = 1
KST = timezone(timedelta(hours=9))

# ─── 37건 Seed 법령 매니페스트 ───
SEED_LAWS = [
    # Group A: 핵심 계약법
    {"id":"local_contract_act","name":"지방계약법","query":"지방자치단체를 당사자로 하는 계약에 관한 법률","type":"law","group":"A"},
    {"id":"local_contract_decree","name":"지방계약법 시행령","query":"지방자치단체를 당사자로 하는 계약에 관한 법률 시행령","type":"law","group":"A"},
    {"id":"local_contract_rule","name":"지방계약법 시행규칙","query":"지방자치단체를 당사자로 하는 계약에 관한 법률 시행규칙","type":"law","group":"A"},
    {"id":"national_contract_act","name":"국가계약법","query":"국가를 당사자로 하는 계약에 관한 법률","type":"law","group":"A"},
    {"id":"national_contract_decree","name":"국가계약법 시행령","query":"국가를 당사자로 하는 계약에 관한 법률 시행령","type":"law","group":"A"},
    {"id":"national_contract_rule","name":"국가계약법 시행규칙","query":"국가를 당사자로 하는 계약에 관한 법률 시행규칙","type":"law","group":"A"},
    {"id":"procurement_act","name":"조달사업법","query":"조달사업에 관한 법률","type":"law","group":"A"},
    {"id":"procurement_decree","name":"조달사업법 시행령","query":"조달사업에 관한 법률 시행령","type":"law","group":"A"},
    {"id":"procurement_rule","name":"조달사업법 시행규칙","query":"조달사업에 관한 법률 시행규칙","type":"law","group":"A"},
    # Group B: 행정규칙·예규·집행기준
    {"id":"local_bid_execution","name":"지방자치단체 입찰 및 계약집행기준","query":"지방자치단체 입찰 및 계약집행기준","type":"admrul","group":"B"},
    {"id":"local_bid_winner","name":"지방자치단체 입찰시 낙찰자 결정기준","query":"지방자치단체 입찰시 낙찰자 결정기준","type":"admrul","group":"B"},
    {"id":"gov_bid_execution","name":"정부 입찰·계약 집행기준","query":"정부 입찰 계약 집행기준","type":"admrul","group":"B"},
    {"id":"contract_regulation","name":"계약예규","query":"계약예규","type":"admrul","group":"B"},
    {"id":"pps_mas_standard","name":"조달청 다수공급자계약 관련 기준","query":"다수공급자계약","type":"admrul","group":"B"},
    {"id":"shopping_mall_ops","name":"나라장터 종합쇼핑몰 운영 관련 기준","query":"종합쇼핑몰 운영","type":"admrul","group":"B"},
    {"id":"mas_processing","name":"물품 다수공급자계약 업무처리규정","query":"물품 다수공급자계약 업무처리규정","type":"admrul","group":"B"},
    {"id":"mas_2step","name":"MAS 2단계경쟁 관련 기준","query":"다수공급자계약 2단계 경쟁","type":"admrul","group":"B"},
    # Group C: 중소·정책기업 법령
    {"id":"sme_purchase_act","name":"중소기업제품 구매촉진 및 판로지원법","query":"중소기업제품 구매촉진 및 판로지원에 관한 법률","type":"law","group":"C"},
    {"id":"sme_purchase_decree","name":"중소기업제품 구매촉진법 시행령","query":"중소기업제품 구매촉진 및 판로지원에 관한 법률 시행령","type":"law","group":"C"},
    {"id":"sme_competition_items","name":"중소기업자간 경쟁제품 지정내역","query":"중소기업자간 경쟁제품 직접구매 대상품목","type":"admrul","group":"C"},
    {"id":"direct_production","name":"직접생산확인 관련 기준","query":"직접생산확인","type":"admrul","group":"C"},
    {"id":"women_enterprise_act","name":"여성기업지원법","query":"여성기업지원에 관한 법률","type":"law","group":"C"},
    {"id":"women_enterprise_decree","name":"여성기업지원법 시행령","query":"여성기업지원에 관한 법률 시행령","type":"law","group":"C"},
    {"id":"disabled_enterprise_act","name":"장애인기업활동 촉진법","query":"장애인기업활동 촉진법","type":"law","group":"C"},
    {"id":"disabled_enterprise_decree","name":"장애인기업활동 촉진법 시행령","query":"장애인기업활동 촉진법 시행령","type":"law","group":"C"},
    {"id":"social_enterprise_act","name":"사회적기업 육성법","query":"사회적기업 육성법","type":"law","group":"C"},
    {"id":"social_enterprise_decree","name":"사회적기업 육성법 시행령","query":"사회적기업 육성법 시행령","type":"law","group":"C"},
    # Group D: 혁신·우수조달·기술개발
    {"id":"innovation_product","name":"혁신제품 관련 조달청 고시·지침","query":"혁신제품 구매","type":"admrul","group":"D"},
    {"id":"innovation_prototype","name":"혁신시제품 지정 및 구매 관련 기준","query":"혁신시제품","type":"admrul","group":"D"},
    {"id":"excellent_procurement","name":"우수조달물품 지정관리 규정","query":"우수조달물품 지정","type":"admrul","group":"D"},
    {"id":"tech_priority_purchase","name":"기술개발제품 우선구매 관련 기준","query":"기술개발제품 우선구매","type":"admrul","group":"D"},
    # Group E: 부산시 자치법규 (PDF 보유, API ordi 미지원 → skip_api)
    {"id":"busan_local_product","name":"부산광역시 지역상품 우선구매 관련 조례","query":"부산광역시 지역상품 우선구매","type":"skip_api","group":"E","note":"PDF 보유"},
    {"id":"busan_local_company","name":"부산광역시 지역업체·지역상품 우대 관련 자치법규","query":"부산광역시 지역업체 지역상품","type":"skip_api","group":"E","note":"PDF 보유"},
    # Group F: 공공기관
    {"id":"public_institution_act","name":"공공기관의 운영에 관한 법률","query":"공공기관의 운영에 관한 법률","type":"law","group":"F"},
    {"id":"public_institution_decree","name":"공공기관의 운영에 관한 법률 시행령","query":"공공기관의 운영에 관한 법률 시행령","type":"law","group":"F"},
    {"id":"public_corp_contract_rule","name":"공기업ㆍ준정부기관 계약사무규칙","query":"공기업 준정부기관 계약사무규칙","type":"law","group":"F"},
    {"id":"public_corp_accounting_rule","name":"공기업ㆍ준정부기관 회계사무규칙","query":"공기업 준정부기관 회계사무규칙","type":"law","group":"F"},
]


# ─── API 호출 함수 ───

def api_get(endpoint, params, retry=MAX_RETRY):
    """법제처 API GET 요청. 재시도 포함."""
    params["OC"] = OC
    params["type"] = "XML"
    for attempt in range(retry + 1):
        try:
            r = requests.get(f"{BASE_URL}/{endpoint}", params=params, timeout=TIMEOUT)
            r.raise_for_status()
            if len(r.content) < 10:
                return None
            return ET.fromstring(r.content)
        except Exception as e:
            if attempt < retry:
                time.sleep(SLEEP_BETWEEN)
                continue
            print(f"    [ERROR] {endpoint}: {e}")
            return None


def search_law_api(query, display=5):
    """법령 검색 → 목록 반환"""
    root = api_get("lawSearch.do", {"target": "law", "query": query, "display": display})
    if root is None:
        return []
    results = []
    for item in root.findall(".//law"):
        entry = {}
        for child in item:
            entry[child.tag] = child.text
        if entry:
            results.append(entry)
    return results


def get_law_full(mst):
    """법령 전문 조회 (MST 기반) → 조문 목록 반환"""
    root = api_get("lawService.do", {"target": "law", "MST": mst})
    if root is None:
        return None

    info = {}
    # 기본정보
    info["법령명"] = _xt(root, ".//법령명_한글") or _xt(root, ".//법령명한글") or ""
    info["법령ID"] = _xt(root, ".//법령ID") or ""
    info["공포일자"] = _xt(root, ".//공포일자") or ""
    info["시행일자"] = _xt(root, ".//시행일자") or ""
    info["소관부처"] = _xt(root, ".//소관부처") or ""
    info["법종구분"] = _xt(root, ".//법종구분") or ""

    # 조문 파싱
    articles = []
    for jo in root.findall(".//조문단위"):
        art = {
            "조문번호": _xt(jo, "조문번호") or "",
            "조문제목": _xt(jo, "조문제목") or "",
            "조문내용": _xt(jo, "조문내용") or "",
        }
        articles.append(art)
    info["조문수"] = len(articles)
    info["조문목록"] = articles

    # 별표 파싱
    annexes = []
    for bp in root.findall(".//별표단위"):
        annex = {
            "별표번호": _xt(bp, "별표번호") or "",
            "별표제목": _xt(bp, "별표제목") or _xt(bp, "별표서식명") or "",
            "별표내용": _xt(bp, "별표내용") or "",
        }
        annexes.append(annex)
    info["별표수"] = len(annexes)
    info["별표목록"] = annexes

    return info


def search_admrul_api(query, display=10):
    """행정규칙 검색 → 목록 반환"""
    root = api_get("lawSearch.do", {"target": "admrul", "query": query, "display": display})
    if root is None:
        return []
    results = []
    for item in root.findall(".//admrul"):
        entry = {}
        for child in item:
            entry[child.tag] = child.text
        if entry:
            results.append(entry)
    return results


def get_admrul_full(admrul_id):
    """행정규칙 전문 조회 (행정규칙일련번호 기반) → 조문/본문 반환"""
    root = api_get("lawService.do", {"target": "admrul", "ID": admrul_id})
    if root is None:
        return None

    info = {}
    info["행정규칙명"] = _xt(root, ".//행정규칙명") or ""
    info["행정규칙종류"] = _xt(root, ".//행정규칙종류") or ""
    info["발령일자"] = _xt(root, ".//발령일자") or ""
    info["발령번호"] = _xt(root, ".//발령번호") or ""
    info["소관부처명"] = _xt(root, ".//소관부처명") or ""
    info["행정규칙ID"] = _xt(root, ".//행정규칙ID") or ""

    # 조문 파싱 — 행정규칙은 법률과 XML 구조가 다름:
    #   법률: <조문><조문단위><조문내용>...</조문단위></조문>
    #   행정규칙: <AdmRulService><조문내용>...</조문내용> (루트 직접 하위)
    articles = []

    # 방법1: 법률식 (조문단위 래핑)
    for jo in root.findall(".//조문단위"):
        art = {
            "조문번호": _xt(jo, "조문번호") or "",
            "조문제목": _xt(jo, "조문제목") or "",
            "조문내용": _xt(jo, "조문내용") or "",
        }
        articles.append(art)

    # 방법2: 행정규칙식 (루트 직접 하위 조문내용 태그)
    if not articles:
        idx = 0
        for child in root:
            if child.tag == "조문내용" and child.text:
                idx += 1
                articles.append({
                    "조문번호": str(idx),
                    "조문제목": "",
                    "조문내용": child.text.strip(),
                })

    info["조문수"] = len(articles)
    info["조문목록"] = articles

    # 부칙 파싱
    appendix_texts = []
    for bp_el in root.findall(".//부칙"):
        for bc in bp_el.findall("부칙내용"):
            if bc.text:
                appendix_texts.append(bc.text.strip())
    info["부칙수"] = len(appendix_texts)

    # 별표 파싱
    annexes = []
    # 방법1: 별표단위 태그
    for bp in root.findall(".//별표단위"):
        annex = {
            "별표번호": _xt(bp, "별표번호") or "",
            "별표제목": _xt(bp, "별표제목") or _xt(bp, "별표서식명") or "",
        }
        annexes.append(annex)
    # 방법2: 별표 > 별표내용 태그 (행정규칙)
    if not annexes:
        for bp_parent in root.findall(".//별표"):
            for bc in bp_parent.findall("별표내용"):
                if bc.text:
                    title = bc.text[:50].split("\n")[0].strip()
                    annexes.append({"별표번호": "", "별표제목": title})
    info["별표수"] = len(annexes)

    # 전체 텍스트 길이 = 조문 + 부칙
    total_text = ""
    for art in articles:
        total_text += art.get("조문내용", "") + "\n"
    for apt in appendix_texts:
        total_text += apt + "\n"
    info["전체텍스트길이"] = len(total_text)

    return info


def _xt(root, xpath):
    """XML 텍스트 추출 헬퍼"""
    el = root.find(xpath)
    return el.text.strip() if el is not None and el.text else None


# ─── 수집 파이프라인 ───

def collect_seed(seed, dry_run=False):
    """하나의 Seed 법령에 대해 수집 파이프라인을 실행합니다."""
    sid = seed["id"]
    stype = seed["type"]
    query = seed["query"]
    mst = seed.get("mst")

    result = {
        "seed_id": sid,
        "name": seed["name"],
        "group": seed["group"],
        "query": query,
        "source_type": stype,
        "status": "pending",
        "steps_completed": [],
        "steps_failed": [],
        "collected_at": datetime.now(KST).isoformat(),
        # 데이터 필드
        "law_id": None,
        "mst": mst,
        "effective_date": None,
        "issuing_org": None,
        "law_name_official": None,
        "article_count": 0,
        "annex_count": 0,
        "full_text_length": 0,
        "raw_search_result": None,
        "articles_preview": None,
    }

    if dry_run:
        result["status"] = "dry_run"
        return result

    # skip_api (부산시 조례 등 - PDF로 보유)
    if stype == "skip_api":
        result["status"] = "skipped_pdf_available"
        result["steps_completed"].append("skip_api_pdf_available")
        note = seed.get("note", "")
        result["raw_search_result"] = f"API 미지원. {note}"
        return result

    print(f"  [{sid}] 수집 시작...")

    # ── Step 1: 검색 ──
    if stype == "law":
        search_results = search_law_api(query, display=3)
        step_name = "search_law"
    elif stype == "admrul":
        search_results = search_admrul_api(query, display=10)
        step_name = "search_admrul"
    else:
        result["status"] = "failed"
        result["steps_failed"].append("unknown_type")
        return result

    time.sleep(SLEEP_BETWEEN)

    if not search_results:
        result["status"] = "failed"
        result["steps_failed"].append(step_name)
        print(f"    → 검색 실패 (결과 0건)")
        return result

    result["steps_completed"].append(step_name)
    result["raw_search_result"] = search_results[0]  # 첫 번째 결과

    # ── Step 2: 법령 전문 조회 (law 타입만) ──
    if stype == "law":
        # MST 결정: 매니페스트에 있으면 사용, 없으면 검색 결과에서 추출
        use_mst = mst or search_results[0].get("법령일련번호")
        if use_mst:
            law_data = get_law_full(use_mst)
            time.sleep(SLEEP_BETWEEN)

            if law_data:
                result["steps_completed"].append("get_full_text")
                result["law_id"] = law_data.get("법령ID")
                result["mst"] = use_mst
                result["effective_date"] = law_data.get("시행일자")
                result["issuing_org"] = law_data.get("소관부처")
                result["law_name_official"] = law_data.get("법령명")
                result["article_count"] = law_data.get("조문수", 0)
                result["annex_count"] = law_data.get("별표수", 0)

                # 전체 텍스트 길이 계산
                full_text = ""
                for art in law_data.get("조문목록", []):
                    full_text += art.get("조문내용", "") + "\n"
                result["full_text_length"] = len(full_text)

                # 조문 미리보기 (처음 5개)
                preview = []
                for art in law_data.get("조문목록", [])[:5]:
                    preview.append({
                        "조문번호": art.get("조문번호"),
                        "조문제목": art.get("조문제목"),
                        "내용미리보기": (art.get("조문내용", "") or "")[:100]
                    })
                result["articles_preview"] = preview
            else:
                result["steps_failed"].append("get_full_text")
        else:
            result["steps_failed"].append("no_mst_available")

    elif stype == "admrul":
        # 행정규칙: 메타데이터 + 전문 수집
        top = search_results[0]
        result["law_name_official"] = top.get("행정규칙명")
        result["effective_date"] = top.get("발령일자") or top.get("시행일자")
        result["issuing_org"] = top.get("소관부처명")
        result["steps_completed"].append("admrul_metadata")

        # 전문 조회
        admrul_serial = top.get("행정규칙일련번호")
        if admrul_serial:
            admrul_data = get_admrul_full(admrul_serial)
            time.sleep(SLEEP_BETWEEN)

            if admrul_data:
                result["steps_completed"].append("get_full_text")
                result["law_id"] = admrul_data.get("행정규칙ID")
                result["article_count"] = admrul_data.get("조문수", 0)
                result["annex_count"] = admrul_data.get("별표수", 0)
                result["full_text_length"] = admrul_data.get("전체텍스트길이", 0)

                # 조문 미리보기
                preview = []
                for art in admrul_data.get("조문목록", [])[:5]:
                    preview.append({
                        "조문번호": art.get("조문번호"),
                        "조문제목": art.get("조문제목"),
                        "내용미리보기": (art.get("조문내용", "") or "")[:100]
                    })
                if not preview and admrul_data.get("본문미리보기"):
                    preview = [{"본문미리보기": admrul_data["본문미리보기"][:200]}]
                result["articles_preview"] = preview
            else:
                result["steps_failed"].append("get_full_text")

    # ── 최종 상태 결정 ──
    if result["steps_failed"]:
        if result["steps_completed"]:
            result["status"] = "partial"
        else:
            result["status"] = "failed"
    else:
        result["status"] = "verified"

    step_info = f"완료={len(result['steps_completed'])}, 실패={len(result['steps_failed'])}"
    print(f"    → {result['status']} | 조문 {result['article_count']}건, 별표 {result['annex_count']}건, 텍스트 {result['full_text_length']}자 | {step_info}")

    return result


# ─── 체크포인트 관리 ───

def load_checkpoint():
    if os.path.exists(CHECKPOINT_PATH):
        with open(CHECKPOINT_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {"completed_seeds": [], "registry": []}


def save_checkpoint(completed, registry):
    with open(CHECKPOINT_PATH, "w", encoding="utf-8") as f:
        json.dump({"completed_seeds": completed, "registry": registry}, f, ensure_ascii=False, indent=2)


# ─── 메인 실행 ───

def main():
    parser = argparse.ArgumentParser(description="법제처 직접 수집 스크립트")
    parser.add_argument("--group", default="all", help="수집 그룹 (A/B/C/D/E/F/all)")
    parser.add_argument("--resume", action="store_true", help="체크포인트에서 재개")
    parser.add_argument("--dry-run", action="store_true", help="MCP 호출 없이 목록만 출력")
    args = parser.parse_args()

    print("=" * 60)
    print("Phase 7-B 법령DB 직접 수집 (법제처 Open API)")
    print(f"시각: {datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S KST')}")
    print(f"그룹: {args.group} | Resume: {args.resume} | Dry-run: {args.dry_run}")
    print("=" * 60)

    # 대상 필터링
    targets = SEED_LAWS
    if args.group.upper() != "ALL":
        targets = [s for s in SEED_LAWS if s["group"] == args.group.upper()]

    print(f"\n수집 대상: {len(targets)}건")

    # 체크포인트 로드
    if args.resume:
        ckpt = load_checkpoint()
        completed = set(ckpt["completed_seeds"])
        registry = ckpt["registry"]
        print(f"체크포인트 로드: {len(completed)}건 완료, {len(targets) - len(completed)}건 남음")
    else:
        completed = set()
        registry = []

    # 수집 실행
    candidates = []
    stats = {"verified": 0, "partial": 0, "failed": 0, "skipped": 0}

    for i, seed in enumerate(targets):
        if seed["id"] in completed:
            print(f"  [{i+1}/{len(targets)}] {seed['name']} — 이미 완료, 건너뜀")
            continue

        print(f"\n[{i+1}/{len(targets)}] {seed['name']} (Group {seed['group']})")
        result = collect_seed(seed, dry_run=args.dry_run)
        registry.append(result)
        completed.add(seed["id"])

        # 상태 집계
        st = result["status"]
        if st == "verified":
            stats["verified"] += 1
        elif st == "partial":
            stats["partial"] += 1
        elif st in ("skipped_pdf_available", "dry_run"):
            stats["skipped"] += 1
        else:
            stats["failed"] += 1

        # 체크포인트 저장
        save_checkpoint(list(completed), registry)

    # 결과 저장
    with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(registry, f, ensure_ascii=False, indent=2)

    with open(CANDIDATE_PATH, "w", encoding="utf-8") as f:
        json.dump(candidates, f, ensure_ascii=False, indent=2)

    # 최종 보고
    print("\n" + "=" * 60)
    print("수집 완료!")
    print(f"  Verified: {stats['verified']}건")
    print(f"  Partial:  {stats['partial']}건")
    print(f"  Failed:   {stats['failed']}건")
    print(f"  Skipped:  {stats['skipped']}건")
    print(f"\n저장 위치:")
    print(f"  Registry:  {REGISTRY_PATH}")
    print(f"  Candidate: {CANDIDATE_PATH}")
    print("=" * 60)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
