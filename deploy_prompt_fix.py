import paramiko

host = '49.50.133.160'
user = 'root'
password = 'U7$B%U5843m'

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    print("Connecting to server...")
    client.connect(host, username=user, password=password)
    
    # Upload updated system_prompt.py
    sftp = client.open_sftp()
    local_path = r'app\system_prompt.py'
    remote_path = '/root/advisor/app/system_prompt.py'
    
    print(f"Uploading {local_path} -> {remote_path}")
    sftp.put(local_path, remote_path)
    print("Upload complete.")
    sftp.close()
    
    # Restart streamlit
    print("Restarting chatbot...")
    stdin, stdout, stderr = client.exec_command(
        'pkill -f "streamlit run" ; sleep 2 ; cd /root/advisor && nohup streamlit run app/main.py --server.port 8502 --server.address 0.0.0.0 > /dev/null 2>&1 &'
    )
    import time
    time.sleep(3)
    
    # Verify it's running
    stdin, stdout, stderr = client.exec_command('pgrep -f "streamlit run" | head -1')
    pid = stdout.read().decode().strip()
    if pid:
        print(f"Chatbot restarted successfully (PID: {pid})")
    else:
        print("Warning: Could not verify chatbot process")
        
finally:
    client.close()
