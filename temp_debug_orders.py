import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('162.35.186.39', username='root', password='DDracular123@', timeout=30)

def run(cmd, timeout=30):
    print(f'\n>>> {cmd}')
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    if out.strip(): print(out.strip()[:5000])
    if err.strip(): print('ERR:', err.strip()[:2000])

# Get recent app logs with errors/tracebacks
run('cd /root/ecommerce && docker compose logs --tail=80 app 2>&1 | grep -A 20 -i "error\\|traceback\\|exception\\|500\\|Internal"')

ssh.close()
