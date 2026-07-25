import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('162.35.186.39', username='root', password='DDracular123@', timeout=30)

def run(cmd, timeout=30):
    print(f'\n>>> {cmd}')
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    if out.strip(): print(out.strip()[:3000])
    if err.strip(): print('ERR:', err.strip()[:500])

# Check hero banners link_url
run("cd /root/ecommerce && docker compose exec -T postgres psql -U ecom_user -d ecom_db -c \"SELECT id, title, link_url, button_text FROM hero_banners WHERE is_active=true;\"")

# Check what the shop page actually does when "Shop Now" is clicked
run("curl -s http://localhost:8000/shop | grep -i 'shop.now\\|href.*shop\\|btn.*shop' | head -10")

# Check admin delete endpoint - try to delete product 1 without auth
run('curl -s -w "\\n%{http_code}" http://localhost:8000/api/admin/products/143 -X DELETE')

# Login and get token then try delete
run('curl -s http://localhost:8000/api/auth/login -X POST -H "Content-Type: application/json" -d "{\\"username\\":\\"admin@primenest.com\\",\\"password\\":\\"password123\\"}"')

ssh.close()
