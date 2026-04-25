import paramiko, json, os
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('49.50.133.160', username='root', password='U7$B%U5843m')

_, stdout, _ = c.exec_command('python3 -c "import json, os; f=\'/root/advisor/qa_results_v2.json\'; print(len(json.load(open(f)))) if os.path.exists(f) else print(0)"')
count = stdout.read().decode().strip()
print(f'Progress: {count}/249')

_, stdout, _ = c.exec_command('ps aux | grep run_qa_v2 | grep -v grep')
if stdout.read().decode().strip():
    print('Status: RUNNING')
else:
    print('Status: STOPPED')
c.close()
