"""Deploy HTTP-only nginx + fix .env on VPS."""
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

def run(ssh, cmd, timeout=120):
    print(f'\n>>> {cmd}')
    try:
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode('utf-8', errors='replace')
        err = stderr.read().decode('utf-8', errors='replace')
        if out.strip():
            for line in out.strip().split('\n')[-25:]:
                print(line)
        if err.strip():
            for line in err.strip().split('\n')[-10:]:
                print(line)
    except Exception as e:
        print(f'  Command failed: {e}')
        return False
    return True

ssh = get_ssh()
if not ssh:
    print('FAILED to connect')
    exit(1)

try:
    run(ssh, 'cd /root/ecommerce && git pull origin main')

    # Fix .env on VPS to include IP-based CORS
    env_content = """# Production Environment
DATABASE_URL=postgresql+asyncpg://ecom_user:ecom_secure_2026@postgres:5432/ecom_db
SECRET_KEY=k8x2m9v7p4q1w6r3t5y8u0i2o4a7s1d5f9g3h6j0k2l8m4n7b5v3c2x9z1
JWT_SECRET_KEY=j7k3m2p9q5w8r1t4y6u0i3o7a2s5d8f1g4h7j9k6l3m0n5b8v2c4x1z6a9d3
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
CORS_ORIGINS=http://162.35.186.39,http://localhost,http://localhost:8000
PROJECT_NAME=ASAH'S PRIMENEST
API_PREFIX=/api
DEBUG=False
"""
    # Write .env to VPS
    sftp = ssh.open_sftp()
    with sftp.open('/root/ecommerce/.env', 'w') as f:
        f.write(env_content)
    sftp.close()
    print('\n.env updated on VPS')

    run(ssh, 'cd /root/ecommerce && docker compose down')
    run(ssh, 'cd /root/ecommerce && docker compose up -d --build', timeout=300)

except Exception as e:
    print(f'Error: {e}')

ssh.close()

# Reconnect to check
time.sleep(30)
ssh = get_ssh()
if not ssh:
    print('FAILED to reconnect')
    exit(1)

try:
    run(ssh, 'cd /root/ecommerce && docker compose ps')
    run(ssh, 'curl -sf http://localhost:8000/health || echo health_pending')
    run(ssh, 'curl -sf -o /dev/null -w "HTTP %{http_code}" http://localhost:80/ || echo http_pending')
    run(ssh, 'curl -sf -o /dev/null -w "HTTP %{http_code}" http://162.35.186.39/ || echo public_http_pending')
    run(ssh, 'cd /root/ecommerce && docker compose logs --tail=10 nginx 2>&1')
    run(ssh, 'cd /root/ecommerce && docker compose logs --tail=10 app 2>&1')
except Exception as e:
    print(f'Error: {e}')

ssh.close()
print('\n=== DONE ===')
