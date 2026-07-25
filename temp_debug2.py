import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('162.35.186.39', username='root', password='DDracular123@', timeout=30)

def run(cmd, timeout=30):
    print(f'\n>>> {cmd}')
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    if out.strip(): print(out.strip()[:3000])
    if err.strip(): print('ERR:', err.strip()[:500])

# Check app logs for recent errors
run('cd /root/ecommerce && docker compose logs --tail=30 app 2>&1 | grep -i "error\\|traceback\\|exception\\|404\\|500\\|delete"')

# Test delete on product ID 1 (get a token first)
run('curl -s http://localhost:8000/api/auth/login -X POST -H "Content-Type: application/json" -d "{\\"email\\":\\"admin@primenest.com\\",\\"password\\":\\"password123\\"}"')

ssh.close()
