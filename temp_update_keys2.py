import paramiko, time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('162.35.186.39', username='root', password='DDracular123@', timeout=30)

def run(cmd, timeout=60):
    print(f'>>> {cmd}')
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    if out.strip(): print(out.strip()[-2000:])
    if err.strip(): print('ERR:', err.strip()[-500:])

# Append Paystack keys and BASE_URL to .env
run("cat >> /root/ecommerce/.env << 'ENVEOF'\n\n# Paystack\nPAYSTACK_SECRET_KEY=sk_test_a535a5327347b71afbed728ed477c9aecb8ac70d\nPAYSTACK_PUBLIC_KEY=pk_test_52acc8c2c7e127b7cd222e568d712ccfbaa24590\nPAYSTACK_WEBHOOK_SECRET=\n\n# Base URL\nBASE_URL=http://162.35.186.39\nENVEOF")

# Verify
run('cat /root/ecommerce/.env | grep -i paystack')
run('cat /root/ecommerce/.env | grep -i base_url')

# Restart app to pick up new env vars
run('cd /root/ecommerce && docker compose restart app')
time.sleep(15)

# Verify
run('curl -sf http://localhost:8000/health')
run('curl -sf -o /dev/null -w "%{http_code}" http://162.35.186.39/')
run('cd /root/ecommerce && docker compose ps')

ssh.close()
