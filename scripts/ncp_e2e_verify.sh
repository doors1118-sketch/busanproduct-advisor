#!/bin/bash
# NCP E2E Verification Runner (Mobile SSH 용)

echo "====================================="
echo "=== 1. 현재 커밋 확인 ==="
COMMIT_HASH=$(git rev-parse --short HEAD)
echo "Commit: $COMMIT_HASH"
echo ""

echo "=== 2. Python 버전 확인 ==="
python --version
echo ""

echo "=== 3. py_compile 실행 ==="
python -m py_compile app/gemini_engine.py app/policies/candidate_policy.py app/policies/candidate_formatter.py app/policies/innovation_search.py scripts/run_staging_verification.py run_tc7_gemini_runtime.py
if [ $? -ne 0 ]; then
    echo "❌ py_compile 실패!"
else
    echo "✅ py_compile 성공"
fi
echo ""

echo "=== 4. staging 검증 실행 ==="
python scripts/run_staging_verification.py
echo ""

echo "=== 5. TC7/Gemini runtime 검증 실행 ==="
python run_tc7_gemini_runtime.py
echo ""

echo "=== 6. 결과 파일 복사 ==="
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
DIR_NAME="artifacts/verification/ncp_e2e_$TIMESTAMP"
mkdir -p "$DIR_NAME"

cp staging_verification_result.json "$DIR_NAME/" 2>/dev/null
cp tc7_gemini_runtime_result.json "$DIR_NAME/" 2>/dev/null
cp CURRENT_STATUS.md "$DIR_NAME/" 2>/dev/null

echo "✅ 결과 파일이 $DIR_NAME 폴더에 저장되었습니다."
echo ""

echo "=== 7. 최종 요약 출력 ==="
echo "- commit hash: $COMMIT_HASH"

# Staging 결과 파싱 (간이 jq/grep)
if grep -q '"pass": false' staging_verification_result.json 2>/dev/null; then
    echo "- staging_verification_result: FAIL"
else
    if [ -f staging_verification_result.json ]; then
        echo "- staging_verification_result: PASS"
    else
        echo "- staging_verification_result: NOT_FOUND"
    fi
fi

# TC7 결과 파싱
if grep -q '"pass": false' tc7_gemini_runtime_result.json 2>/dev/null; then
    echo "- TC7/G-RT: FAIL"
else
    if [ -f tc7_gemini_runtime_result.json ]; then
         echo "- TC7/G-RT: PASS"
    else
         echo "- TC7/G-RT: NOT_FOUND"
    fi
fi

# RAG / Latency 상태 추출
LAWS_STATUS=$(grep '"laws_chromadb_status"' staging_verification_result.json 2>/dev/null | head -1 | awk -F '"' '{print $4}')
MANUALS_STATUS=$(grep '"manuals_rag"' staging_verification_result.json 2>/dev/null | head -1 | awk -F '"' '{print $4}')
LATENCY_WARN=$(if grep -q '"latency_warning": true' staging_verification_result.json 2>/dev/null; then echo "YES"; elif [ -f staging_verification_result.json ]; then echo "NO"; else echo "UNKNOWN"; fi)

echo "- laws RAG status: ${LAWS_STATUS:-UNKNOWN}"
echo "- manuals RAG status: ${MANUALS_STATUS:-UNKNOWN}"
echo "- latency warning 여부: $LATENCY_WARN"
echo "- Production deployment: HOLD"
echo "====================================="
