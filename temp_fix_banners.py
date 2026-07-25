import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('162.35.186.39', username='root', password='DDracular123@', timeout=30)

def run(cmd, timeout=30):
    print(f'\n>>> {cmd}')
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    if out.strip(): print(out.strip()[:2000])
    if err.strip(): print('ERR:', err.strip()[:500])

# Fix hero banner link_urls to point to actual pages
# Banner 1: /collections/best-sellers -> /shop
# Banner 5: /collections/new-arrivals -> /shop
# Banner 4: /brands/grohe -> /shop (no brand detail page exists)
run("cd /root/ecommerce && docker compose exec -T postgres psql -U ecom_user -d ecom_db -c \"UPDATE hero_banners SET link_url='/shop' WHERE link_url IN ('/collections/best-sellers', '/collections/new-arrivals', '/brands/grohe');\"")

# Verify
run("cd /root/ecommerce && docker compose exec -T postgres psql -U ecom_user -d ecom_db -c \"SELECT id, title, link_url, button_text FROM hero_banners WHERE is_active=true;\"")

ssh.close()
