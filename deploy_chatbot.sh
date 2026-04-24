#!/bin/bash
# 법령챗봇 독립 서비스 배포 스크립트
# cron 또는 수동 실행: bash deploy_chatbot.sh

set -e
echo "=== 법령챗봇 독립 서비스 배포 ==="

# 1. 최신 코드 가져오기
cd /root/advisor
git pull origin main -q
echo "✅ 코드 업데이트 완료"

# 2. 의존성 설치 (없는 패키지만 설치)
pip3 install -r requirements.txt --break-system-packages -q 2>/dev/null || true
echo "✅ 의존성 확인 완료"

# 3. systemd 서비스 등록
cp law-chatbot.service /etc/systemd/system/
systemctl daemon-reload
echo "✅ 서비스 등록 완료"

# 4. 서비스 시작
systemctl enable law-chatbot 2>/dev/null
systemctl restart law-chatbot
echo "✅ 서비스 시작 완료"

# 5. 상태 확인
sleep 2
systemctl status law-chatbot --no-pager || true

echo ""
echo "=== 배포 완료 ==="
echo "접속 URL: http://49.50.133.160:8502"
echo "기존 대시보드(8501)는 영향 없음"
