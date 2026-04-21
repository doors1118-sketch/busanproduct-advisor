#!/bin/bash
# Korean Law MCP 배포 스크립트
# NCP 서버에서 실행: bash deploy_mcp.sh
set -e

echo "=== Korean Law MCP 배포 ==="

# 기존 프로세스 종료
pkill -f korean-law-mcp 2>/dev/null || true
sleep 2

# Node.js 확인/설치
if ! command -v node &> /dev/null; then
    echo "[설치] Node.js 설치 중..."
    apt update && apt install -y nodejs npm
fi
echo "[OK] Node.js $(node -v)"

# MCP 설치
echo "[설치] korean-law-mcp 설치 중..."
npm install -g korean-law-mcp

# systemd 서비스 등록
cp korean-law-mcp.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable korean-law-mcp
systemctl restart korean-law-mcp

echo ""
echo "=== 배포 완료! ==="
systemctl status korean-law-mcp --no-pager
echo ""
echo "엔드포인트: http://49.50.133.160:3000/mcp?oc=busanproduct"
