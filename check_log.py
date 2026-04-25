import paramiko, time
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('49.50.133.160', username='root', password='U7$B%U5843m')
time.sleep(3)
_, stdout, _ = c.exec_command('tail -15 /root/advisor/qa_v2.log')
print(stdout.read().decode().strip())
c.close()
