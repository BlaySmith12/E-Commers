"""Full reset - wipe volumes and redeploy."""
import paramiko, time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('162.35.186.39', username='root', password='DDracular123@', timeout=15)
print('Connected!')

def run(cmd, timeout=120):
    print(f'\n>>> {cmd}')
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    if out: print(out)
    if err: print(err.rstrip())

# Full reset including volumes
print('\n=== Full reset ===')
run('cd /root/ecommerce && docker compose down -v')

# Pull and rebuild
print('\n=== Pull + rebuild ===')
run('cd /root/ecommerce && git pull origin main')
run('cd /root/ecommerce && docker compose up -d --build', timeout=600)

print('\n=== Wait and check ===')
time.sleep(40)
run('cd /root/ecommerce && docker compose ps')
run('curl -sf http://localhost:8000/health || echo health_pending')
run('cd /root/ecommerce && docker compose logs --tail=30 app 2>&1')

ssh.close()
print('\n=== DONE ===')
