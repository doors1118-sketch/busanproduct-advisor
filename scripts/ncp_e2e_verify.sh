#!/bin/bash
# NCP E2E Verification Runner (Mobile SSH 용)
# python/python3 자동 감지, 결과 JSON 없으면 PASS 금지, py_compile 실패 시 중단

# ─── Python 자동 감지 ───
if command -v python3 &>/dev/null; then
    PY=python3
elif command -v python &>/dev/null; then
    PY=python
else
    echo "[FATAL] python3/python not found"
    exit 1
fi

# ─── .env fallback ───
if [ ! -f .env ]; then
    if [ -f /root/advisor/.env ]; then
        cp /root/advisor/.env .
        echo "[INFO] .env copied from /root/advisor/.env"
    else
        echo "[WARN] .env not found"
    fi
fi

echo "====================================="
echo "=== 1. Commit ==="
COMMIT_HASH=$(git rev-parse --short HEAD)
echo "Commit: $COMMIT_HASH"
echo ""

echo "=== 2. Python ==="
$PY --version
echo ""

echo "=== 3. py_compile ==="
$PY -m py_compile app/gemini_engine.py app/policies/candidate_policy.py app/policies/candidate_formatter.py app/policies/innovation_search.py scripts/run_staging_verification.py run_tc7_gemini_runtime.py
PY_COMPILE_RC=$?
if [ $PY_COMPILE_RC -ne 0 ]; then
    echo "[FAIL] py_compile failed!"
    echo "=== SUMMARY ==="
    echo "- commit hash: $COMMIT_HASH"
    echo "- py_compile: FAIL"
    echo "- staging_verification_result: BLOCKED (py_compile failed)"
    echo "- TC7/G-RT: BLOCKED (py_compile failed)"
    echo "- Production deployment: HOLD"
    echo "====================================="
    exit 1
fi
echo "[OK] py_compile"
echo ""

echo "=== 4. staging ==="
$PY scripts/run_staging_verification.py
echo ""

echo "=== 5. TC7/Gemini runtime ==="
$PY run_tc7_gemini_runtime.py
echo ""

echo "=== 6. Copy artifacts ==="
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
DIR_NAME="artifacts/verification/ncp_e2e_$TIMESTAMP"
mkdir -p "$DIR_NAME"

cp staging_verification_result.json "$DIR_NAME/" 2>/dev/null
cp tc7_gemini_runtime_result.json "$DIR_NAME/" 2>/dev/null
cp CURRENT_STATUS.md "$DIR_NAME/" 2>/dev/null

echo "[OK] artifacts saved to $DIR_NAME"
echo ""

echo "=== 7. SUMMARY ==="
echo "- commit hash: $COMMIT_HASH"
echo "- py_compile: PASS"

# Staging - 결과 JSON 없으면 PASS 금지
if [ ! -f staging_verification_result.json ]; then
    echo "- staging_verification_result: NOT_FOUND (no JSON)"
elif grep -q '"pass": false' staging_verification_result.json 2>/dev/null; then
    echo "- staging_verification_result: FAIL"
else
    echo "- staging_verification_result: PASS"
fi

# TC7 - 결과 JSON 없으면 PASS 금지
if [ ! -f tc7_gemini_runtime_result.json ]; then
    echo "- TC7/G-RT: NOT_FOUND (no JSON)"
elif grep -q '"pass": false' tc7_gemini_runtime_result.json 2>/dev/null; then
    echo "- TC7/G-RT: FAIL"
else
    echo "- TC7/G-RT: PASS"
fi

# RAG status
LAWS_STATUS=$(grep '"laws_chromadb_status"' staging_verification_result.json 2>/dev/null | head -1 | awk -F '"' '{print $4}')
MANUALS_STATUS=$(grep '"manuals_rag"' staging_verification_result.json 2>/dev/null | head -1 | awk -F '"' '{print $4}')
INNOVATION_STATUS=$(grep '"innovation_status"' staging_verification_result.json 2>/dev/null | head -1 | awk -F '"' '{print $4}')
LATENCY_WARN=$(if grep -q '"latency_warning": true' staging_verification_result.json 2>/dev/null; then echo "YES"; elif [ -f staging_verification_result.json ]; then echo "NO"; else echo "UNKNOWN"; fi)

echo "- laws RAG: ${LAWS_STATUS:-UNKNOWN}"
echo "- manuals RAG: ${MANUALS_STATUS:-UNKNOWN}"
echo "- innovation: ${INNOVATION_STATUS:-UNKNOWN}"
echo "- latency warning: $LATENCY_WARN"
echo "- artifact path: $DIR_NAME"
echo "- Production deployment: HOLD"
echo "====================================="
