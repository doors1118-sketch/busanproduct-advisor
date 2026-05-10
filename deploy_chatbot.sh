#!/bin/bash
# 법령챗봇 독립 서비스 배포 스크립트
# cron에서 5분마다 자동 실행

cd /opt/advisor

# 원격 저장소 상태 업데이트
git fetch origin main -q

# 로컬과 원격 해시 비교
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

if [ "$LOCAL" = "$REMOTE" ]; then
    # 업데이트가 없으면 아무 작업도 하지 않고 종료 (CPU/메모리 절약)
    exit 0
fi

# 변경사항이 있을 때만 pull 시도 (Merge 충돌 등으로 실패하면 즉시 중단)
git pull origin main -q || {
    echo "$(date): Git pull failed (merge conflict). Aborting deployment." >> /tmp/deploy_error.log
    exit 1
}

# 의존성 설치 (에러 로그 기록)
pip3 install -r requirements.txt --break-system-packages -q >> /tmp/pip_install.log 2>&1

# 서비스 파일 업데이트
cp law-chatbot.service /etc/systemd/system/
cp busan-advisor-pilot.service /etc/systemd/system/
chmod +x warmup.sh 2>/dev/null || true
chmod +x scripts/server_preflight.py 2>/dev/null || true
systemctl daemon-reload
systemctl enable law-chatbot 2>/dev/null
systemctl enable busan-advisor-pilot 2>/dev/null
systemctl restart busan-advisor-pilot
systemctl restart law-chatbot
