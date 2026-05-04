"""Phase 7-B 최종 결과 JSON 생성"""
import json, sys, os
from datetime import datetime, timezone, timedelta

sys.stdout.reconfigure(encoding="utf-8")
KST = timezone(timedelta(hours=9))
base = r"c:\Users\COMTREE\Desktop\메뉴얼 제작\app\data"

# 모든 데이터 로드
reg = json.load(open(os.path.join(base, "legal_source_registry.json"), encoding="utf-8"))
patch = json.load(open(os.path.join(base, "legal_source_registry_patch_from_charts.json"), encoding="utf-8"))
cand = json.load(open(os.path.join(base, "legal_source_candidate_patch_from_charts.json"), encoding="utf-8"))
failed = json.load(open(os.path.join(base, "legal_chart_failed_or_partial_list.json"), encoding="utf-8"))
nodes = json.load(open(os.path.join(base, "legal_system_chart_nodes.json"), encoding="utf-8"))
rels = json.load(open(os.path.join(base, "legal_system_chart_relations.json"), encoding="utf-8"))
already = json.load(open(os.path.join(base, "legal_source_already_collected_map.json"), encoding="utf-8"))

# 통계
reg_arts = sum(r.get("article_count", 0) for r in reg)
reg_text = sum(r.get("full_text_length", 0) for r in reg)
p_arts = sum(r.get("article_count", 0) for r in patch)
p_text = sum(r.get("full_text_length", 0) for r in patch)

from collections import Counter
patch_types = dict(Counter(r.get("source_type", "unknown") for r in patch))
reg_types = dict(Counter(r.get("source_type", "unknown") for r in reg))

# source별 상세 목록 (patch)
patch_sources = []
for r in patch:
    patch_sources.append({
        "name": r.get("law_name_official") or r.get("node_name", ""),
        "source_type": r.get("source_type", ""),
        "article_count": r.get("article_count", 0),
        "full_text_length": r.get("full_text_length", 0),
        "effective_date": r.get("effective_date", ""),
        "issuing_org": r.get("issuing_org", ""),
        "collection_status": r.get("collection_status", ""),
        "match_status": r.get("match_status", ""),
    })

# 최종 JSON
final = {
    "report_title": "Phase 7-B 법령DB 직접 수집 및 체계도 기반 누락분 수집 최종 보고서",
    "report_date": datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"),
    "작업_단계": [
        {
            "단계": "1단계: 법제처 직접 API 수집",
            "설명": "NCP MCP 서버의 법제처 TCP 차단을 우회하여 사무실 PC에서 법제처 Open API를 직접 호출",
            "스크립트": "app/direct_law_collector.py",
            "대상": "37건 Seed 법령 (Group A~F)",
            "결과": {
                "verified": 35,
                "skipped_pdf": 2,
                "failed": 0,
                "소요시간": "약 80초",
            },
            "비고": "행정규칙 전문 수집 기능 보강 후 재실행 완료",
        },
        {
            "단계": "2단계: 법령체계도 엑셀 기반 누락분 수집",
            "설명": "법제처 법령체계도 엑셀 3개에서 node/relation 추출 후 기존 registry와 대조하여 누락분만 추가 수집",
            "스크립트": "app/chart_gap_collector.py",
            "입력_엑셀": [
                "법령체계도_국가를_당사자로_하는_계약에_관한_법률.xls",
                "법령체계도_공기업ㆍ준정부기관_계약사무규칙.xls",
                "법령체계도_지방자치단체를_당사자로_하는_계약에_관한_법률_시행규칙.xls",
            ],
            "엑셀_추출": {
                "total_nodes": len(nodes),
                "total_relations": len(rels),
            },
            "대조_결과": {
                "already_collected": len(already),
                "missing_primary": 219,
                "ambiguous_candidate": 9,
                "out_of_scope": 4,
            },
            "수집_결과": {
                "collected_to_registry_patch": len(patch),
                "collected_to_candidate_patch": len(cand),
                "failed": len(failed),
                "total_articles": p_arts,
                "total_text_chars": p_text,
                "total_text_kb": round(p_text / 1024, 1),
            },
        },
        {
            "단계": "3단계: 실패건 복구 수집",
            "설명": "검색어 축약 전략으로 실패 11건 중 5건 복구 (고시금액 포함)",
            "복구건수": 5,
            "잔여실패": len(failed),
        },
    ],
    "최종_통계": {
        "기존_registry_sources": len(reg),
        "기존_registry_articles": reg_arts,
        "기존_registry_text_chars": reg_text,
        "patch_sources": len(patch),
        "patch_articles": p_arts,
        "patch_text_chars": p_text,
        "candidate_sources": len(cand),
        "failed_sources": len(failed),
        "chart_nodes": len(nodes),
        "chart_relations": len(rels),
        "합산_total_sources": len(reg) + len(patch),
        "합산_total_articles": reg_arts + p_arts,
        "합산_total_text_chars": reg_text + p_text,
        "합산_total_text_kb": round((reg_text + p_text) / 1024, 1),
    },
    "patch_유형별_분포": patch_types,
    "실패_목록": [
        {
            "name": f.get("node_name", ""),
            "error": f.get("error", ""),
            "사유": (
                "엑셀 헤더 (법령 아님)" if "▼" in f.get("node_name", "") else
                "자치법규 API 미지원 (조례)" if "조례" in f.get("node_name", "") else
                "법제처 미등록 고시"
            ),
        }
        for f in failed
    ],
    "생성된_파일": [
        {"파일": "legal_source_registry.json", "유형": "기존 registry (Group B)", "건수": len(reg)},
        {"파일": "legal_source_registry_patch_from_charts.json", "유형": "신규 수집 patch", "건수": len(patch)},
        {"파일": "legal_source_candidate_patch_from_charts.json", "유형": "후보 (review 필요)", "건수": len(cand)},
        {"파일": "legal_system_chart_nodes.json", "유형": "체계도 node 목록", "건수": len(nodes)},
        {"파일": "legal_system_chart_relations.json", "유형": "체계도 relation 목록", "건수": len(rels)},
        {"파일": "legal_source_missing_from_charts.json", "유형": "누락 분석 결과", "건수": 219},
        {"파일": "legal_source_already_collected_map.json", "유형": "기존 매칭 결과", "건수": len(already)},
        {"파일": "legal_chart_failed_or_partial_list.json", "유형": "실패/부분 수집 목록", "건수": len(failed)},
        {"파일": "legal_chart_collection_log.json", "유형": "수집 로그", "건수": "obj"},
        {"파일": "legal_relation_seed_patch_from_charts.json", "유형": "관계 seed patch", "건수": len(rels)},
    ],
    "금지사항_준수": {
        "기존_33개_Seed_재수집": False,
        "기존_registry_덮어쓰기": False,
        "운영_legal_rule_변경": False,
        "Production_배포": False,
        "ChromaDB_ingest": False,
        "API_key_노출": False,
    },
    "patch_상세_목록": patch_sources,
}

out_path = os.path.join(base, "phase7b_final_collection_report.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(final, f, ensure_ascii=False, indent=2)

print("Saved: %s" % out_path)
print("Total entries in report JSON: %d patch sources" % len(patch_sources))
