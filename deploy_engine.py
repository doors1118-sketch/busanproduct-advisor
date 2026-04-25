import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('49.50.133.160', username='root', password='U7$B%U5843m')

print("Uploading gemini_engine.py...")
sftp = c.open_sftp()
sftp.put(r'app\gemini_engine.py', '/root/advisor/app/gemini_engine.py')
sftp.close()

print("Restarting chatbot...")
c.exec_command('pkill -f "8502"')
import time
time.sleep(3)
c.exec_command('cd /root/advisor && nohup streamlit run "app/pages/💬_법령챗봇.py" --server.port 8502 --server.address 0.0.0.0 --server.headless true > /root/advisor/chatbot.log 2>&1 &')
time.sleep(5)

_, stdout, _ = c.exec_command('ps aux | grep 8502 | grep -v grep')
result = stdout.read().decode().strip()
print("Process:", result if result else "Failed")
c.close()
