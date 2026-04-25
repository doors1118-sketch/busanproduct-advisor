import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('49.50.133.160', username='root', password='U7$B%U5843m')

# Check streamlit chatbot logs
print("=== Streamlit 챗봇 로그 (최근 50줄) ===")
_, stdout, _ = c.exec_command('journalctl -u streamlit-chatbot --no-pager -n 50 2>/dev/null || tail -50 /root/advisor/chatbot.log 2>/dev/null || echo "(systemd/로그 없음)"')
print(stdout.read().decode().strip())

# Check nohup output
print("\n=== nohup 출력 ===")
_, stdout, _ = c.exec_command('ls -la /root/advisor/nohup.out 2>/dev/null && tail -30 /root/advisor/nohup.out 2>/dev/null || echo "(없음)"')
print(stdout.read().decode().strip())

# Check stderr of the streamlit process
print("\n=== Streamlit 프로세스 stderr ===")
_, stdout, _ = c.exec_command('cat /proc/$(pgrep -f "법령챗봇" | head -1)/fd/2 2>/dev/null | tail -40 || echo "(접근 불가)"')
print(stdout.read().decode().strip())

# Check if there's a general streamlit log
print("\n=== /tmp or advisor 로그 파일 ===")
_, stdout, _ = c.exec_command('find /root/advisor -name "*.log" -newer /root/advisor/.env -type f 2>/dev/null | head -5')
print(stdout.read().decode().strip())

# Direct test: try calling the chat function
print("\n=== 직접 테스트: chat() 함수 호출 ===")
_, stdout, stderr = c.exec_command('''cd /root/advisor && python3 -c "
import sys, os
sys.path.insert(0, 'app')
from dotenv import load_dotenv
load_dotenv('.env', override=True)
print(f'Model: {os.getenv(\"GEMINI_MODEL\")}')
from gemini_engine import chat
try:
    answer, refs = chat('2억 물품 수의계약 가능해?')
    print(f'Answer length: {len(answer)}')
    print(f'Answer preview: {answer[:300]}')
except Exception as e:
    print(f'ERROR: {e}')
" 2>&1 | tail -30''')
print(stdout.read().decode().strip())

c.close()
