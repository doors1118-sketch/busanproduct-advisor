#!/bin/bash
# 법령챗봇 독립 서비스 배포 스크립트
# cron에서 5분마다 자동 실행

cd /root/advisor
git pull origin main -q

# 의존성 설치 (에러 로그 기록)
pip3 install -r requirements.txt --break-system-packages -q >> /tmp/pip_install.log 2>&1

# 서비스 파일 업데이트
cp law-chatbot.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable law-chatbot 2>/dev/null
systemctl restart law-chatbot
