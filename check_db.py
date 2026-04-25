import paramiko

def check_progress(host, user, pwd):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(hostname=host, username=user, password=pwd, timeout=10)
        
        # Check running python processes
        print("--- Running Python Processes ---")
        stdin, stdout, stderr = client.exec_command("ps aux | grep python")
        print(stdout.read().decode('utf-8'))
        
        # Check size of .chroma directory
        print("--- ChromaDB Directory Size ---")
        stdin, stdout, stderr = client.exec_command("du -sh /root/advisor/app/.chroma 2>/dev/null || echo 'Not found'")
        print(stdout.read().decode('utf-8'))
        
        # Check files inside .chroma
        print("--- ChromaDB Files ---")
        stdin, stdout, stderr = client.exec_command("ls -la /root/advisor/app/.chroma 2>/dev/null")
        print(stdout.read().decode('utf-8'))
        
    finally:
        client.close()

if __name__ == "__main__":
    check_progress("49.50.133.160", "root", "U7$B%U5843m")
