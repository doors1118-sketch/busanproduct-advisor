import paramiko
import os
import glob

host = '49.50.133.160'
pwd = 'U7$B%U5843m'
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host, username='root', password=pwd)

sftp = ssh.open_sftp()

print("1. Installing rank_bm25 on server...")
stdin, stdout, stderr = ssh.exec_command("ps -ef | grep streamlit | grep -v grep | awk '{print $8}' | head -n 1")
python_path = stdout.read().decode().strip()
if not python_path or "streamlit" in python_path:
    python_path = "/usr/bin/python3"
ssh.exec_command(f"{python_path} -m pip install rank_bm25 --break-system-packages")

print("2. Uploading Manual PDFs...")
ssh.exec_command('mkdir -p "/root/advisor/계약메뉴얼"')
local_manual_dir = "계약메뉴얼"
for filename in os.listdir(local_manual_dir):
    if filename.endswith(".pdf"):
        local_path = os.path.join(local_manual_dir, filename)
        remote_path = f"/root/advisor/계약메뉴얼/{filename}"
        print(f"  Uploading {filename}...")
        try:
            sftp.put(local_path, remote_path)
        except Exception as e:
            print(f"  Failed: {e}")

print("3. Uploading Extra PDFs...")
extra_pdfs = [
    "물품 다수공급자계약 업무처리규정(조달청훈령)(제2373호)(20260227).pdf",
    "용역 다수공급자계약 업무처리규정(조달청고시)(제2026-1호)(20260201).pdf",
    "용역 카탈로그 계약 업무처리규정(조달청고시)(제2026-2호)(20260201).pdf",
    "물품구매(제조)계약 특수조건(조달청지침)(제7356호)(20260101).pdf",
    "조달청 경쟁적 대화에 의한 계약체결 세부기준(조달청지침)(제403호)(20200401).pdf",
    "혁신제품 제3자단가계약 추가특수조건(조달청공고)(제2026-90호)(20260227).pdf",
    "다수공급자계약 추가특수조건(조달청공고)(제2016-22호)(20160301).pdf",
    "디지털서비스 카탈로그계약 특수조건(조달청공고)(제2025-531호)(20260101).pdf",
    "복수물품 공급계약업무 처리규정(조달청훈령)(제2329호)(20260123).pdf",
    "상용소프트웨어 다수공급자계약 업무처리규정(조달청훈령)(제2290호)(20250901).pdf",
    "물품구매계약 품질관리 특수조건(조달청지침)(제1635호)(20260316).pdf",
    "상용소프트웨어 다수공급자계약 특수조건(조달청공고)(제2025-532호)(20260101).pdf",
    "지방자치단체 입찰 및 계약집행기준(행정안전부예규)(제332호)(20250708).pdf",
    "(붙임1) 중소벤처기업부 시범구매제도 안내.pdf"
]
for filename in extra_pdfs:
    if os.path.exists(filename):
        remote_path = f"/root/advisor/{filename}"
        print(f"  Uploading {filename}...")
        try:
            sftp.put(filename, remote_path)
        except Exception as e:
            print(f"  Failed: {e}")

sftp.close()

print("4. Removing corrupted Chroma DB and starting clean ingestion in background...")
cmd = f'''
cd /root/advisor/app
rm -rf .chroma
export PYTHONPATH=/root/advisor
nohup {python_path} ingest_laws.py > ingest_laws.log 2>&1 &
nohup {python_path} ingest_manuals.py > ingest_manuals.log 2>&1 &
'''
ssh.exec_command(cmd)
ssh.close()
print("All fix commands sent. Ingestion running in background.")
