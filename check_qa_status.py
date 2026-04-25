import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('49.50.133.160', username='root', password='U7$B%U5843m')

cmds = {
    'qa_list.json 확인': 'python3 -c "import json; d=json.load(open(\'/root/advisor/qa_list.json\')); print(f\'PDF수: {len(d)}, 총 질문수: {sum(len(v) for v in d.values())}\')"',
    '전수조사 실행 상태': 'ps aux | grep exhaustive | grep -v grep || echo "(실행 중 아님)"',
    '테스트 리포트 상위 10줄': 'head -10 /root/advisor/test_report.md 2>/dev/null || echo "(리포트 없음)"',
    '리포트 진행률': 'wc -l /root/advisor/test_report.md 2>/dev/null || echo "0"',
}

for title, cmd in cmds.items():
    print(f"\n=== {title} ===")
    _, stdout, _ = c.exec_command(cmd)
    print(stdout.read().decode().strip())

c.close()
