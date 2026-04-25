import paramiko
import sys
import time

def run_remote_command(host, user, pwd, cmds):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        print(f"Connecting to {host}...")
        client.connect(hostname=host, username=user, password=pwd, timeout=10)
        print("Connected successfully.")
        
        for cmd in cmds:
            print(f"\n--- Executing: {cmd} ---")
            stdin, stdout, stderr = client.exec_command(cmd)
            while True:
                line = stdout.readline()
                if not line:
                    break
                print(line, end="")
            err = stderr.read().decode('utf-8')
            if err:
                print("STDERR:", err)
            status = stdout.channel.recv_exit_status()
            print(f"Exit status: {status}")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    host = "49.50.133.160"
    user = "root"
    pwd = "U7$B%U5843m"
    commands = [
        "which python3",
        "systemctl stop law-chatbot",
        "rm -rf /root/advisor/app/.chroma",
        "sed -i '/^RestartSec=10/a TimeoutStopSec=120' /etc/systemd/system/law-chatbot.service",
        "cat /etc/systemd/system/law-chatbot.service",
        "systemctl daemon-reload",
        "cd /root/advisor/app && python3 ingest_laws.py",
        "cd /root/advisor/app && python3 ingest_pps_qa.py",
        "cd /root/advisor/app && python3 ingest_manuals.py",
        "systemctl start law-chatbot",
        "systemctl status law-chatbot --no-pager"
    ]
    run_remote_command(host, user, pwd, commands)
