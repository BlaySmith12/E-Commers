import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('162.35.186.39', username='root', password='DDracular123@', timeout=30)

def run(cmd, timeout=30):
    print(f'>>> {cmd}')
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    if out.strip(): print(out.strip()[:2000])
    if err.strip(): print('ERR:', err.strip()[:500:])

# Test /shop via public IP
run('curl -s -o /dev/null -w "%{http_code}" http://162.35.186.39/shop')
# Test /shop via localhost
run('curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/shop')
# Check nginx config
run('cat /root/ecommerce/nginx/nginx.conf')
# Test admin product delete - get a product ID first
run('curl -s http://localhost:8000/api/products | python3 -c "import sys,json; d=json.load(sys.stdin); print(d[:3] if isinstance(d,list) else d)"')

ssh.close()
