"""Full reset - force no-cache rebuild."""
import paramiko, time, sys

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('162.35.186.39', username='root', password='DDracular123@', timeout=15)
print('Connected!')

def run(cmd, timeout=600):
    print(f'\n>>> {cmd}')
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.channel.recv(65536).decode('utf-8', errors='replace') if not stdout.channel.closed else ''
    err = stderr.channel.recv(65536).decode('utf-8', errors='replace') if not stderr.channel.closed else ''
    if out.strip(): print(out.strip()[-500:] if len(out.strip()) > 500 else out.strip())
    if err.strip(): print(err.strip()[-500:] if len(err.strip()) > 500 else err.strip())

def run_long(cmd, timeout=600):
    """Run command and read all output without encoding issues."""
    print(f'\n>>> {cmd}')
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    # Just wait for completion
    exit_status = stdout.channel.recv_exit_status()
    # Read tail of output
    buf = b''
    while not stdout.channel.exit_status_ready:
        time.sleep(0.5)
    # Get remaining
    while stdout.channel.recv_ready():
        buf += stdout.channel.recv(65536)
    out = buf.decode('utf-8', errors='replace')
    if out.strip():
        lines = out.strip().split('\n')
        for line in lines[-20:]:
            print(line)
    print(f'Exit status: {exit_status}')

print('\n=== Pull ===')
run('cd /root/ecommerce && git pull origin main')

print('\n=== Remove old image + build fresh ===')
run('docker rmi ecommerce-app 2>/dev/null; true')
run_long('cd /root/ecommerce && docker compose build --no-cache', timeout=600)

print('\n=== Start ===')
run('cd /root/ecommerce && docker compose up -d')

print('\n=== Wait and check ===')
time.sleep(60)
run('cd /root/ecommerce && docker compose ps')
run('curl -sf http://localhost:8000/health || echo health_pending')
run('cd /root/ecommerce && docker compose logs --tail=30 app 2>&1')

ssh.close()
print('\n=== DONE ===')
