"""
Phase 7-B Legal Source Registry 적재 결과 감사 스크립트
백업 ZIP에서 추출한 데이터를 분석하여 JSON 보고서를 생성합니다.
"""
import json, os, glob

BASE = r"C:\Users\COMTREE\Desktop\메뉴얼_제작_백업_추출"
OUT_PATH = r"C:\Users\COMTREE\Desktop\메뉴얼 제작\phase7b_legal_registry_audit_report.json"

# === 1. Phase 7-B Registry 결과 분석 ===
reg_path = os.path.join(BASE, "app", "data", "legal_source_registry.json")
with open(reg_path, encoding="utf-8") as f:
    registry = json.load(f)

status_counts = {"verified": 0, "partial": 0, "failed": 0}
seeds_detail = []
for r in registry:
    s = r["status"]
    status_counts[s] = status_counts.get(s, 0) + 1
    has_data = r.get("raw_search_result_preview") is not None
    seeds_detail.append({
        "seed_id": r["seed_id"],
        "name": r["name"],
        "group": r["group"],
        "status": r["status"],
        "tool": r["tool"],
        "steps_completed": len(r.get("steps_completed", [])),
        "steps_failed": len(r.get("steps_failed", [])),
        "has_data": has_data
    })

# === 2. law_hierarchy_2.json (기존 MCP 수집 데이터) ===
lh_path = os.path.join(BASE, "app", "law_hierarchy_2.json")
lh_data = {}
if os.path.exists(lh_path):
    with open(lh_path, encoding="utf-8") as f:
        lh = json.load(f)
    for k, v in lh.items():
        lh_data[k] = {
            "name": k,
            "text_length": len(v),
            "has_content": len(v) > 100,
            "preview": v[:200] + "..." if len(v) > 200 else v
        }

# === 3. 로컬 텍스트 파일 법령 원문 ===
txt_files = []
seen = set()
patterns = ["*텍스트*", "*시행령*", "*조달*", "*계약*", "*지역*", "*별표*", "*집행기준*", "*낙찰*"]
for pat in patterns:
    for f in glob.glob(os.path.join(BASE, pat + ".txt")):
        bn = os.path.basename(f)
        if bn not in seen:
            seen.add(bn)
            sz = os.path.getsize(f)
            txt_files.append({"filename": bn, "size_bytes": sz, "size_kb": round(sz / 1024, 1)})

# === 4. PDF 법령/규정 파일 ===
pdf_files = []
for f in glob.glob(os.path.join(BASE, "*.pdf")):
    bn = os.path.basename(f)
    sz = os.path.getsize(f)
    pdf_files.append({"filename": bn, "size_bytes": sz, "size_kb": round(sz / 1024, 1)})

# === 5. ChromaDB 백업 ===
chroma_path = os.path.join(BASE, "app", ".chroma_backup_20260423")
chroma_exists = os.path.isdir(chroma_path)
chroma_file_count = 0
if chroma_exists:
    for root, dirs, files in os.walk(chroma_path):
        chroma_file_count += len(files)

# === 6. candidate.json ===
cand_path = os.path.join(BASE, "app", "data", "legal_source_candidate.json")
with open(cand_path, encoding="utf-8") as f:
    candidates = json.load(f)

# === 7. 추가: HWPX 법령 파일 ===
hwpx_files = []
for f in glob.glob(os.path.join(BASE, "*.hwpx")):
    bn = os.path.basename(f)
    sz = os.path.getsize(f)
    hwpx_files.append({"filename": bn, "size_bytes": sz, "size_kb": round(sz / 1024, 1)})

# === 종합 보고서 ===
total_seeds = len(registry)
report = {
    "report_title": "Phase 7-B Legal Source Registry 적재 결과 분석 보고서",
    "report_date": "2026-05-04T09:40:00+09:00",
    "backup_source": r"C:\Users\COMTREE\Desktop\메뉴얼_제작_백업.zip",

    "section_1_registry_pipeline_result": {
        "description": "build_legal_source_registry.py 실행 결과 (37건 Seed × 7단계 MCP 수집 파이프라인)",
        "total_seeds": total_seeds,
        "status_verified": status_counts.get("verified", 0),
        "status_partial": status_counts.get("partial", 0),
        "status_failed": status_counts.get("failed", 0),
        "data_collected_count": sum(1 for s in seeds_detail if s["has_data"]),
        "conclusion": "NCP MCP 서버(49.50.133.160) Read Timeout으로 인해 37건 전건 failed. legal_source_registry.json에 법령 원문 데이터 0건 적재.",
        "seeds_by_group": {}
    },

    "section_2_existing_mcp_data": {
        "description": "기존 MCP chain_law_system으로 수집된 법체계 데이터 (law_hierarchy_2.json)",
        "file": "app/law_hierarchy_2.json",
        "file_size_bytes": os.path.getsize(lh_path) if os.path.exists(lh_path) else 0,
        "total_laws_with_content": len(lh_data),
        "laws": list(lh_data.values()),
        "conclusion": "{0}건의 법체계 데이터가 기존에 수집 완료됨 (조문+시행령+시행규칙 3단 비교 포함)".format(len(lh_data))
    },

    "section_3_local_law_text_files": {
        "description": "로컬에 텍스트로 보관 중인 법령 원문 파일",
        "total_files": len(txt_files),
        "total_size_kb": round(sum(t["size_bytes"] for t in txt_files) / 1024, 1),
        "files": sorted(txt_files, key=lambda x: x["size_bytes"], reverse=True)
    },

    "section_4_pdf_law_files": {
        "description": "법령/예규/고시/지침 PDF 원본 파일",
        "total_files": len(pdf_files),
        "total_size_mb": round(sum(p["size_bytes"] for p in pdf_files) / 1024 / 1024, 1),
        "files": sorted(pdf_files, key=lambda x: x["size_bytes"], reverse=True)
    },

    "section_5_hwpx_law_files": {
        "description": "법령/계획서 HWPX 원본 파일",
        "total_files": len(hwpx_files),
        "files": hwpx_files
    },

    "section_6_chromadb_backup": {
        "description": "ChromaDB 벡터DB 백업 (RAG 인덱스)",
        "backup_exists": chroma_exists,
        "backup_path": ".chroma_backup_20260423",
        "file_count": chroma_file_count
    },

    "section_7_candidate_auto_discovery": {
        "description": "자동 발견 후보 법령/행정규칙 (legal_source_candidate.json)",
        "total_candidates": len(candidates),
        "conclusion": "Seed 수집이 전건 실패하여 자동 발견 후보도 0건"
    },

    "overall_conclusion": {
        "phase7b_registry_status": "FAILED - 전건 수집 실패 (37/37 failed)",
        "failure_reason": "NCP MCP 서버(49.50.133.160:3000)의 Read Timeout (15초). TCP 연결은 성공하나 내부 법제처(www.law.go.kr) 연동 지연으로 응답 불가.",
        "existing_data_available": True,
        "existing_data_summary": {
            "law_hierarchy_json": "{0}건 법체계 데이터 (조문 포함, 52KB)".format(len(lh_data)),
            "law_text_files": "{0}건 텍스트 파일 ({1}KB)".format(len(txt_files), round(sum(t["size_bytes"] for t in txt_files) / 1024, 1)),
            "pdf_files": "{0}건 PDF 법령/규정 원본 ({1}MB)".format(len(pdf_files), round(sum(p["size_bytes"] for p in pdf_files) / 1024 / 1024, 1)),
            "chromadb_backup": "존재" if chroma_exists else "없음"
        },
        "next_action": [
            "1. NCP MCP 서버(49.50.133.160) 재기동 및 법제처 연결 점검",
            "2. app/data/_checkpoint.json 삭제",
            "3. python build_legal_source_registry.py --group all 재실행",
            "4. 수집 완료 후 ChromaDB 적재 (ingest_laws.py 연동)"
        ]
    }
}

# Group별 Seed 분류
groups = {}
for s in seeds_detail:
    g = s["group"]
    if g not in groups:
        groups[g] = []
    groups[g].append(s)
report["section_1_registry_pipeline_result"]["seeds_by_group"] = groups

with open(OUT_PATH, "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

print("=" * 60)
print("보고서 생성 완료:", OUT_PATH)
print("=" * 60)
print("Registry: %d건 중 verified=%d, partial=%d, failed=%d" % (
    total_seeds, status_counts.get("verified", 0),
    status_counts.get("partial", 0), status_counts.get("failed", 0)))
print("law_hierarchy_2.json: %d건 법체계 데이터" % len(lh_data))
print("텍스트 파일: %d건" % len(txt_files))
print("PDF 파일: %d건" % len(pdf_files))
print("HWPX 파일: %d건" % len(hwpx_files))
print("ChromaDB 백업: %s (%d files)" % (str(chroma_exists), chroma_file_count))
print("자동발견 후보: %d건" % len(candidates))
