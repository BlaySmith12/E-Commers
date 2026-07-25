import paramiko, time

def get_ssh():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    for attempt in range(5):
        try:
            ssh.connect('162.35.186.39', username='root', password='DDracular123@', timeout=30, banner_timeout=30)
            print(f'Connected (attempt {attempt+1})')
            return ssh
        except Exception as e:
            print(f'  Connect failed: {e}')
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            time.sleep(10)
    return None

def run(ssh, cmd, timeout=300):
    print(f'\n>>> {cmd}')
    try:
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode('utf-8', errors='replace')
        err = stderr.read().decode('utf-8', errors='replace')
        if out.strip():
            for line in out.strip().split('\n')[-15:]:
                print(line)
        if err.strip():
            for line in err.strip().split('\n')[-5:]:
                print(line)
    except Exception as e:
        print(f'  Command failed: {e}')

ssh = get_ssh()
if not ssh:
    print('FAILED')
    exit(1)

try:
    run(ssh, 'cd /root/ecommerce && git pull origin main')
    run(ssh, 'cd /root/ecommerce && docker compose up -d --build', timeout=300)
except Exception as e:
    print(f'Error: {e}')

ssh.close()

time.sleep(25)
ssh = get_ssh()
if not ssh:
    print('FAILED reconnect')
    exit(1)

try:
    run(ssh, 'cd /root/ecommerce && docker compose ps')
    run(ssh, 'curl -sf http://localhost:8000/health || echo NOT_HEALTHY')
    run(ssh, 'curl -sf -o /dev/null -w "%{http_code}" http://162.35.186.39/ || echo FAIL')
    run(ssh, 'cd /root/ecommerce && docker compose logs --tail=15 app 2>&1')
except Exception as e:
    print(f'Error: {e}')

ssh.close()
print('\nDONE')
