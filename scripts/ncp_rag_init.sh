#!/bin/bash
# NCP RAG DB Initialization & Verification Runner (Mobile SSH 용)
# python/python3 자동 감지, 각 단계 실패 시 전체 중단 금지

# ─── Python 자동 감지 ───
if command -v python3 &>/dev/null; then
    PY=python3
elif command -v python &>/dev/null; then
    PY=python
else
    echo "[FATAL] python3/python not found"
    exit 1
fi

echo "====================================="
echo "=== 1. laws RAG DB ==="
$PY app/ingest_laws.py || echo "[WARN] ingest_laws.py failed or skipped"
echo ""

echo "=== 2. manuals RAG DB ==="
$PY app/ingest_manuals.py || echo "[WARN] ingest_manuals.py failed or skipped (PDF not found?)"
echo ""

echo "=== 3. innovation RAG DB ==="
$PY app/ingest_innovation.py || echo "[WARN] ingest_innovation.py failed or skipped (Excel not found?)"
echo ""

echo "=== 4. E2E verify ==="
chmod +x scripts/ncp_e2e_verify.sh
./scripts/ncp_e2e_verify.sh
echo "====================================="
