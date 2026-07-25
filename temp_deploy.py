"""Deploy to VPS via SSH."""
import paramiko
import time
import sys

HOST = "162.35.186.39"
USER = "root"
PASS = "DDracular123@"

def run(ssh, cmd, timeout=60):
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out: print(out)
    if err: print(err)
    return out, err

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=15)
print(f"Connected to {HOST}")

# Step 1: System update + Docker install
print("\n=== STEP 1: System setup ===")
run(ssh, "apt-get update && apt-get upgrade -y", timeout=120)
run(ssh, "apt-get install -y curl git ufw", timeout=120)
run(ssh, "curl -fsSL https://get.docker.com | sh", timeout=180)
run(ssh, "systemctl enable docker && systemctl start docker")
run(ssh, "apt-get install -y docker-compose-plugin", timeout=120)

# Step 2: Firewall
print("\n=== STEP 2: Firewall ===")
run(ssh, "ufw default deny incoming")
run(ssh, "ufw default allow outgoing")
run(ssh, "ufw allow ssh")
run(ssh, "ufw allow 80/tcp")
run(ssh, "ufw allow 443/tcp")
run(ssh, "echo y | ufw --force enable")

# Step 3: Clone repo
print("\n=== STEP 3: Clone repo ===")
run(ssh, "rm -rf /root/ecommerce")
run(ssh, "cd /root && git clone https://github.com/BlaySmith12/E-Commers.git ecommerce", timeout=60)

# Step 4: Configure .env
print("\n=== STEP 4: Configure .env ===")
run(ssh, "cd /root/ecommerce && cp .env.production .env")

# Step 5: Build and start
print("\n=== STEP 5: Build & Deploy ===")
run(ssh, "cd /root/ecommerce && docker compose up -d --build", timeout=600)

# Step 6: Wait and check
print("\n=== STEP 6: Health check ===")
time.sleep(10)
run(ssh, "cd /root/ecommerce && docker compose ps")
run(ssh, "curl -sf http://localhost:8000/health || echo 'Health check failed - may need more time'")

ssh.close()
print("\n=== DONE ===")
