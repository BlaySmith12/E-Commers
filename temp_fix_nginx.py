import paramiko, time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('162.35.186.39', username='root', password='DDracular123@', timeout=30)
print('Connected')

def run(cmd, timeout=120):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    if out.strip():
        print(out.strip())
    if err.strip():
        print(err.strip())

run('cd /root/ecommerce && docker compose up -d nginx')
time.sleep(5)
run('cd /root/ecommerce && docker compose ps')
run('curl -sf -o /dev/null -w "%{http_code}" http://162.35.186.39/ || echo FAIL')
run('curl -sf -o /dev/null -w "%{http_code}" http://162.35.186.39/admin/orders || echo FAIL')

ssh.close()
print('DONE')
