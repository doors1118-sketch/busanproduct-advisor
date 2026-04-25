import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('49.50.133.160', username='root', password='U7$B%U5843m')

# Check chatbot log for recent activity
print("=== 챗봇 로그 (최근 활동) ===")
_, stdout, _ = c.exec_command('tail -50 /root/advisor/chatbot.log 2>/dev/null')
print(stdout.read().decode().strip())

# Check process stderr for timing info
print("\n=== 프로세스 로그 ===")
_, stdout, _ = c.exec_command('pid=$(pgrep -f "8502" | head -1); cat /proc/$pid/fd/2 2>/dev/null | tail -30')
print(stdout.read().decode().strip())

# Also check the QA v2 test progress for timing reference
print("\n=== QA V2 테스트 진행 상황 (응답시간 참고) ===")
_, stdout, _ = c.exec_command('tail -20 /root/advisor/qa_v2.log 2>/dev/null')
print(stdout.read().decode().strip())

# Check if qa_results_v2.json has data with timing
_, stdout, _ = c.exec_command("""python3 << 'EOF'
import json, os
f = '/root/advisor/qa_results_v2.json'
if os.path.exists(f):
    data = json.load(open(f))
    print(f"완료: {len(data)}/249건")
    if data:
        times = [r['elapsed'] for r in data]
        print(f"평균 응답시간: {sum(times)/len(times):.1f}초")
        print(f"최소: {min(times):.1f}초 / 최대: {max(times):.1f}초")
        print(f"\n최근 5건:")
        for r in data[-5:]:
            print(f"  [{r['idx']}] {r['elapsed']}s - {r['status']} - {r['question'][:40]}...")
else:
    print("아직 결과 없음")
EOF
""")
print(f"\n=== QA 테스트 응답시간 통계 ===")
print(stdout.read().decode().strip())

c.close()
