"""
Phase 7-B Legal Cache Seed 구축 — 오프라인 ETL 배치 스크립트
33개 Seed 법령에 대해 MCP 7단계 수집 파이프라인을 실행합니다.

사용법:
    python build_legal_source_registry.py --group A        # Group A만
    python build_legal_source_registry.py --group all      # 전체
    python build_legal_source_registry.py --dry-run        # MCP 호출 없이 목록만
    python build_legal_source_registry.py --resume         # checkpoint에서 재개

산출물:
    app/data/legal_source_registry.json    — Seed 수집 결과
    app/data/legal_source_candidate.json   — 검수 대기 자동발견 자료
    app/data/_checkpoint.json              — seed 단위 중간저장

주의: 실시간 챗봇 runtime에서 실행하지 마세요. 오프라인 ETL 전용입니다.
"""
import os, sys, json, time, re, argparse
from datetime import datetime, timezone, timedelta

_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _root)
os.environ.setdefault("PROMPT_MODE", "dynamic_v1_4_4")
# ETL 배치 전용: MCP 타임아웃을 15초로 오버라이드 (runtime 기본 10초보다 높게)
os.environ["MCP_LAW_TEXT_TIMEOUT_SECONDS"] = "15"
os.environ["MCP_ADMIN_RULE_TIMEOUT_SECONDS"] = "15"
os.environ["MCP_CHAIN_TIMEOUT_SECONDS"] = "15"
os.environ["MCP_ORDINANCE_TIMEOUT_SECONDS"] = "15"
os.environ["MCP_DECISION_TIMEOUT_SECONDS"] = "15"

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(_root), ".env"))

import mcp_client as mcp

# ─── 설정 ───
DATA_DIR = os.path.join(_root, "data")
REGISTRY_PATH = os.path.join(DATA_DIR, "legal_source_registry.json")
CANDIDATE_PATH = os.path.join(DATA_DIR, "legal_source_candidate.json")
CHECKPOINT_PATH = os.path.join(DATA_DIR, "_checkpoint.json")

SLEEP_BETWEEN_CALLS = 2.0   # MCP 호출 간 대기(초)
MCP_TIMEOUT = 15             # MCP 호출 타임아웃(초)
MAX_RETRY = 1                # 실패 시 재시도 횟수
CANDIDATE_LIMIT_TOPIC = 10   # 주제형 Seed candidate 상한
CANDIDATE_LIMIT_EXACT = 5    # 정확매칭 Seed candidate 상한

KST = timezone(timedelta(hours=9))

# ─── Seed 법령 매니페스트 (33건) ───
SEED_LAWS = [
    # Group A: 핵심 계약법 (법률 → search_law)
    {"id":"local_contract_act","name":"지방계약법","query":"지방자치단체를 당사자로 하는 계약에 관한 법률","tool":"search_law","group":"A","mst":"253973"},
    {"id":"local_contract_decree","name":"지방계약법 시행령","query":"지방자치단체를 당사자로 하는 계약에 관한 법률 시행령","tool":"search_law","group":"A","mst":"281055"},
    {"id":"local_contract_rule","name":"지방계약법 시행규칙","query":"지방자치단체를 당사자로 하는 계약에 관한 법률 시행규칙","tool":"search_law","group":"A","mst":"282729"},
    {"id":"national_contract_act","name":"국가계약법","query":"국가를 당사자로 하는 계약에 관한 법률","tool":"search_law","group":"A","mst":"277151"},
    {"id":"national_contract_decree","name":"국가계약법 시행령","query":"국가를 당사자로 하는 계약에 관한 법률 시행령","tool":"search_law","group":"A","mst":"280803"},
    {"id":"national_contract_rule","name":"국가계약법 시행규칙","query":"국가를 당사자로 하는 계약에 관한 법률 시행규칙","tool":"search_law","group":"A","mst":"282607"},
    {"id":"procurement_act","name":"조달사업법","query":"조달사업에 관한 법률","tool":"search_law","group":"A","mst":"277155"},
    {"id":"procurement_decree","name":"조달사업법 시행령","query":"조달사업에 관한 법률 시행령","tool":"search_law","group":"A","mst":"280891"},
    {"id":"procurement_rule","name":"조달사업법 시행규칙","query":"조달사업에 관한 법률 시행규칙","tool":"search_law","group":"A","mst":"282675"},
    # Group B: 행정규칙·예규·집행기준
    {"id":"local_bid_execution","name":"지방자치단체 입찰 및 계약집행기준","query":"지방자치단체 입찰 및 계약집행기준","tool":"search_admin_rule","group":"B","topic":False},
    {"id":"local_bid_winner","name":"지방자치단체 입찰시 낙찰자 결정기준","query":"지방자치단체 입찰시 낙찰자 결정기준","tool":"search_admin_rule","group":"B","topic":False},
    {"id":"gov_bid_execution","name":"정부 입찰·계약 집행기준","query":"정부 입찰 계약 집행기준","tool":"search_admin_rule","group":"B","topic":False},
    {"id":"contract_regulation","name":"계약예규","query":"계약예규","tool":"search_admin_rule","group":"B","topic":True},
    {"id":"pps_mas_standard","name":"조달청 다수공급자계약 관련 기준","query":"다수공급자계약","tool":"search_admin_rule","group":"B","topic":True},
    {"id":"shopping_mall_ops","name":"나라장터 종합쇼핑몰 운영 관련 기준","query":"종합쇼핑몰 운영","tool":"search_admin_rule","group":"B","topic":True},
    {"id":"mas_processing","name":"물품 다수공급자계약 업무처리규정","query":"물품 다수공급자계약 업무처리규정","tool":"search_admin_rule","group":"B","topic":False},
    {"id":"mas_2step","name":"MAS 2단계경쟁 관련 기준","query":"다수공급자계약 2단계 경쟁","tool":"search_admin_rule","group":"B","topic":True},
    # Group C: 중소·정책기업 법령
    {"id":"sme_purchase_act","name":"중소기업제품 구매촉진 및 판로지원법","query":"중소기업제품 구매촉진 및 판로지원에 관한 법률","tool":"search_law","group":"C","mst":"277129"},
    {"id":"sme_purchase_decree","name":"중소기업제품 구매촉진법 시행령","query":"중소기업제품 구매촉진 및 판로지원에 관한 법률 시행령","tool":"search_law","group":"C","mst":"281341"},
    {"id":"sme_competition_items","name":"중소기업자간 경쟁제품 지정내역","query":"중소기업자간 경쟁제품 직접구매 대상품목","tool":"search_admin_rule","group":"C","topic":True},
    {"id":"direct_production","name":"직접생산확인 관련 기준","query":"직접생산확인","tool":"search_admin_rule","group":"C","topic":True},
    {"id":"women_enterprise_act","name":"여성기업지원법","query":"여성기업지원에 관한 법률","tool":"search_law","group":"C"},
    {"id":"women_enterprise_decree","name":"여성기업지원법 시행령","query":"여성기업지원에 관한 법률 시행령","tool":"search_law","group":"C"},
    {"id":"disabled_enterprise_act","name":"장애인기업활동 촉진법","query":"장애인기업활동 촉진법","tool":"search_law","group":"C"},
    {"id":"disabled_enterprise_decree","name":"장애인기업활동 촉진법 시행령","query":"장애인기업활동 촉진법 시행령","tool":"search_law","group":"C"},
    {"id":"social_enterprise_act","name":"사회적기업 육성법","query":"사회적기업 육성법","tool":"search_law","group":"C"},
    {"id":"social_enterprise_decree","name":"사회적기업 육성법 시행령","query":"사회적기업 육성법 시행령","tool":"search_law","group":"C"},
    # Group D: 혁신·우수조달·기술개발
    {"id":"innovation_product","name":"혁신제품 관련 조달청 고시·지침","query":"혁신제품 구매","tool":"search_admin_rule","group":"D","topic":True},
    {"id":"innovation_prototype","name":"혁신시제품 지정 및 구매 관련 기준","query":"혁신시제품 지정","tool":"search_admin_rule","group":"D","topic":True},
    {"id":"excellent_procurement","name":"우수조달물품 지정관리 규정","query":"우수조달물품 지정관리","tool":"search_admin_rule","group":"D","topic":False},
    {"id":"tech_priority_purchase","name":"기술개발제품 우선구매 관련 기준","query":"기술개발제품 우선구매","tool":"search_admin_rule","group":"D","topic":True},
    # Group E: 부산시 자치법규
    {"id":"busan_local_product","name":"부산광역시 지역상품 우선구매 관련 조례","query":"부산광역시 지역상품 우선구매","tool":"chain_ordinance_compare","group":"E"},
    {"id":"busan_local_company","name":"부산광역시 지역업체·지역상품 우대 관련 자치법규","query":"부산광역시 지역업체 우대","tool":"chain_ordinance_compare","group":"E"},
    # Group F: 공공기관·공기업·준정부기관 계약기준
    {"id":"public_institution_act","name":"공공기관의 운영에 관한 법률","query":"공공기관의 운영에 관한 법률","tool":"search_law","group":"F"},
    {"id":"public_institution_decree","name":"공공기관의 운영에 관한 법률 시행령","query":"공공기관의 운영에 관한 법률 시행령","tool":"search_law","group":"F"},
    {"id":"public_corp_contract_rule","name":"공기업ㆍ준정부기관 계약사무규칙","query":"공기업 준정부기관 계약사무규칙","tool":"search_law","group":"F","mst":"285569"},
    {"id":"public_corp_accounting_rule","name":"공기업ㆍ준정부기관 회계사무규칙","query":"공기업 준정부기관 회계사무규칙","tool":"search_law","group":"F"},
]

# ─── MCP 호출 래퍼 ───
def _call_mcp(func, *args, label="", **kwargs):
    """MCP 호출 + retry + sleep + 로깅. 에러 텍스트 감지."""
    for attempt in range(1 + MAX_RETRY):
        try:
            result = func(*args, **kwargs)
            # MCP 래퍼가 에러를 텍스트로 반환하는 경우 감지
            if isinstance(result, str) and result.startswith("MCP 호출 오류"):
                raise RuntimeError(result[:120])
            time.sleep(SLEEP_BETWEEN_CALLS)
            return result
        except Exception as e:
            print(f"    [{'RETRY' if attempt < MAX_RETRY else 'FAIL'}] {label}: {e}")
            if attempt < MAX_RETRY:
                time.sleep(SLEEP_BETWEEN_CALLS * 2)
    return None

def _parse_mcp_text(text):
    """MCP 텍스트 응답에서 MST, rule_id 등을 추출."""
    if not text:
        return {}
    info = {}
    # MST 추출
    mst_match = re.search(r'MST[:\s]*(\d+)', text)
    if mst_match:
        info["mst"] = mst_match.group(1)
    # 법령ID
    law_id_match = re.search(r'법령ID[:\s]*(\d+)', text)
    if law_id_match:
        info["law_id"] = law_id_match.group(1)
    # 시행일
    eff_match = re.search(r'시행[일날짜]*[:\s]*([\d./-]+)', text)
    if eff_match:
        info["effective_date"] = eff_match.group(1)
    return info

def _extract_discovered_sources(text, seed_id, via_tool):
    """MCP 응답 텍스트에서 자동 발견된 하위 법령/행정규칙/해석례를 추출."""
    candidates = []
    if not text:
        return candidates
    # 행정규칙/고시/예규/훈령 언급 패턴
    patterns = [
        r'「([^」]+(?:고시|예규|훈령|지침|규정|기준|규칙))」',
        r'\'([^\']+(?:고시|예규|훈령|지침|규정|기준|규칙))\'',
        r'"([^"]+(?:고시|예규|훈령|지침|규정|기준|규칙))"',
    ]
    seen = set()
    for pat in patterns:
        for m in re.finditer(pat, text):
            name = m.group(1).strip()
            if name not in seen and len(name) > 4:
                seen.add(name)
                candidates.append({
                    "candidate_id": f"auto_{seed_id}_{len(candidates)}",
                    "name": name,
                    "source_type": "admin_rule_or_notice",
                    "discovered_from": seed_id,
                    "discovered_via": via_tool,
                    "raw_text_preview": text[max(0,m.start()-50):m.end()+100][:300],
                    "status": "candidate_needs_review",
                    "review_status": "candidate_needs_review",
                    "selected_as_primary": False,
                    "collected_at": datetime.now(KST).isoformat(),
                })
    return candidates


# ─── 7단계 파이프라인 ───
def collect_seed(seed: dict) -> dict:
    """단일 Seed에 대해 7단계 MCP 수집 파이프라인을 실행."""
    sid = seed["id"]
    name = seed["name"]
    tool = seed["tool"]
    query = seed["query"]
    group = seed["group"]
    print(f"\n{'='*60}")
    print(f"[{group}] {name} (id={sid})")
    print(f"{'='*60}")

    entry = {
        "seed_id": sid,
        "name": name,
        "group": group,
        "query": query,
        "tool": tool,
        "mst": seed.get("mst"),
        "status": "pending",
        "steps_completed": [],
        "steps_failed": [],
        "collected_at": datetime.now(KST).isoformat(),
        # 향후 스키마 전환용 필드
        "source_type": None,
        "law_id": None,
        "rule_id": None,
        "effective_date": None,
        "issuing_org": None,
        "law_system_tree": None,
        "annexes": None,
        "amendment_history": None,
        "citations_verified": None,
        "raw_search_result_preview": None,
        "discovered_candidates": [],
    }
    all_candidates = []

    # ── Step 1: 원천 식별 ──
    print(f"  Step 1: 원천 식별 ({tool})")
    step1_text = None
    if tool == "search_law":
        step1_text = _call_mcp(mcp.search_law, query, 3, label=f"search_law({query})")
        entry["source_type"] = "law"
        if step1_text:
            parsed = _parse_mcp_text(step1_text)
            entry["mst"] = entry.get("mst") or parsed.get("mst")
            entry["law_id"] = parsed.get("law_id")
            entry["effective_date"] = parsed.get("effective_date")
            entry["raw_search_result_preview"] = step1_text[:500]
            entry["steps_completed"].append("search_law")
        else:
            entry["steps_failed"].append("search_law")

    elif tool == "search_admin_rule":
        step1_text = _call_mcp(mcp.search_admin_rule, query, label=f"search_admin_rule({query})")
        entry["source_type"] = "admin_rule"
        if step1_text:
            entry["raw_search_result_preview"] = step1_text[:800]
            entry["steps_completed"].append("search_admin_rule")
            # 행정규칙 primary/candidate 분류
            _classify_admin_results(entry, step1_text, seed, all_candidates)
        else:
            entry["steps_failed"].append("search_admin_rule")

    elif tool == "chain_ordinance_compare":
        step1_text = _call_mcp(mcp.chain_ordinance_compare, query, label=f"chain_ordinance({query})")
        entry["source_type"] = "ordinance"
        if step1_text:
            entry["raw_search_result_preview"] = step1_text[:800]
            entry["steps_completed"].append("chain_ordinance_compare")
        else:
            entry["steps_failed"].append("chain_ordinance_compare")

    # ── Step 2: 법체계 탐색 ──
    print(f"  Step 2: chain_law_system")
    chain_text = _call_mcp(mcp.chain_law_system, seed.get("query", name), label=f"chain_law_system({name})")
    if chain_text:
        entry["law_system_tree"] = chain_text[:2000]
        entry["steps_completed"].append("chain_law_system")
        all_candidates.extend(_extract_discovered_sources(chain_text, sid, "chain_law_system"))
    else:
        entry["steps_failed"].append("chain_law_system")

    # ── Step 3: 별표·서식 수집 ──
    print(f"  Step 3: get_annexes")
    annex_query = seed.get("query", name)
    annex_text = _call_mcp(mcp.get_annexes, annex_query, label=f"get_annexes({annex_query})")
    if annex_text:
        entry["annexes"] = annex_text[:2000]
        entry["steps_completed"].append("get_annexes")
    else:
        entry["steps_failed"].append("get_annexes")

    # ── Step 4: 개정이력 ──
    print(f"  Step 4: chain_amendment_track")
    amend_text = _call_mcp(mcp.chain_amendment_track, seed.get("query", name), label=f"chain_amendment_track({name})")
    if amend_text:
        entry["amendment_history"] = amend_text[:2000]
        entry["steps_completed"].append("chain_amendment_track")
        eff = _parse_mcp_text(amend_text).get("effective_date")
        if eff:
            entry["effective_date"] = eff
    else:
        entry["steps_failed"].append("chain_amendment_track")

    # ── Step 5: 조문 인용 검증 ──
    print(f"  Step 5: verify_citations")
    if step1_text and len(step1_text) > 20:
        verify_text = _call_mcp(mcp.verify_citations, step1_text[:3000], label="verify_citations")
        if verify_text:
            entry["citations_verified"] = verify_text[:1000]
            entry["steps_completed"].append("verify_citations")
        else:
            entry["steps_failed"].append("verify_citations")
    else:
        entry["steps_failed"].append("verify_citations_skipped_no_source")

    # ── Step 6-7: 자동 발견 자료 수집 ──
    print(f"  Step 6-7: 자동 발견 자료 분류")
    entry["discovered_candidates"] = all_candidates

    # 최종 상태 판정
    if len(entry["steps_failed"]) == 0:
        entry["status"] = "verified"
    elif len(entry["steps_completed"]) > 0:
        entry["status"] = "partial"
    else:
        entry["status"] = "failed"

    completed = len(entry["steps_completed"])
    failed = len(entry["steps_failed"])
    print(f"  → {entry['status']} (completed={completed}, failed={failed}, candidates={len(all_candidates)})")
    return entry


def _classify_admin_results(entry, text, seed, all_candidates):
    """행정규칙 검색 결과를 primary_source + candidate로 분류."""
    is_topic = seed.get("topic", False)
    limit = CANDIDATE_LIMIT_TOPIC if is_topic else CANDIDATE_LIMIT_EXACT
    sid = seed["id"]

    # 결과에서 개별 규칙 항목 패턴 추출 시도
    items = re.split(r'\n(?=\d+[\.\)]\s)', text)
    if len(items) <= 1:
        items = re.split(r'\n---\n', text)

    primary_set = False
    for i, item in enumerate(items[:limit]):
        item_text = item.strip()
        if not item_text or len(item_text) < 10:
            continue

        # 메타데이터 추출
        title_match = re.search(r'[「\[]([^」\]]+)[」\]]', item_text)
        title = title_match.group(1) if title_match else item_text[:80]
        org_match = re.search(r'(행정안전부|기획재정부|조달청|중소벤처기업부|국토교통부|산업통상자원부|고용노동부)', item_text)
        issuing_org = org_match.group(1) if org_match else "unknown"
        eff_match = re.search(r'시행[일날짜]*[:\s]*([\d./-]+)', item_text)
        effective_date = eff_match.group(1) if eff_match else None
        rule_id_match = re.search(r'(?:ID|번호)[:\s]*(\d+)', item_text)
        rule_id = rule_id_match.group(1) if rule_id_match else None

        is_superseded = any(kw in item_text for kw in ["폐지", "실효", "만료", "효력상실"])

        if not primary_set and not is_superseded:
            # 첫 번째 유효 결과 → primary_source
            entry["rule_id"] = rule_id
            entry["issuing_org"] = issuing_org
            entry["effective_date"] = effective_date
            primary_set = True
            print(f"    → PRIMARY: {title[:60]}")
        else:
            # 나머지 → candidate
            status = "superseded_candidate" if is_superseded else "candidate_needs_review"
            all_candidates.append({
                "candidate_id": f"admin_{sid}_{i}",
                "name": title,
                "source_type": "admin_rule",
                "discovered_from": sid,
                "discovered_via": "search_admin_rule",
                "title": title,
                "issuing_org": issuing_org,
                "rule_id": rule_id,
                "effective_date": effective_date,
                "status": status,
                "review_status": status,
                "selected_as_primary": False,
                "match_reason": "topic_search" if is_topic else "exact_title_search",
                "raw_text_preview": item_text[:300],
                "collected_at": datetime.now(KST).isoformat(),
            })


# ─── Checkpoint 관리 ───
def _load_checkpoint():
    if os.path.exists(CHECKPOINT_PATH):
        with open(CHECKPOINT_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"completed_seeds": [], "registry": [], "candidates": []}

def _save_checkpoint(cp):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(CHECKPOINT_PATH, "w", encoding="utf-8") as f:
        json.dump(cp, f, ensure_ascii=False, indent=2)

def _save_results(registry, candidates):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(registry, f, ensure_ascii=False, indent=2)
    with open(CANDIDATE_PATH, "w", encoding="utf-8") as f:
        json.dump(candidates, f, ensure_ascii=False, indent=2)


# ─── 메인 ───
def main():
    parser = argparse.ArgumentParser(description="Legal Source Registry Builder (Offline ETL)")
    parser.add_argument("--group", default="A", help="실행할 그룹 (A/B/C/D/E/F/all)")
    parser.add_argument("--dry-run", action="store_true", help="MCP 호출 없이 목록만 출력")
    parser.add_argument("--resume", action="store_true", help="checkpoint에서 재개")
    args = parser.parse_args()

    target_groups = list("ABCDEF") if args.group.lower() == "all" else [g.upper() for g in args.group.split(",")]
    seeds = [s for s in SEED_LAWS if s["group"] in target_groups]

    print(f"{'='*60}")
    print(f"Legal Source Registry Builder — Phase 7-B ETL")
    print(f"{'='*60}")
    print(f"대상 그룹: {target_groups} ({len(seeds)}건)")
    print(f"MCP 엔드포인트: {mcp.MCP_BASE_URL}")
    print(f"설정: sleep={SLEEP_BETWEEN_CALLS}s, timeout={MCP_TIMEOUT}s, retry={MAX_RETRY}")
    print()

    if args.dry_run:
        print("[DRY-RUN] Seed 목록:")
        for s in seeds:
            print(f"  [{s['group']}] {s['id']}: {s['name']} (tool={s['tool']})")
        print(f"\n총 {len(seeds)}건, 예상 MCP 호출: ~{len(seeds)*6}회")
        return

    # checkpoint
    cp = _load_checkpoint() if args.resume else {"completed_seeds": [], "registry": [], "candidates": []}
    completed_ids = set(cp["completed_seeds"])

    registry = list(cp["registry"])
    candidates = list(cp["candidates"])

    start_time = time.time()

    for i, seed in enumerate(seeds):
        if seed["id"] in completed_ids:
            print(f"\n[SKIP] {seed['id']} (already in checkpoint)")
            continue

        print(f"\n[{i+1}/{len(seeds)}] Processing...")
        entry = collect_seed(seed)

        # candidate 분리
        seed_candidates = entry.pop("discovered_candidates", [])
        registry.append(entry)
        candidates.extend(seed_candidates)

        # checkpoint 저장
        cp["completed_seeds"].append(seed["id"])
        cp["registry"] = registry
        cp["candidates"] = candidates
        _save_checkpoint(cp)

    # 최종 저장
    _save_results(registry, candidates)
    elapsed = int(time.time() - start_time)

    # 요약
    print(f"\n{'='*60}")
    print(f"수집 완료 ({elapsed}초)")
    print(f"{'='*60}")
    status_counts = {}
    for r in registry:
        s = r["status"]
        status_counts[s] = status_counts.get(s, 0) + 1
    for s, c in status_counts.items():
        print(f"  {s}: {c}건")
    print(f"  candidates: {len(candidates)}건")
    print(f"\n산출물:")
    print(f"  {REGISTRY_PATH}")
    print(f"  {CANDIDATE_PATH}")


if __name__ == "__main__":
    main()
