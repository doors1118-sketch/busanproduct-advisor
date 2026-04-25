import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('49.50.133.160', username='root', password='U7$B%U5843m')

cmds = {
    'CPU cores': 'nproc',
    'CPU model': 'lscpu | grep "Model name"',
    'Memory': 'free -h',
    'Load': 'uptime',
    'Disk': 'df -h /',
    'Top processes': 'ps aux --sort=-%cpu | head -6',
    'Streamlit': 'ps aux | grep streamlit | grep -v grep',
}

for title, cmd in cmds.items():
    print(f"\n=== {title} ===")
    _, stdout, _ = client.exec_command(cmd)
    print(stdout.read().decode().strip())

client.close()
