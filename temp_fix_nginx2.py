import paramiko, time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('162.35.186.39', username='root', password='DDracular123@', timeout=30)

def run(cmd, timeout=120):
    print(f'>>> {cmd}')
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    if out.strip():
        for line in out.strip().split('\n')[-15:]:
            print(line)
    if err.strip():
        for line in err.strip().split('\n')[-5:]:
            print('ERR:', line)

run('cd /root/ecommerce && docker compose up -d nginx')
time.sleep(5)
run('cd /root/ecommerce && docker compose ps')
run('curl -sf -o /dev/null -w "%{http_code}" http://162.35.186.39/')
run('curl -sf -o /dev/null -w "%{http_code}" http://162.35.186.39/health')
run('docker logs ecommerce-nginx-1 --tail=10 2>&1')
ssh.close()
