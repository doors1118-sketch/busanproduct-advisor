import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('49.50.133.160', username='root', password='U7$B%U5843m')

_, stdout, _ = c.exec_command("""
pid=$(pgrep -f "8502" | head -1)
if [ -n "$pid" ]; then
    cat /proc/$pid/fd/2 | tail -100
else
    cat /root/advisor/chatbot.log | tail -100
fi
""")
print(stdout.read().decode().strip())
c.close()
