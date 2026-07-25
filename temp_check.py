"""Check deployment status with retries."""
import paramiko, time

def try_connect():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    for attempt in range(5):
        try:
            print(f'Connection attempt {attempt+1}...')
            ssh.connect('162.35.186.39', username='root', password='DDracular123@', timeout=30, banner_timeout=30)
            print('Connected!')
            return ssh
        except Exception as e:
            print(f'  Failed: {e}')
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            time.sleep(15)
    return None

def run(ssh, cmd, timeout=30):
    print(f'\n>>> {cmd}')
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    if out.strip(): print(out.strip()[-2000:])
    if err.strip(): print(err.strip()[-1000:])

ssh = try_connect()
if not ssh:
    print('Could not connect after 5 attempts')
    exit(1)

run(ssh, 'uptime')
run(ssh, 'cd /root/ecommerce && docker compose ps')
run(ssh, 'curl -sf http://localhost:8000/health || echo health_pending')
run(ssh, 'cd /root/ecommerce && docker compose logs --tail=20 app 2>&1')
run(ssh, 'cd /root/ecommerce && docker compose logs --tail=10 nginx 2>&1')

ssh.close()
print('\n=== DONE ===')
