"""Debug deploy - check DB state."""
import paramiko, time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('162.35.186.39', username='root', password='DDracular123@', timeout=15)
print('Connected!')

def run(cmd, timeout=30):
    print(f'\n>>> {cmd}')
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    if out: print(out)
    if err: print(err.rstrip())

# Check if the app container is running and its logs
run('cd /root/ecommerce && docker compose logs app 2>&1 | tail -40')

# Check the table schema directly
sql_check = "SELECT column_name FROM information_schema.columns WHERE table_name = 'users' ORDER BY ordinal_position;"
run(f'docker compose -f /root/ecommerce/docker-compose.yml exec -T postgres psql -U ecom_user -d ecom_db -c "{sql_check}"')

# Check alembic_version
run(f'docker compose -f /root/ecommerce/docker-compose.yml exec -T postgres psql -U ecom_user -d ecom_db -c "SELECT * FROM alembic_version;"')

ssh.close()
print('\n=== DONE ===')
