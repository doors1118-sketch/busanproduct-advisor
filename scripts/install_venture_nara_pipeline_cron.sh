#!/usr/bin/env bash
set -euo pipefail

CRON_OWNER="${CRON_OWNER:-busan-monitor}"
BUSAN_ROOT="${BUSAN_ROOT:-/opt/busan}"
PYTHON_BIN="${PYTHON_BIN:-/opt/busan/venv/bin/python3}"
IMPORT_SCRIPT="${IMPORT_SCRIPT:-/opt/busan/import_venture_nara_api.py}"
LOG_FILE="${LOG_FILE:-/opt/busan/sync_log/chatbot_venture_nara.log}"
SCHEDULE="${VENTURE_NARA_CRON_SCHEDULE:-25 6 * * *}"
JOB_LINE="${SCHEDULE} cd ${BUSAN_ROOT} && . ${BUSAN_ROOT}/.env && CHATBOT_DB=${BUSAN_ROOT}/chatbot_company.db ${PYTHON_BIN} ${IMPORT_SCRIPT} --per-page 1000 --max-pages 20 >> ${LOG_FILE} 2>&1"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root because this script updates the ${CRON_OWNER} crontab." >&2
  exit 1
fi

if [[ ! -f "${IMPORT_SCRIPT}" ]]; then
  echo "Missing import script: ${IMPORT_SCRIPT}" >&2
  exit 1
fi

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "Missing python runtime: ${PYTHON_BIN}" >&2
  exit 1
fi

mkdir -p "$(dirname "${LOG_FILE}")"
chown "${CRON_OWNER}:${CRON_OWNER}" "$(dirname "${LOG_FILE}")"

backup="/tmp/${CRON_OWNER}.crontab.before_venture_nara.$(date +%Y%m%d_%H%M%S)"
crontab -u "${CRON_OWNER}" -l > "${backup}" 2>/dev/null || true

if grep -Fq "import_venture_nara_api.py" "${backup}"; then
  echo "VentureNara cron is already registered. Backup: ${backup}"
  exit 0
fi

tmp="$(mktemp)"
cat "${backup}" > "${tmp}"
{
  echo ""
  echo "# VentureNara product/designated-company full refresh for vendor recommendation DB"
  echo "${JOB_LINE}"
} >> "${tmp}"

crontab -u "${CRON_OWNER}" "${tmp}"
rm -f "${tmp}"

echo "Installed VentureNara cron for ${CRON_OWNER}:"
echo "${JOB_LINE}"
echo "Previous crontab backup: ${backup}"
