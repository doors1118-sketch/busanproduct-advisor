#!/bin/bash
# Non-invasive API warmup.
# Do not call /chat here: warmup must not create user-visible QA log records.

set +e

cd /opt/advisor || exit 0

DELAY="${ADVISOR_WARMUP_DELAY_SECONDS:-5}"
sleep "$DELAY"

if [ -f /opt/advisor/pilot_auth.env ]; then
  # shellcheck disable=SC1091
  source /opt/advisor/pilot_auth.env
fi

AUTH_HEADER=()
if [ -n "$PILOT_AUTH_USER" ] && [ -n "$PILOT_AUTH_PASSWORD" ]; then
  TOKEN=$(printf '%s' "$PILOT_AUTH_USER:$PILOT_AUTH_PASSWORD" | base64)
  AUTH_HEADER=(-H "Authorization: Basic $TOKEN")
fi

ADMIN_HEADER=("${AUTH_HEADER[@]}")
if [ -n "$ADMIN_HEALTH_TOKEN" ]; then
  ADMIN_HEADER=(-H "X-Admin-Token: $ADMIN_HEALTH_TOKEN")
fi

curl -fsS --max-time 5 "${AUTH_HEADER[@]}" http://127.0.0.1:8001/health > /dev/null || true
curl -fsS --max-time 8 "${AUTH_HEADER[@]}" http://127.0.0.1:8001/rag/status > /dev/null || true
curl -fsS --max-time 8 "${ADMIN_HEADER[@]}" 'http://127.0.0.1:8001/admin/health/routing?recent_limit=20' > /dev/null || true

echo "warmup health done"
exit 0
