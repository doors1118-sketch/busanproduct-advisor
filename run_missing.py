import paramiko

def run_missing(host, user, pwd):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=host, username=user, password=pwd, timeout=10)
    
    cmds = [
        "cd /root/advisor/app && nohup python3 ingest_innovation.py > ingest_innov.log 2>&1 &",
        "cd /root/advisor/app && nohup python3 ingest_tech_products.py > ingest_tech.log 2>&1 &"
    ]
    
    for cmd in cmds:
        print(f"Running: {cmd}")
        client.exec_command(cmd)
        
    client.close()

if __name__ == "__main__":
    run_missing("49.50.133.160", "root", "U7$B%U5843m")
