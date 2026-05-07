import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('49.50.133.160', username='root', password='back9900@@', timeout=10)
stdin, stdout, stderr = ssh.exec_command("curl -s -X POST http://127.0.0.1:8001/chat -H 'Content-Type: application/json' -d '{\"message\":\"2억 물품 수의계약 가능해?\", \"agency_type\": \"지방자치단체\", \"history\": []}'")
print(stdout.read().decode()[:500])
print("STDERR:", stderr.read().decode())
ssh.close()
