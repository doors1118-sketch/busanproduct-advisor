import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('49.50.133.160', username='root', password='U7$B%U5843m')

_, stdout, _ = c.exec_command("cat /root/advisor/chatbot.log | tail -50")
print(stdout.read().decode().strip())

c.close()
