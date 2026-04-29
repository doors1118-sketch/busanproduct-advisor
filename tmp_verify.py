import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    ssh.connect('49.50.133.160', username='root', password='back9900@@', timeout=10)
    
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
    with urllib.request.urlopen(req, timeout=60) as r:
        body = r.read().decode()
        print(path, r.status)
        return body

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

    with urllib.request.urlopen(req, timeout=180) as r:
        data = json.loads(r.read().decode())
        print("/chat", r.status)
        print("candidate_table_source:", data.get("candidate_table_source"))
        print("legal_conclusion_allowed:", data.get("legal_conclusion_allowed"))
        print("contract_possible_auto_promoted:", data.get("contract_possible_auto_promoted"))
        print("forbidden_patterns_remaining_after_rewrite:", data.get("forbidden_patterns_remaining_after_rewrite"))
        print("production_deployment:", data.get("production_deployment"))
        print("answer_chars:", len(data.get("answer", "")))

get("/ui/")
get("/ui/app.js")
get("/version")
get("/rag/status")
post_chat()
"""
    stdin, stdout, stderr = ssh.exec_command(f'python3 -c \'"""\n{script}\n"""\'')
    print(stdout.read().decode())
    err = stderr.read().decode()
    if err:
        print('STDERR:', err)
        
    ssh.close()
except Exception as e:
    print('Failed:', e)
