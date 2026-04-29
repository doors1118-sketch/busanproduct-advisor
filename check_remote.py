import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('49.50.133.160', username='root', password='U7$B%U5843m', timeout=10)

cmds = [
    # 1. manuals ingest process still running?
    ("Process check", "ps -p 2601082 -o pid,etime,cmd 2>/dev/null || echo 'Process not running'"),
    # 2. ingest result file
    ("Ingest result", "tail -10 ~/manuals_ingest_result.txt 2>/dev/null || echo 'File not found'"),
    # 3. ChromaDB collections
    ("ChromaDB collections", """cd ~/e2e_workspace && python3 -c "
import chromadb
c=chromadb.PersistentClient(path='app/.chroma')
for col in c.list_collections():
 name=col.name if hasattr(col,'name') else col
 print(name, c.get_collection(name).count())
" """),
    # 4. env check
    ("ENV CHROMA vars", "grep -i chroma ~/e2e_workspace/.env 2>/dev/null || echo 'No CHROMA in .env'"),
]

for label, cmd in cmds:
    print(f"\n=== {label} ===")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out.strip():
        print(out.strip())
    if err.strip():
        print(f"[STDERR] {err.strip()}")

ssh.close()
print("\nDone.")
