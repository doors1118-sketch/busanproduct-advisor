import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('49.50.133.160', username='root', password='U7$B%U5843m')

# Check qa_results_v2.json for timing data
_, stdout, _ = c.exec_command("""python3 -c "
import json, os
f = '/root/advisor/qa_results_v2.json'
if os.path.exists(f):
    data = json.load(open(f))
    print(f'완료: {len(data)}/249건')
    if data:
        times = [r['elapsed'] for r in data]
        print(f'평균: {sum(times)/len(times):.1f}초')
        print(f'최소: {min(times):.1f}초 / 최대: {max(times):.1f}초')
        for r in data[-5:]:
            print(f'  [{r[\"idx\"]}] {r[\"elapsed\"]}s {r[\"status\"]} - {r[\"question\"][:50]}')
else:
    print('결과 파일 없음')
"
""")
print(stdout.read().decode().strip())

# Check process status
_, stdout, _ = c.exec_command('ps aux | grep qa_v2 | grep -v grep | head -1')
print(f"\n프로세스: {stdout.read().decode().strip()}")

c.close()
