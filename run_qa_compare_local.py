import paramiko
import time

host = '49.50.133.160'
user = 'root'
password = 'U7$B%U5843m'

remote_script = """
import sys
import time
sys.path.insert(0, '/root/advisor/app')
import gemini_engine

questions = [
    "지방계약법상 물품 수의계약 한도가 어떻게 되나요? (여성기업인 경우 포함해서 설명해주세요)",
    "부산교통공사에서 2억 5천만원짜리 일반용역을 발주하려고 하는데, 지역제한 경쟁입찰이 가능한가요? 법적 근거와 함께 상세히 설명해주세요."
]

models = ["gemini-2.5-flash", "gemini-2.5-pro"]

with open("/root/advisor/qa_comparison_result.md", "w", encoding="utf-8") as f:
    f.write("# ⚖️ Gemini 2.5 Pro vs 2.5 Flash 답변 수준(질적) 비교 리포트\\n\\n")

    for i, q in enumerate(questions):
        f.write(f"## ❓ 질문 {i+1}: {q}\\n\\n")
        
        for model in models:
            f.write(f"### 🤖 모델: `{model}`\\n")
            gemini_engine.MODEL_ID = model
            print(f"Running {model} for question {i+1}...")
            
            start_time = time.time()
            try:
                ans, _ = gemini_engine.chat(q)
            except Exception as e:
                ans = f"Error: {e}"
            elapsed = time.time() - start_time
            
            f.write(f"- **소요 시간:** {elapsed:.1f}초\\n\\n")
            f.write(f"**[답변 내용]**\\n{ans}\\n\\n")
            f.write("---\\n")
"""

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    print("Connecting to server...")
    client.connect(host, username=user, password=password)
    
    sftp = client.open_sftp()
    with sftp.file('/root/advisor/run_qa_compare.py', 'w') as f:
        f.write(remote_script)
    sftp.close()
    
    print("Running qualitative comparison. This will take ~2 minutes...")
    stdin, stdout, stderr = client.exec_command('cd /root/advisor && export PYTHONPATH=/root/advisor && /usr/bin/python3 run_qa_compare.py')
    
    # Wait for completion
    exit_status = stdout.channel.recv_exit_status()
    print(f"Completed with exit code {exit_status}")
    print(stdout.read().decode())
    
    sftp = client.open_sftp()
    sftp.get('/root/advisor/qa_comparison_result.md', 'qa_comparison_result.md')
    sftp.close()
    print("Downloaded qa_comparison_result.md")

finally:
    client.close()
