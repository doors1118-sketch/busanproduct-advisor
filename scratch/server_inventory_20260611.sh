#!/usr/bin/env bash
set -euo pipefail
out=/tmp/server_inventory_20260611.txt
{
  echo "# Server Inventory"
  echo "checked_at=$(date '+%Y-%m-%d %H:%M:%S %Z')"
  echo "hostname=$(hostname)"
  echo
  echo "## Disk"
  df -h /
  echo
  echo "## /opt size depth1"
  du -xhd1 /opt 2>/dev/null | sort -h
  echo
  echo "## /opt/busan depth1"
  du -xhd1 /opt/busan 2>/dev/null | sort -h
  echo
  echo "## /opt/advisor depth1"
  du -xhd1 /opt/advisor 2>/dev/null | sort -h
  echo
  echo "## Services"
  for s in busan-api.service busan-dashboard.service busan-advisor-pilot.service law-chatbot.service korean-law-mcp.service busan-company-cache-sync.service; do
    if systemctl list-unit-files "$s" >/dev/null 2>&1; then
      echo "### $s"
      systemctl is-enabled "$s" 2>/dev/null || true
      systemctl is-active "$s" 2>/dev/null || true
      systemctl cat "$s" 2>/dev/null | sed -n '1,120p'
    fi
  done
  echo
  echo "## Timers"
  systemctl list-timers --all --no-pager | sed -n '1,120p'
  echo
  echo "## Crontab busan-monitor"
  crontab -u busan-monitor -l 2>/dev/null || true
  echo
  echo "## Crontab busan-chatbot"
  crontab -u busan-chatbot -l 2>/dev/null || true
  echo
  echo "## Crontab root"
  crontab -l 2>/dev/null || true
  echo
  echo "## Key DB/cache files"
  for p in \
    /opt/busan/procurement_contracts.db \
    /opt/busan/busan_companies_master.db \
    /opt/busan/busan_agencies_master.db \
    /opt/busan/servc_site.db \
    /opt/busan/chatbot_company.db \
    /opt/busan/api_cache.json \
    /opt/busan/monthly_cache.json \
    /opt/advisor/cache/company/cache_current/chatbot_company.db \
    /opt/advisor/cache/company/cache_previous/chatbot_company.db; do
    if [ -e "$p" ]; then
      stat -c '%n|%s|%y' "$p"
    else
      echo "$p|missing|"
    fi
  done
  echo
  echo "## Company cache symlinks"
  readlink -f /opt/advisor/cache/company/cache_current 2>/dev/null || true
  readlink -f /opt/advisor/cache/company/cache_previous 2>/dev/null || true
  find /opt/advisor/cache/company/archive -maxdepth 1 -mindepth 1 -type d -printf '%TY-%Tm-%Td %TH:%TM %p\n' 2>/dev/null | sort || true
  echo
  echo "## DB counts"
  python3 - <<'PY'
import sqlite3, json, os
paths = ['/opt/busan/chatbot_company.db', '/opt/advisor/cache/company/cache_current/chatbot_company.db']
objects = ['chatbot_company_candidate_view','product_policy_summary','direct_production_certificate','company_license','company_license_construction_capacity','facility_material_item_dictionary','facility_material_price_current']
for path in paths:
    print('DB', path)
    if not os.path.exists(path):
        print(' missing')
        continue
    con=sqlite3.connect(f'file:{path}?mode=ro', uri=True)
    try:
        for obj in objects:
            exists=con.execute("SELECT 1 FROM sqlite_master WHERE name=? AND type IN ('table','view')", (obj,)).fetchone()
            if not exists:
                print(f' {obj}=missing')
                continue
            cnt=con.execute(f'SELECT COUNT(*) FROM {obj}').fetchone()[0]
            print(f' {obj}={cnt}')
    finally:
        con.close()
PY
  echo
  echo "## Git status"
  for d in /opt/busan /opt/advisor; do
    echo "### $d"
    if [ -d "$d/.git" ]; then
      git -C "$d" rev-parse --abbrev-ref HEAD || true
      git -C "$d" rev-parse --short HEAD || true
      git -C "$d" status --short | sed -n '1,80p' || true
    else
      echo "not git repo"
    fi
  done
} > "$out"
cat "$out"
