import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('49.50.133.160', username='root', password='U7$B%U5843m')

# Check what streamlit processes are running
print("=== 실행 중인 Streamlit 프로세스 ===")
_, stdout, _ = c.exec_command('ps aux | grep streamlit | grep -v grep')
print(stdout.read().decode().strip())

# Check the chatbot main file
print("\n=== 챗봇 메인 파일 확인 ===")
_, stdout, _ = c.exec_command('ls -la /root/advisor/app/main.py /root/advisor/app/pages/*챗봇* 2>/dev/null')
print(stdout.read().decode().strip())

# Check stderr of chatbot process
print("\n=== 챗봇 프로세스 에러 로그 ===")
_, stdout, _ = c.exec_command('pid=$(pgrep -f "법령챗봇\\|8502" | head -1); cat /proc/$pid/fd/2 2>/dev/null | tail -30 || echo "(없음)"')
print(stdout.read().decode().strip())

# Restart chatbot properly with main.py
print("\n=== 챗봇 재시작 (main.py 기준) ===")
_, stdout, _ = c.exec_command('pkill -f "8502"; sleep 2; cd /root/advisor && nohup streamlit run app/main.py --server.port 8502 --server.address 0.0.0.0 --server.headless true > /root/advisor/chatbot.log 2>&1 &')
import time
time.sleep(4)

_, stdout, _ = c.exec_command('ps aux | grep 8502 | grep -v grep')
result = stdout.read().decode().strip()
print(result if result else "(시작 실패)")

# Check startup log
_, stdout, _ = c.exec_command('cat /root/advisor/chatbot.log 2>/dev/null | tail -10')
print(f"\n시작 로그:\n{stdout.read().decode().strip()}")

c.close()
