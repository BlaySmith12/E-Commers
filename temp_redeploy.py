"""Deploy with nginx fix and certbot cert generation."""
import paramiko, time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('162.35.186.39', username='root', password='DDracular123@', timeout=30, banner_timeout=30)
print('Connected!')

def run(cmd, timeout=120):
    print(f'\n>>> {cmd}')
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    if out.strip():
        for line in out.strip().split('\n')[-25:]:
            print(line)
    if err.strip():
        for line in err.strip().split('\n')[-10:]:
            print(line)

run('cd /root/ecommerce && git pull origin main')
run('cd /root/ecommerce && docker compose down')
run('cd /root/ecommerce && docker compose build --no-cache nginx', timeout=300)
run('cd /root/ecommerce && docker compose up -d', timeout=120)

time.sleep(20)
run('cd /root/ecommerce && docker compose ps')
run('curl -sf http://localhost:8000/health || echo health_pending')
run('curl -sf http://localhost:80 || echo http_pending')
run('cd /root/ecommerce && docker compose logs --tail=15 nginx 2>&1')

ssh.close()
print('\n=== DONE ===')
