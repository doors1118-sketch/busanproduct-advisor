import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('49.50.133.160', username='root', password='back9900@@', timeout=10)
stdin, stdout, stderr = ssh.exec_command("tail -n 150 /var/log/busan_advisor_pilot_out.log")
print(stdout.read().decode())
ssh.close()
