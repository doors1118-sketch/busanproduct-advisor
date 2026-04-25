import paramiko
import time

host = '49.50.133.160'
user = 'root'
password = 'U7$B%U5843m'

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    print("Connecting to server...")
    client.connect(host, username=user, password=password)
    
    print("Starting Flash test synchronously. This will be faster than Pro...")
    stdin, stdout, stderr = client.exec_command('cd /root/advisor && export PYTHONPATH=/root/advisor && /usr/bin/python3 run_stress_test.py')
    
    # Read output as it comes
    exit_status = stdout.channel.recv_exit_status() 
    print(f"Test completed with exit code {exit_status}")
    print(stdout.read().decode())
    print(stderr.read().decode())
    
    print("Downloading report...")
    sftp = client.open_sftp()
    sftp.get('/root/advisor/stress_report.md', 'stress_report_flash.md')
    sftp.close()
    print("Saved as stress_report_flash.md")

finally:
    client.close()
