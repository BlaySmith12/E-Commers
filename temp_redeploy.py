"""Upload seed_comprehensive.py to VPS and run it inside the app container."""
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
            for line in out.strip().split('\n')[-40:]:
                print(line)
        if err.strip():
            for line in err.strip().split('\n')[-20:]:
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
    # Upload seed_comprehensive.py via SFTP
    print('\n=== Uploading seed_comprehensive.py ===')
    sftp = ssh.open_sftp()
    sftp.put('seed_comprehensive.py', '/tmp/seed_comprehensive.py')
    sftp.close()
    print('Uploaded!')

    # Copy it into the running container
    run(ssh, 'docker cp /tmp/seed_comprehensive.py ecommerce-app-1:/app/seed_comprehensive.py')

    # Run the seed script inside the container
    print('\n=== Running seed_comprehensive.py in container ===')
    run(ssh, 'docker exec ecommerce-app-1 python /app/seed_comprehensive.py', timeout=600)

    # Verify data
    print('\n=== Verifying data ===')
    run(ssh, "docker exec ecommerce-app-1 python -c \"import asyncio; from sqlalchemy import text; from app.db import get_engine; e=get_engine(); asyncio.run(e.connect().then(lambda c: c.execute(text('SELECT count(*) FROM products')).scalar().then(lambda r: print(f'Products: {r}'))))\" 2>&1 || echo 'verify manually'")

except Exception as e:
    print(f'Error: {e}')

ssh.close()
print('\n=== DONE ===')
