import paramiko

host = '49.50.133.160'
user = 'root'
password = 'U7$B%U5843m'

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    client.connect(host, username=user, password=password)
    
    # Kill the chatbot process on port 8502
    print("Killing streamlit chatbot...")
    client.exec_command("ps -ef | grep '8502' | grep -v grep | awk '{print $2}' | xargs -r kill -9")
    
    # Wait a sec
    import time
    time.sleep(2)
    
    # Restart the chatbot
    print("Starting streamlit chatbot...")
    # Using cd /root/advisor && nohup ... &
    cmd = "cd /root/advisor && nohup /usr/bin/python3 /usr/local/bin/streamlit run app/pages/💬_법령챗봇.py --server.port 8502 --server.address 0.0.0.0 --server.headless true > chatbot.log 2>&1 &"
    client.exec_command(cmd)
    
    print("Restarted.")
    
finally:
    client.close()
