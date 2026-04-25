import paramiko, time
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('49.50.133.160', username='root', password='U7$B%U5843m')

# Kill existing 8502 process
c.exec_command('pkill -f "8502"')
time.sleep(3)

# Start with the correct file path (법령챗봇.py directly)
print("재시작 중...")
c.exec_command('cd /root/advisor && nohup streamlit run "app/pages/💬_법령챗봇.py" --server.port 8502 --server.address 0.0.0.0 --server.headless true > /root/advisor/chatbot.log 2>&1 &')
time.sleep(5)

# Verify
_, stdout, _ = c.exec_command('ps aux | grep 8502 | grep -v grep')
result = stdout.read().decode().strip()
if result:
    pid = result.split()[1]
    print(f"챗봇 재시작 완료 (PID: {pid})")
else:
    print("시작 실패!")
    _, stdout, _ = c.exec_command('cat /root/advisor/chatbot.log')
    print(stdout.read().decode().strip())

# Check .env is loaded
_, stdout, _ = c.exec_command('cat /root/advisor/.env | grep MODEL')
print(f"모델: {stdout.read().decode().strip()}")

c.close()
