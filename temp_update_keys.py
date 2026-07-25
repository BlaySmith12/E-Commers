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

# Update .env with real Paystack keys
run("cd /root/ecommerce && sed -i 's|PAYSTACK_SECRET_KEY=sk_test_xxxx|PAYSTACK_SECRET_KEY=sk_test_a535a5327347b71afbed728ed477c9aecb8ac70d|' .env")
run("cd /root/ecommerce && sed -i 's|PAYSTACK_PUBLIC_KEY=pk_test_xxxx|PAYSTACK_PUBLIC_KEY=pk_test_52acc8c2c7e127b7cd222e568d712ccfbaa24590|' .env")
run("cd /root/ecommerce && sed -i 's|PAYSTACK_WEBHOOK_SECRET=whsec_xxxx|PAYSTACK_WEBHOOK_SECRET=whsec_skip|' .env")

# Verify the keys are set
run("cd /root/ecommerce && grep PAYSTACK .env")

# Restart app to pick up new env vars
run("cd /root/ecommerce && docker compose restart app")
time.sleep(15)

# Verify health
run("cd /root/ecommerce && docker compose ps")
run("curl -sf http://localhost:8000/health")
run("curl -sf -o /dev/null -w \"%{http_code}\" http://162.35.186.39/")

ssh.close()
