import paramiko
import re

host = '49.50.133.160'
user = 'root'
password = 'U7$B%U5843m'

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    client.connect(host, username=user, password=password)
    
    # Read .env
    stdin, stdout, stderr = client.exec_command('cat /root/advisor/.env')
    env_content = stdout.read().decode()
    print("--- OLD ENV ---")
    print(env_content)
    
    # Replace model
    new_env = re.sub(r'GEMINI_MODEL=.*', 'GEMINI_MODEL=gemini-2.5-flash', env_content)
    
    # Write back .env
    # We use a trick: write to a temp file, then move it
    sftp = client.open_sftp()
    with sftp.file('/root/advisor/.env.tmp', 'w') as f:
        f.write(new_env)
    sftp.close()
    
    client.exec_command('mv /root/advisor/.env.tmp /root/advisor/.env')
    
    print("--- NEW ENV ---")
    stdin, stdout, stderr = client.exec_command('cat /root/advisor/.env')
    print(stdout.read().decode())
    
    # Check running streamlit processes
    stdin, stdout, stderr = client.exec_command('ps -ef | grep streamlit | grep -v grep')
    ps_output = stdout.read().decode()
    print("--- RUNNING STREAMLIT PROCESSES ---")
    print(ps_output)
    
finally:
    client.close()
