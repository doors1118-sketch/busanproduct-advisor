import paramiko
import sys

def check(host, user, pwd):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(hostname=host, username=user, password=pwd, timeout=10)
        stdin, stdout, stderr = client.exec_command("ps aux | grep python")
        print(stdout.read().decode('utf-8'))
    finally:
        client.close()

if __name__ == "__main__":
    check("49.50.133.160", "root", "U7$B%U5843m")
