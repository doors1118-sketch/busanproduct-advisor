"""
Phase 7-B 법령체계도 기반 누락분 수집 스크립트
엑셀 3개에서 node/relation 추출 → 기존 registry 대조 → 누락분만 수집 → patch 생성

지시문: antigravity_phase7b_chart_gap_collection_directive_20260504.md
"""
import os, sys, json, re, time, hashlib
import xlrd
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
import requests

sys.stdout.reconfigure(encoding="utf-8")

# ─── 설정 ───
_root = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(_root, "data")
os.makedirs(DATA_DIR, exist_ok=True)

BASE_URL = "http://www.law.go.kr/DRF"
OC = os.getenv("LAW_API_OC", "busanproduct1")
KST = timezone(timedelta(hours=9))
SLEEP = 1.0
TIMEOUT = 15

EXCEL_FILES = [
    r"C:\Users\COMTREE\Desktop\법령체계도_국가를_당사자로_하는_계약에_관한_법률.xls",
    r"C:\Users\COMTREE\Desktop\법령체계도_공기업ㆍ준정부기관_계약사무규칙.xls",
    r"C:\Users\COMTREE\Desktop\법령체계도_지방자치단체를_당사자로_하는_계약에_관한_법률_시행규칙.xls",
]

# ─── Step 1: 기존 파일 로드 ───
def load_existing():
    reg_path = os.path.join(DATA_DIR, "legal_source_registry.json")
    cand_path = os.path.join(DATA_DIR, "legal_source_candidate.json")
    rel_path = os.path.join(DATA_DIR, "legal_relation_seed.json")

    registry = json.load(open(reg_path, encoding="utf-8")) if os.path.exists(reg_path) else []
    candidates = json.load(open(cand_path, encoding="utf-8")) if os.path.exists(cand_path) else []
    relations = json.load(open(rel_path, encoding="utf-8")) if os.path.exists(rel_path) else []
    return registry, candidates, relations


# ─── 명칭 정규화 ───
def normalize_name(raw):
    """법령명 정규화: 시행정보/괄호 제거, 약칭 확장, 표기 통일"""
    if not raw:
        return ""
    s = raw.strip()
    # 모든 대괄호 [...] 제거 (시행일, 법률호, 제명개정 등)
    s = re.sub(r'\[.*?\]', '', s)
    # (계약예규) 등 유형 접두사 제거
    s = re.sub(r'^\([가-힣]+\)\s*', '', s)
    # 공백 정리
    s = re.sub(r'\s+', ' ', s).strip()
    # 표기 통일
    s = s.replace('·', 'ㆍ')
    # 약칭 확장
    abbrevs = {
        "국가계약법": "국가를 당사자로 하는 계약에 관한 법률",
        "지방계약법": "지방자치단체를 당사자로 하는 계약에 관한 법률",
        "공공기관운영법": "공공기관의 운영에 관한 법률",
    }
    for short, full in abbrevs.items():
        if s == short:
            s = full
    return s


def guess_source_type(name):
    """명칭에서 source_type 추정"""
    if not name:
        return "unknown"
    if re.search(r'시행규칙|부령', name):
        return "law_rule"
    if re.search(r'시행령|대통령령', name):
        return "law_decree"
    if re.search(r'법률|에 관한 법$|촉진법$|지원법$|육성법$', name):
        return "law"
    if re.search(r'사무규칙|회계.*규칙', name):
        return "law_rule"
    if re.search(r'훈령', name):
        return "admrul_instruction"
    if re.search(r'예규|집행기준|결정기준', name):
        return "admrul_regulation"
    if re.search(r'고시|지침|기준|규정|내역|요령|세칙', name):
        return "admrul_notice"
    if re.search(r'조례|자치법규', name):
        return "ordinance"
    return "admrul"


def guess_relation_type(parent_type, child_type):
    """부모-자식 source_type으로 관계 유형 추정"""
    if parent_type == "law" and child_type == "law_decree":
        return "enforcement_decree"
    if child_type == "law_rule":
        return "enforcement_rule"
    if "admrul" in child_type:
        return "delegated_admin_rule"
    if child_type == "ordinance":
        return "local_ordinance"
    return "related_admin_rule"


# ─── Step 2: 엑셀 파싱 ───
def parse_excel_files():
    all_nodes = []
    all_relations = []

    for fp in EXCEL_FILES:
        fname = os.path.basename(fp)
        wb = xlrd.open_workbook(fp)
        sh = wb.sheet_by_index(0)

        # 각 행에서 가장 오른쪽 비어있지 않은 셀 = node, 열 위치 = 계층
        hierarchy_stack = {}  # col -> node_name

        for r in range(sh.nrows):
            # 모든 셀 값 읽기
            row_vals = []
            rightmost_col = -1
            rightmost_val = ""
            for c in range(sh.ncols):
                v = str(sh.cell_value(r, c)).strip()
                row_vals.append(v)
                if v and v != "▼ 상하위법" and v != "행정규칙":
                    rightmost_col = c
                    rightmost_val = v

            if rightmost_col < 0 or not rightmost_val:
                continue

            # "행정규칙" 헤더 행 스킵
            if rightmost_val in ("▼ 상하위법", "행정규칙"):
                continue

            norm = normalize_name(rightmost_val)
            if not norm:
                continue

            stype = guess_source_type(norm)

            node = {
                "node_name": norm,
                "raw_cell_value": rightmost_val[:100],
                "source_type": stype,
                "source_file": fname,
                "row_no": r,
                "col_no": rightmost_col,
            }
            all_nodes.append(node)

            # 계층 스택 업데이트
            hierarchy_stack[rightmost_col] = norm
            # 이 열보다 큰 열 제거
            for k in list(hierarchy_stack.keys()):
                if k > rightmost_col:
                    del hierarchy_stack[k]

            # 부모 찾기: 이 열보다 작은 열 중 가장 가까운 것
            parent_col = -1
            parent_name = None
            for k in sorted(hierarchy_stack.keys()):
                if k < rightmost_col:
                    parent_col = k
                    parent_name = hierarchy_stack[k]

            if parent_name and parent_name != norm:
                parent_type = guess_source_type(parent_name)
                rel = {
                    "relation_id": hashlib.md5(f"{parent_name}|{norm}".encode()).hexdigest()[:12],
                    "parent_source_name": parent_name,
                    "child_source_name": norm,
                    "parent_source_id": None,
                    "child_source_id": None,
                    "relation_type": guess_relation_type(parent_type, stype),
                    "discovered_via": "uploaded_xls",
                    "source_file": fname,
                    "row_no": r,
                    "confidence": "high" if rightmost_col - parent_col == 1 else "medium",
                    "review_status": "candidate_needs_review",
                }
                all_relations.append(rel)

    return all_nodes, all_relations


# ─── Step 4: 기존 registry와 대조 ───
def match_against_existing(nodes, registry, candidates):
    # 기존 수집된 명칭 set 구축
    reg_names = set()
    reg_map = {}
    for r in registry:
        n = normalize_name(r.get("name", ""))
        n2 = normalize_name(r.get("law_name_official", "") or "")
        reg_names.add(n)
        if n2:
            reg_names.add(n2)
        reg_map[n] = r.get("seed_id", "")
        if n2:
            reg_map[n2] = r.get("seed_id", "")

    cand_names = set()
    for c in candidates:
        cn = normalize_name(c.get("name", "") or c.get("node_name", ""))
        if cn:
            cand_names.add(cn)

    already_collected = []
    missing_primary = []
    ambiguous = []
    out_of_scope = []

    seen = set()
    for node in nodes:
        nn = node["node_name"]
        if nn in seen:
            continue
        seen.add(nn)

        if nn in reg_names:
            node["match_status"] = "already_collected"
            node["matched_seed_id"] = reg_map.get(nn, "")
            already_collected.append(node)
        elif nn in cand_names:
            node["match_status"] = "existing_candidate"
            already_collected.append(node)
        elif _is_out_of_scope(nn):
            node["match_status"] = "out_of_scope"
            out_of_scope.append(node)
        else:
            # 유사 명칭 검사
            similar = _find_similar(nn, reg_names)
            if similar:
                node["match_status"] = "ambiguous_candidate"
                node["similar_to"] = similar
                ambiguous.append(node)
            else:
                node["match_status"] = "missing_primary"
                missing_primary.append(node)

    return already_collected, missing_primary, ambiguous, out_of_scope


def _is_out_of_scope(name):
    """계약·조달·지역업체 구매와 직접 관련 없는 항목"""
    oos_keywords = ["건축법", "주택법", "도로법", "전기사업법", "산업안전", "소방", "환경"]
    return any(k in name for k in oos_keywords)


def _find_similar(name, existing_names):
    """유사명칭 검색 (부분 포함)"""
    for en in existing_names:
        # 핵심 키워드 비교
        if len(name) > 5 and len(en) > 5:
            if name[:5] == en[:5] or name in en or en in name:
                return en
    return None


# ─── Step 5: 누락분 수집 ───
def api_get(endpoint, params):
    params["OC"] = OC
    params["type"] = "XML"
    try:
        r = requests.get(f"{BASE_URL}/{endpoint}", params=params, timeout=TIMEOUT)
        r.raise_for_status()
        if len(r.content) < 10:
            return None
        return ET.fromstring(r.content)
    except Exception as e:
        return None


def _xt(root, xpath):
    el = root.find(xpath)
    return el.text.strip() if el is not None and el.text else None


def collect_missing(missing_nodes, ambiguous_nodes):
    """누락분 수집: missing_primary + ambiguous_candidate"""
    registry_patch = []
    candidate_patch = []
    failed_list = []
    targets = missing_nodes + ambiguous_nodes

    for i, node in enumerate(targets):
        nn = node["node_name"]
        stype = node["source_type"]
        status = node["match_status"]
        print(f"  [{i+1}/{len(targets)}] {nn} ({stype}, {status})")

        # 검색 쿼리에서 잔여 브래킷/접두사 제거
        search_query = re.sub(r'\[.*?\]', '', nn).strip()
        search_query = re.sub(r'^\([가-힣]+\)\s*', '', search_query).strip()

        if stype in ("law", "law_decree", "law_rule"):
            result = _collect_law(search_query, node)
        elif stype == "ordinance":
            result = _collect_ordinance(nn, node)
        else:
            result = _collect_admrul(search_query, node)

        if result:
            if result.get("collection_status") == "collected":
                registry_patch.append(result)
                print(f"    → collected | {result.get('article_count',0)} articles, {result.get('full_text_length',0)} chars")
            elif result.get("collection_status") == "partial":
                candidate_patch.append(result)
                print(f"    → partial/candidate")
            else:
                failed_list.append(result)
                print(f"    → failed")
        else:
            failed_list.append({"node_name": nn, "source_type": stype, "error": "no_api_response"})
            print(f"    → failed (no response)")

        time.sleep(SLEEP)

    return registry_patch, candidate_patch, failed_list


def _collect_law(name, node):
    """법률/시행령/시행규칙 수집"""
    root = api_get("lawSearch.do", {"target": "law", "query": name, "display": "3"})
    if root is None:
        return {"node_name": name, "collection_status": "api_failed", "error": "search_failed"}

    items = root.findall(".//law")
    if not items:
        return {"node_name": name, "collection_status": "api_failed", "error": "no_search_results"}

    # 첫 번째 결과
    top = items[0]
    mst = top.findtext("법령일련번호") or ""
    law_name = top.findtext("법령명한글") or name

    result = {
        "node_name": name,
        "law_name_official": law_name,
        "source_type": node["source_type"],
        "mst": mst,
        "law_id": top.findtext("법령ID") or "",
        "effective_date": top.findtext("시행일자") or "",
        "issuing_org": top.findtext("소관부처명") or "",
        "source_file": node.get("source_file", ""),
        "match_status": node.get("match_status", ""),
        "collected_at": datetime.now(KST).isoformat(),
        "review_status": "candidate_needs_review",
    }

    # 전문 조회
    if mst:
        time.sleep(SLEEP)
        full_root = api_get("lawService.do", {"target": "law", "MST": mst})
        if full_root is not None:
            articles = full_root.findall(".//조문단위")
            annexes = full_root.findall(".//별표단위")
            text_len = sum(len(_xt(jo, "조문내용") or "") for jo in articles)
            result["article_count"] = len(articles)
            result["annex_count"] = len(annexes)
            result["full_text_length"] = text_len
            result["collection_status"] = "collected"
        else:
            result["collection_status"] = "partial"
    else:
        result["collection_status"] = "partial"

    return result


def _collect_admrul(name, node):
    """행정규칙 수집"""
    root = api_get("lawSearch.do", {"target": "admrul", "query": name, "display": "5"})
    if root is None:
        return {"node_name": name, "collection_status": "api_failed", "error": "search_failed"}

    items = root.findall(".//admrul")
    if not items:
        return {"node_name": name, "collection_status": "api_failed", "error": "no_search_results"}

    top = items[0]
    serial = top.findtext("행정규칙일련번호") or ""
    rule_name = top.findtext("행정규칙명") or name

    result = {
        "node_name": name,
        "law_name_official": rule_name,
        "source_type": node["source_type"],
        "admrul_serial": serial,
        "law_id": top.findtext("행정규칙ID") if top.findtext("행정규칙ID") else "",
        "effective_date": top.findtext("발령일자") or top.findtext("시행일자") or "",
        "issuing_org": top.findtext("소관부처명") or "",
        "source_file": node.get("source_file", ""),
        "match_status": node.get("match_status", ""),
        "collected_at": datetime.now(KST).isoformat(),
        "review_status": "candidate_needs_review",
    }

    # 전문 조회
    if serial:
        time.sleep(SLEEP)
        full_root = api_get("lawService.do", {"target": "admrul", "ID": serial})
        if full_root is not None:
            # 조문 카운트
            art_count = 0
            for child in full_root:
                if child.tag == "조문내용" and child.text:
                    art_count += 1
            for jo in full_root.findall(".//조문단위"):
                art_count += 1

            annex_count = 0
            for bp in full_root.findall(".//별표"):
                annex_count += len(bp.findall("별표내용"))
            for bp in full_root.findall(".//별표단위"):
                annex_count += 1

            text_len = 0
            for child in full_root:
                if child.tag == "조문내용" and child.text:
                    text_len += len(child.text)

            result["article_count"] = art_count
            result["annex_count"] = annex_count
            result["full_text_length"] = text_len
            result["collection_status"] = "collected"
        else:
            result["collection_status"] = "partial"
    else:
        result["collection_status"] = "partial"

    return result


def _collect_ordinance(name, node):
    """조례 수집 시도 (법제처 API에서 ordi 미지원 시 partial)"""
    return {
        "node_name": name,
        "source_type": "ordinance",
        "collection_status": "partial",
        "error": "ordinance_api_not_supported",
        "source_file": node.get("source_file", ""),
        "match_status": node.get("match_status", ""),
        "review_status": "candidate_needs_review",
    }


# ─── 메인 ───
def main():
    print("=" * 60)
    print("Phase 7-B 법령체계도 기반 누락분 수집")
    print(datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST"))
    print("=" * 60)

    # Step 1: 기존 로드
    print("\n[Step 1] 기존 registry/candidate 로드")
    registry, candidates, relations = load_existing()
    print(f"  Registry: {len(registry)}건, Candidates: {len(candidates)}건, Relations: {len(relations)}건")

    # Step 2: 엑셀 파싱
    print("\n[Step 2] 엑셀 파싱")
    nodes, rels = parse_excel_files()
    print(f"  추출 nodes: {len(nodes)}건, relations: {len(rels)}건")
    for fp in EXCEL_FILES:
        fn = os.path.basename(fp)
        n_count = sum(1 for n in nodes if n["source_file"] == fn)
        r_count = sum(1 for r in rels if r["source_file"] == fn)
        print(f"    {fn}: nodes={n_count}, relations={r_count}")

    # Step 3-4: 대조
    print("\n[Step 3-4] 기존 registry와 대조")
    already, missing, ambiguous, oos = match_against_existing(nodes, registry, candidates)
    print(f"  already_collected: {len(already)}건")
    print(f"  missing_primary: {len(missing)}건")
    print(f"  ambiguous_candidate: {len(ambiguous)}건")
    print(f"  out_of_scope: {len(oos)}건")

    if missing:
        print("\n  누락 목록:")
        for m in missing:
            print(f"    - {m['node_name']} ({m['source_type']}) [{m['source_file']}]")

    if ambiguous:
        print("\n  유사명칭 목록:")
        for a in ambiguous:
            print(f"    - {a['node_name']} ≈ {a.get('similar_to','')} ({a['source_type']})")

    # Step 5: 누락분 수집
    print("\n[Step 5] 누락분 추가 수집")
    to_collect = missing + ambiguous
    if not to_collect:
        print("  수집 대상 없음")
        reg_patch, cand_patch, failed = [], [], []
    else:
        print(f"  수집 대상: {len(to_collect)}건")
        reg_patch, cand_patch, failed = collect_missing(missing, ambiguous)

    # 출력 파일 생성
    print("\n[Step 6] 출력 파일 생성")
    outputs = {
        "legal_system_chart_nodes.json": nodes,
        "legal_system_chart_relations.json": rels,
        "legal_source_missing_from_charts.json": missing,
        "legal_source_already_collected_map.json": already,
        "legal_source_registry_patch_from_charts.json": reg_patch,
        "legal_source_candidate_patch_from_charts.json": cand_patch,
        "legal_relation_seed_patch_from_charts.json": rels,
        "legal_chart_collection_log.json": {
            "run_at": datetime.now(KST).isoformat(),
            "excel_files": [os.path.basename(f) for f in EXCEL_FILES],
            "total_nodes": len(nodes),
            "total_relations": len(rels),
            "already_collected": len(already),
            "missing_primary": len(missing),
            "ambiguous_candidate": len(ambiguous),
            "out_of_scope": len(oos),
            "newly_collected": len(reg_patch),
            "candidate_added": len(cand_patch),
            "failed": len(failed),
        },
        "legal_chart_failed_or_partial_list.json": failed,
    }

    for fname, data in outputs.items():
        path = os.path.join(DATA_DIR, fname)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"  ✓ {fname} ({len(data) if isinstance(data, list) else 'obj'})")

    # 최종 보고
    print("\n" + "=" * 60)
    print("작업 완료!")
    print(f"  엑셀 추출: {len(nodes)} nodes, {len(rels)} relations")
    print(f"  already_collected: {len(already)}건")
    print(f"  missing_primary: {len(missing)}건")
    print(f"  ambiguous_candidate: {len(ambiguous)}건")
    print(f"  newly_collected: {len(reg_patch)}건")
    print(f"  candidate_added: {len(cand_patch)}건")
    print(f"  failed: {len(failed)}건")
    print(f"  기존 registry 병합 여부: 미병합 (patch만 생성)")
    print("=" * 60)


if __name__ == "__main__":
    main()
