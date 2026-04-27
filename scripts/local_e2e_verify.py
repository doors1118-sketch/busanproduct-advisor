"""
Local E2E Verification Pipeline
- py_compile → RAG status → RAG smoke test → staging verification → TC7/G-RT
- 결과를 artifacts/verification/local_e2e_<timestamp>/ 에 저장
- Production deployment: HOLD
"""
import os
import sys
sys.stdout.reconfigure(encoding='utf-8')
import json
import time
import shutil
import subprocess
import py_compile

# ─── 경로 설정 ───
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(PROJECT_ROOT, "scripts")
ARTIFACTS_BASE = os.path.join(PROJECT_ROOT, "artifacts", "verification")

sys.path.insert(0, os.path.join(PROJECT_ROOT, "app"))

os.environ["STAGING_MODE"] = "1"
os.environ["PROMPT_MODE"] = "dynamic_v1_4_4"

PYTHON = sys.executable

# ─── py_compile 대상 파일 ───
COMPILE_TARGETS = [
    "app/gemini_engine.py",
    "app/policies/candidate_policy.py",
    "app/policies/candidate_formatter.py",
    "app/policies/innovation_search.py",
    "scripts/run_staging_verification.py",
    "run_tc7_gemini_runtime.py",
]


def step_py_compile() -> dict:
    """1단계: py_compile 검증."""
    print("\n=== 1. py_compile ===")
    results = {}
    all_pass = True
    for rel_path in COMPILE_TARGETS:
        abs_path = os.path.join(PROJECT_ROOT, rel_path)
        try:
            py_compile.compile(abs_path, doraise=True)
            results[rel_path] = "PASS"
            print(f"  [OK] {rel_path}")
        except py_compile.PyCompileError as e:
            results[rel_path] = f"FAIL: {e}"
            print(f"  [FAIL] {rel_path}: {e}")
            all_pass = False
    return {"py_compile": "PASS" if all_pass else "FAIL", "details": results}


def step_rag_status() -> dict:
    """2단계: RAG DB 존재 여부 확인."""
    print("\n=== 2. RAG DB Status ===")
    from local_rag_smoke_test import run_smoke_test, print_summary
    results = run_smoke_test()
    print_summary(results)
    return {
        "laws_chromadb_status": results["laws"]["status"],
        "laws_indexed_doc_count": results["laws"]["doc_count"],
        "laws_retrieved_doc_count": results["laws"]["retrieved_count"],
        "laws_role": "advisory_context_only",
        "manuals_chromadb_status": results["manuals"]["status"],
        "manuals_indexed_doc_count": results["manuals"]["doc_count"],
        "manuals_retrieved_doc_count": results["manuals"]["retrieved_count"],
        "innovation_status": results["innovation"]["status"],
        "innovation_product_count": results["innovation"]["doc_count"],
        "rag_smoke_raw": results,
    }


def step_run_staging() -> dict:
    """3단계: scripts/run_staging_verification.py 실행."""
    print("\n=== 3. Staging Verification ===")
    script = os.path.join(SCRIPTS_DIR, "run_staging_verification.py")
    st = time.time()
    proc = subprocess.run(
        [PYTHON, script],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
        encoding='utf-8',
        errors='replace',
        env={**os.environ, "STAGING_MODE": "1", "PYTHONIOENCODING": "utf-8"},
    )
    elapsed = int((time.time() - st) * 1000)

    result_file = os.path.join(PROJECT_ROOT, "staging_verification_result.json")
    staging_data = {}
    if os.path.exists(result_file):
        with open(result_file, "r", encoding="utf-8") as f:
            staging_data = json.load(f)

    # pass/fail 판정
    if isinstance(staging_data, list):
        all_pass = all(r.get("pass", False) for r in staging_data)
    elif isinstance(staging_data, dict):
        all_pass = staging_data.get("pass", False)
    else:
        all_pass = False

    print(f"  staging_verification_result: {'PASS' if all_pass else 'FAIL'}")
    print(f"  elapsed: {elapsed}ms")
    if proc.returncode != 0:
        print(f"  stderr (last 500 chars): {proc.stderr[-500:]}")

    return {
        "staging_verification_result": "PASS" if all_pass else "FAIL",
        "staging_elapsed_ms": elapsed,
        "staging_exit_code": proc.returncode,
        "staging_data": staging_data,
    }


def step_run_tc7() -> dict:
    """4단계: run_tc7_gemini_runtime.py 실행."""
    print("\n=== 4. TC7/Gemini Runtime ===")
    script = os.path.join(PROJECT_ROOT, "run_tc7_gemini_runtime.py")
    st = time.time()
    proc = subprocess.run(
        [PYTHON, script],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=600,
        encoding='utf-8',
        errors='replace',
        env={**os.environ, "STAGING_MODE": "1", "PYTHONIOENCODING": "utf-8"},
    )
    elapsed = int((time.time() - st) * 1000)

    result_file = os.path.join(PROJECT_ROOT, "tc7_gemini_runtime_result.json")
    tc7_data = []
    if os.path.exists(result_file):
        with open(result_file, "r", encoding="utf-8") as f:
            tc7_data = json.load(f)

    all_pass = all(r.get("pass", False) for r in tc7_data) if tc7_data else False

    print(f"  TC7/G-RT: {'PASS' if all_pass else 'FAIL'}")
    print(f"  elapsed: {elapsed}ms")
    if proc.returncode != 0:
        print(f"  stderr (last 500 chars): {proc.stderr[-500:]}")

    return {
        "tc7_grt_result": "PASS" if all_pass else "FAIL",
        "tc7_elapsed_ms": elapsed,
        "tc7_exit_code": proc.returncode,
        "tc7_data": tc7_data,
    }


def extract_key_fields(tc7_data: list) -> dict:
    """TC7 결과에서 필수 출력 필드 추출."""
    fields = {
        "candidate_table_source": [],
        "contract_possible_auto_promoted": [],
        "legal_conclusion_allowed": [],
        "forbidden_patterns_remaining_after_rewrite": [],
        "pass": [],
        "failure_reason": [],
    }
    for r in tc7_data:
        for key in fields:
            fields[key].append(r.get(key, "N/A"))
    return fields


def save_artifacts(all_results: dict) -> str:
    """결과를 artifacts/verification/local_e2e_<timestamp>/ 에 저장."""
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    out_dir = os.path.join(ARTIFACTS_BASE, f"local_e2e_{timestamp}")
    os.makedirs(out_dir, exist_ok=True)

    # 전체 결과 저장
    with open(os.path.join(out_dir, "local_e2e_result.json"), "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2, default=str)

    # 개별 결과 파일 복사
    for fname in ["staging_verification_result.json", "tc7_gemini_runtime_result.json", "CURRENT_STATUS.md"]:
        src = os.path.join(PROJECT_ROOT, fname)
        if os.path.exists(src):
            shutil.copy2(src, out_dir)

    # RAG smoke result 복사
    rag_src = os.path.join(SCRIPTS_DIR, "local_rag_smoke_result.json")
    if os.path.exists(rag_src):
        shutil.copy2(rag_src, out_dir)

    return out_dir


def print_final_summary(all_results: dict, artifact_path: str):
    """최종 요약 출력."""
    rag = all_results.get("rag_status", {})
    staging = all_results.get("staging", {})
    tc7 = all_results.get("tc7", {})
    tc7_fields = all_results.get("tc7_key_fields", {})

    print("\n" + "=" * 60)
    print("  LOCAL E2E VERIFICATION SUMMARY")
    print("=" * 60)
    print(f"  py_compile:                          {all_results.get('compile', {}).get('py_compile', 'N/A')}")
    print(f"  laws_chromadb_status:                 {rag.get('laws_chromadb_status', 'N/A')}")
    print(f"  laws_indexed_doc_count:               {rag.get('laws_indexed_doc_count', 0)}")
    print(f"  laws_retrieved_doc_count:             {rag.get('laws_retrieved_doc_count', 0)}")
    print(f"  laws_role:                            advisory_context_only")
    print(f"  manuals_chromadb_status:              {rag.get('manuals_chromadb_status', 'N/A')}")
    print(f"  manuals_indexed_doc_count:            {rag.get('manuals_indexed_doc_count', 0)}")
    print(f"  manuals_retrieved_doc_count:          {rag.get('manuals_retrieved_doc_count', 0)}")
    print(f"  innovation_status:                    {rag.get('innovation_status', 'N/A')}")
    print(f"  innovation_product_count:             {rag.get('innovation_product_count', 0)}")
    print(f"  staging_verification_result:          {staging.get('staging_verification_result', 'N/A')}")
    print(f"  TC7/G-RT:                             {tc7.get('tc7_grt_result', 'N/A')}")
    print(f"  candidate_table_source:               {tc7_fields.get('candidate_table_source', 'N/A')}")
    print(f"  contract_possible_auto_promoted:      {tc7_fields.get('contract_possible_auto_promoted', 'N/A')}")
    print(f"  legal_conclusion_allowed:             {tc7_fields.get('legal_conclusion_allowed', 'N/A')}")
    print(f"  forbidden_patterns_remaining:         {tc7_fields.get('forbidden_patterns_remaining_after_rewrite', 'N/A')}")
    print(f"  pass:                                 {tc7_fields.get('pass', 'N/A')}")
    print(f"  failure_reason:                       {tc7_fields.get('failure_reason', 'N/A')}")
    print(f"  artifact_path:                        {artifact_path}")
    print(f"  Production deployment:                HOLD")
    print("=" * 60)


def main():
    print("=" * 60)
    print("  LOCAL E2E VERIFICATION PIPELINE")
    print(f"  Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Python: {sys.version}")
    print(f"  Project: {PROJECT_ROOT}")
    print("=" * 60)

    all_results = {}

    # 1. py_compile
    all_results["compile"] = step_py_compile()

    # 2. RAG status + smoke test
    all_results["rag_status"] = step_rag_status()

    # 3. staging verification
    all_results["staging"] = step_run_staging()

    # 4. TC7/G-RT
    all_results["tc7"] = step_run_tc7()

    # TC7 key fields 추출
    tc7_data = all_results["tc7"].get("tc7_data", [])
    all_results["tc7_key_fields"] = extract_key_fields(tc7_data)

    # 5. artifacts 저장
    artifact_path = save_artifacts(all_results)

    # 6. 최종 요약
    print_final_summary(all_results, artifact_path)


if __name__ == "__main__":
    main()
