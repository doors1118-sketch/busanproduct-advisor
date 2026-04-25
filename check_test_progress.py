import paramiko
import json
import time

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('49.50.133.160', username='root', password='U7$B%U5843m')

# 1. Check if there's any intermediate output from the running test
print("=== 1. 기존 테스트 진행 상황 확인 ===")
_, stdout, _ = c.exec_command('ls -la /root/advisor/test_report*.md /root/advisor/exhaustive_*.json 2>/dev/null || echo "(중간 결과 파일 없음)"')
print(stdout.read().decode().strip())

# Check stdout/log of running process
_, stdout, _ = c.exec_command('ls -la /root/advisor/nohup.out /root/advisor/test_*.log 2>/dev/null; tail -30 /root/advisor/nohup.out 2>/dev/null || echo "(로그 없음)"')
print("\n=== 실행 로그 (최근 30줄) ===")
print(stdout.read().decode().strip())

# Check if there are any result files being written
_, stdout, _ = c.exec_command('find /root/advisor -name "*.json" -newer /root/advisor/run_exhaustive_test.py -type f 2>/dev/null')
print("\n=== 테스트 후 생성된 JSON 파일 ===")
result = stdout.read().decode().strip()
print(result if result else "(없음)")

# Check process stdout by looking at /proc
_, stdout, _ = c.exec_command('cat /proc/2066212/fd/1 2>/dev/null | tail -20 || echo "(접근 불가)"')
print("\n=== 프로세스 stdout ===")
print(stdout.read().decode().strip())

c.close()
