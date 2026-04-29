import paramiko
import os

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    ssh.connect('49.50.133.160', username='root', password='back9900@@', timeout=10)
    
    # Check if frontend exists
    stdin, stdout, stderr = ssh.exec_command('ls -l /root/e2e_workspace/frontend')
    print("ls frontend:", stdout.read().decode())
    
    # Also we need the latest api_server.py! Because basic auth was added to api_server.py locally!
    # Wait, if basic auth was added to api_server.py locally, how did the remote server use it?
    # Actually, the remote server didn't use it! The python test `get("/ui/")` hit 404 because the frontend folder wasn't there or not mounted.
    # The Python test for `/version` returned 200 without auth! Wait, I used auth in the python script.
    # Ah! The remote server ran `uvicorn app.api_server:app`, but its `api_server.py` doesn't have the Basic Auth middleware, so it just allows everything.
    
    # So I need to sync the whole local directory to the server, or at least the modified files:
    # app/api_server.py, frontend/index.html, frontend/app.js, frontend/styles.css
    
    sftp = ssh.open_sftp()
    
    def put_file(local_path, remote_path):
        print(f"Uploading {local_path} -> {remote_path}")
        # ensure dir
        ssh.exec_command(f"mkdir -p $(dirname {remote_path})")
        sftp.put(local_path, remote_path)

    base = 'c:\\Users\\doors\\OneDrive\\바탕 화면\\사무실 메뉴얼 제작_추출\\메뉴얼 제작'
    
    put_file(os.path.join(base, 'app', 'api_server.py'), '/root/e2e_workspace/app/api_server.py')
    put_file(os.path.join(base, 'app', 'gemini_engine.py'), '/root/e2e_workspace/app/gemini_engine.py')
    
    # Copy frontend dir
    frontend_dir = os.path.join(base, 'frontend')
    for f in os.listdir(frontend_dir):
        if os.path.isfile(os.path.join(frontend_dir, f)):
            put_file(os.path.join(frontend_dir, f), f'/root/e2e_workspace/frontend/{f}')

    sftp.close()
    
    # Restart service
    ssh.exec_command("systemctl restart busan-advisor-pilot.service")
    
    ssh.close()
except Exception as e:
    print('Failed:', e)
