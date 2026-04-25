import paramiko
import sys
import os

host = '49.50.133.160'
pwd = 'U7$B%U5843m'

try:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, username='root', password=pwd)

    stdin, stdout, stderr = ssh.exec_command("echo '--- CPU Info ---'; lscpu | grep -E 'Model name|CPU\(s\):|Thread'; echo '--- Memory Info ---'; free -h; echo '--- Disk Info ---'; df -h /")
    specs = stdout.read().decode()
    ssh.close()
except Exception as e:
    specs = f"Failed to get specs: {e}"

prompt_path = r"C:\Users\doors\OneDrive\바탕 화면\사무실 메뉴얼 제작_추출\메뉴얼 제작\app\system_prompt.py"
with open(prompt_path, 'r', encoding='utf-8') as f:
    prompt_code = f.read()

# Extract just the SYSTEM_PROMPT string (it starts at SYSTEM_PROMPT = """ and ends at """)
try:
    start_idx = prompt_code.find('SYSTEM_PROMPT = """') + len('SYSTEM_PROMPT = """')
    end_idx = prompt_code.find('"""', start_idx)
    prompt_text = prompt_code[start_idx:end_idx]
except:
    prompt_text = prompt_code

md_content = f"""# 🖥️ 서버 시스템 사양 및 챗봇 프롬프트 명세서

## 1. 운영 서버(NCP) 사양 요약

```text
{specs.strip()}
```

## 2. 지역상생 조달 어드바이저 시스템 프롬프트 (System Prompt)

이 프롬프트는 제미나이(Gemini) AI 엔진의 성격, 제약 조건, 도구 사용 규칙을 정의하는 핵심 명령어 집합입니다.

```text
{prompt_text.strip()}
```
"""

with open("system_specs_prompt.md", "w", encoding="utf-8") as f:
    f.write(md_content)
    
print("Successfully created system_specs_prompt.md")
