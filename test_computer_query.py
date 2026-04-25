import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('49.50.133.160', username='root', password='U7$B%U5843m')

_, stdout, _ = c.exec_command("""cd /root/advisor && python3 << 'PYEOF'
import sys, os
sys.path.insert(0, 'app')
from dotenv import load_dotenv
load_dotenv('.env', override=True)
from gemini_engine import chat

try:
    chat_input = "[소속기관: 지방자치단체(부산시·구·군·교육청)] 컴퓨터 8천만원정도 구매하려고 한다. 지역업체랑 계약할 수 있는 방법이 있을까?"
    answer, refs = chat(chat_input)
    print(f"Answer length: {len(answer)}")
    print(f"Answer:\n{answer}")
except Exception as e:
    import traceback
    traceback.print_exc()
PYEOF
""")
print(stdout.read().decode().strip())
c.close()
