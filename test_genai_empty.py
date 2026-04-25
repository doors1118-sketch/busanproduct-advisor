import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('49.50.133.160', username='root', password='U7$B%U5843m')

_, stdout, _ = c.exec_command("""cd /root/advisor && python3 << 'PYEOF'
import sys, os
sys.path.insert(0, 'app')
from dotenv import load_dotenv
load_dotenv('.env', override=True)
from gemini_engine import get_gemini_client, SYSTEM_PROMPT, _tools
import google.generativeai as genai

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel(
    model_name=os.getenv("GEMINI_MODEL"),
    system_instruction=SYSTEM_PROMPT,
    tools=_tools
)
chat = model.start_chat()
msg = "[소속기관: 지방자치단체(부산시·구·군·교육청)] 2억 물품 수의계약 가능해?"
response = chat.send_message(msg)
print(f"Turn 1 parts: {response.parts}")

if response.function_call:
    # mock a function call response
    from google.generativeai.types import content_types
    # Just to see how the model behaves when we ask it directly
    # actually it's easier to just use the engine's chat
PYEOF
""")
print(stdout.read().decode().strip())
c.close()
