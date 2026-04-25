import paramiko

host = '49.50.133.160'
user = 'root'
password = 'U7$B%U5843m'

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    print("Connecting to server...")
    client.connect(host, username=user, password=password)
    
    # Upload updated .env
    sftp = client.open_sftp()
    
    local_env = r'.env'
    remote_env = '/root/advisor/.env'
    print(f"Uploading {local_env} -> {remote_env}")
    sftp.put(local_env, remote_env)
    print(".env upload complete.")
    sftp.close()
    
    # Verify .env
    stdin, stdout, stderr = client.exec_command('cat /root/advisor/.env')
    env_content = stdout.read().decode().strip()
    print(f"Server .env:\n{env_content}")
    
    # Restart streamlit
    print("\nRestarting chatbot...")
    stdin, stdout, stderr = client.exec_command(
        'pkill -f "streamlit run" ; sleep 2 ; cd /root/advisor && nohup streamlit run app/main.py --server.port 8502 --server.address 0.0.0.0 > /dev/null 2>&1 &'
    )
    import time
    time.sleep(3)
    
    # Verify
    stdin, stdout, stderr = client.exec_command('pgrep -f "streamlit run" | head -1')
    pid = stdout.read().decode().strip()
    if pid:
        print(f"Chatbot restarted successfully (PID: {pid})")
    else:
        print("Warning: Could not verify chatbot process")
        
finally:
    client.close()
