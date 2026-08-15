#!/usr/bin/env bash
set -euo pipefail
echo '=== sizes ==='
du -xhd1 /root /opt/backups /opt/busan/backups /opt/advisor/artifacts /opt/advisor/.cache 2>/dev/null | sort -h | tail -60
echo '=== root workspace files ==='
find /root/e2e_workspace /root/_advisor_archives -xdev -type f -printf '%s %TY-%Tm-%Td %TH:%TM %p\n' 2>/dev/null | sort -n | tail -30 || true
echo '=== opt backup files ==='
find /opt/backups -xdev -type f -printf '%s %TY-%Tm-%Td %TH:%TM %p\n' 2>/dev/null | sort -n | tail -30 || true
echo '=== busan backup files ==='
find /opt/busan/backups -xdev -type f -printf '%s %TY-%Tm-%Td %TH:%TM %p\n' 2>/dev/null | sort -n | tail -40 || true
echo '=== process references ==='
ps -eo pid,user,args | grep -F '/root/e2e_workspace' | grep -v grep || true
ps -eo pid,user,args | grep -F '/root/_advisor_archives' | grep -v grep || true
ps -eo pid,user,args | grep -F '/opt/backups' | grep -v grep || true
ps -eo pid,user,args | grep -F '/opt/busan/backups' | grep -v grep || true
