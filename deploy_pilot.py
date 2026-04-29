import paramiko
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    ssh.connect('49.50.133.160', username='root', password='back9900@@', timeout=10)
    
    # 1. Create pilot_auth.env
    env_content = """PILOT_AUTH_ENABLED=true
PILOT_AUTH_USER=admin
PILOT_AUTH_PASSWORD=pilot123!
PROMPT_MODE=dynamic_v1_4_4
"""
    ssh.exec_command(f"cat << 'EOF' > /root/advisor/pilot_auth.env\n{env_content}EOF")
    ssh.exec_command("chmod 600 /root/advisor/pilot_auth.env")
    
    # 2. Get working directory
    stdin, stdout, stderr = ssh.exec_command("cd /root/advisor/app && pwd")
    # Actually, the user asked to use the '검증된 clean clone 디렉터리', which is usually /root/advisor or /opt/busan. Wait! Let's check where the app is.
    stdin, stdout, stderr = ssh.exec_command("find /root -name api_server.py 2>/dev/null")
    print("Found api_server.py at:", stdout.read().decode().strip())
    
    service_content = """[Unit]
Description=Busan Procurement AI Chatbot Internal Pilot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/advisor
EnvironmentFile=/root/advisor/.env
EnvironmentFile=/root/advisor/pilot_auth.env
ExecStart=/usr/bin/python3 -m uvicorn app.api_server:app --host 0.0.0.0 --port 8001
Restart=always
RestartSec=5
StandardOutput=append:/var/log/busan_advisor_pilot_out.log
StandardError=append:/var/log/busan_advisor_pilot_err.log

[Install]
WantedBy=multi-user.target
"""
    ssh.exec_command(f"cat << 'EOF' > /etc/systemd/system/busan-advisor-pilot.service\n{service_content}EOF")
    
    # 3. Start service
    ssh.exec_command("systemctl daemon-reload")
    ssh.exec_command("systemctl start busan-advisor-pilot.service")
    
    time.sleep(3)
    
    # 4. Check status
    print('--- systemd status ---')
    stdin, stdout, stderr = ssh.exec_command('systemctl status busan-advisor-pilot.service --no-pager; systemctl is-active busan-advisor-pilot.service; ss -ltnp | grep 8001')
    print(stdout.read().decode())
    
    print('--- curl without auth ---')
    stdin, stdout, stderr = ssh.exec_command('curl -s -I http://127.0.0.1:8001/ui/')
    print(stdout.read().decode())
    
    print('--- python smoke test ---')
    script = """
import base64, json, urllib.request

env = {}
with open("/root/advisor/pilot_auth.env", "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k] = v

user = env.get("PILOT_AUTH_USER")
pw = env.get("PILOT_AUTH_PASSWORD")

if not user or not pw:
    raise SystemExit("pilot auth env missing")

token = base64.b64encode(f"{user}:{pw}".encode()).decode()
headers = {"Authorization": f"Basic {token}"}

def get(path):
    req = urllib.request.Request(f"http://127.0.0.1:8001{path}", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            body = r.read().decode()
            print(path, r.status)
            return body
    except Exception as e:
        print(path, "ERROR:", str(e))

def post_chat():
    payload = json.dumps({
        "message": "CCTV 부산 업체 추천해줘",
        "agency_type": "local_government",
        "history": []
    }).encode("utf-8")

    req = urllib.request.Request(
        "http://127.0.0.1:8001/chat",
        data=payload,
        headers={**headers, "Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            data = json.loads(r.read().decode())
            print("/chat", r.status)
            print("candidate_table_source:", data.get("candidate_table_source"))
            print("legal_conclusion_allowed:", data.get("legal_conclusion_allowed"))
            print("contract_possible_auto_promoted:", data.get("contract_possible_auto_promoted"))
            print("forbidden_patterns_remaining_after_rewrite:", data.get("forbidden_patterns_remaining_after_rewrite"))
            print("production_deployment:", data.get("production_deployment"))
            print("answer_chars:", len(data.get("answer", "")))
    except Exception as e:
        print("/chat", "ERROR:", str(e))

get("/ui/")
get("/ui/app.js")
get("/version")
get("/rag/status")
post_chat()
"""
    # Write smoke script to file on server and run it
    ssh.exec_command(f"cat << 'EOF' > /tmp/smoke.py\n{script}\nEOF")
    stdin, stdout, stderr = ssh.exec_command("python3 /tmp/smoke.py")
    print(stdout.read().decode())
    err = stderr.read().decode()
    if err:
        print('STDERR:', err)
        
    ssh.close()
except Exception as e:
    print('Failed:', e)
