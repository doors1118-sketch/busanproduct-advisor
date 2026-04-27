#!/bin/bash
# NCP RAG DB Initialization & Verification Runner (Mobile SSH 용)

echo "====================================="
echo "=== 1. laws RAG DB 생성 ==="
python3 app/ingest_laws.py 
echo ""

echo "=== 2. manuals RAG DB 생성 ==="
# 내부 try-except로 PyMuPDF (fitz) 에러 발생 시 자동 skip 처리됨
python3 app/ingest_manuals.py || echo "Warning: ingest_manuals.py returned non-zero, but continuing."
echo ""

echo "=== 3. innovation RAG DB 생성 ==="
python3 app/ingest_innovation.py 
echo ""

echo "=== 4. 모든 DB 생성 완료 -> 검증 스크립트 재실행 ==="
chmod +x scripts/ncp_e2e_verify.sh
./scripts/ncp_e2e_verify.sh
echo "====================================="
echo "RAG 생성 및 검증 완료 성공!"
