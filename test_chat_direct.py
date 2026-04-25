import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('49.50.133.160', username='root', password='U7$B%U5843m')

# Direct test with proper quoting
_, stdout, _ = c.exec_command("""cd /root/advisor && python3 << 'PYEOF'
import sys, os
sys.path.insert(0, 'app')
from dotenv import load_dotenv
load_dotenv('.env', override=True)
print(f"Model: {os.getenv('GEMINI_MODEL')}")
from gemini_engine import chat
try:
    answer, refs = chat("2억 물품 수의계약 가능해?")
    print(f"Answer length: {len(answer)}")
    print(f"Answer: {answer[:500]}")
except Exception as e:
    import traceback
    traceback.print_exc()
PYEOF
""")
output = stdout.read().decode().strip()
err = c.exec_command("""cd /root/advisor && python3 << 'PYEOF'
import sys
sys.path.insert(0, 'app')
PYEOF
""")[2].read().decode().strip()
print(output)
if err:
    print(f"\nSTDERR: {err}")

c.close()
