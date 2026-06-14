# Set up Apex on Oracle Cloud Free Tier (always-on brain)

Oracle Cloud's Always Free tier gives you a **2 OCPU / 12 GB RAM Ampere A1 VM —
genuinely free forever**. This is the recommended host for the autonomous cortex
so Apex never sleeps.

---

## 1. Create your free Oracle Cloud account

1. Go to `cloud.oracle.com` → **Start for free**
2. Enter name, email, region (pick one near you), credit card (verification only — not charged)
3. Confirm email → account created

---

## 2. Provision the free VM

1. Oracle Cloud Console → **Compute → Instances → Create Instance**
2. Click **Change image** → **Ubuntu** → Ubuntu 22.04 LTS (aarch64) ✓
3. Click **Change shape** → **Ampere** → `VM.Standard.A1.Flex`
   - Set **OCPUs: 2**, **Memory: 12 GB** (both free-tier eligible)
4. Under **Networking**: leave defaults (new VCN + public subnet gets created)
5. **Add SSH keys**: upload your `~/.ssh/id_ed25519.pub` (or generate a new pair)
6. Click **Create**

The VM boots in ~2 minutes. Note the **public IP** from the instance details page.

---

## 3. Open firewall for Tailscale (and close everything else)

In Oracle Console → **Networking → Virtual Cloud Networks → your VCN →
Security Lists → Default Security List**:

- **Ingress rules**: keep only SSH (port 22). Remove any rules for port 80/443.
- Apex will be reached via Tailscale, not directly — no public port needed.

Also open the OS firewall on the VM:
```bash
sudo iptables -F INPUT
sudo iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 22 -j ACCEPT
sudo iptables -A INPUT -i lo -j ACCEPT
sudo iptables -A INPUT -j DROP
sudo netfilter-persistent save    # apt install iptables-persistent if needed
```

---

## 4. SSH in and install dependencies

```bash
ssh ubuntu@<your-oracle-ip>

# System packages
sudo apt update && sudo apt install -y git curl python3-pip python3-venv

# uv (fast Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc   # reload PATH

# Tailscale (connects VM to your private network)
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up   # opens auth URL — paste it in your browser
```

After `tailscale up`, your VM gets a Tailscale IP (e.g. `100.x.x.x`). From your
laptop: `ssh ubuntu@$(tailscale ip -4)` — no public IP needed anymore.

---

## 5. Clone Apex and configure

```bash
git clone https://github.com/alexkhouryyy/ni.git
cd ni

# Copy your .env from your laptop
# On your LAPTOP: scp .env ubuntu@<tailscale-ip>:~/ni/.env

# Install Python dependencies
uv pip install -r requirements.txt
```

Test it boots:
```bash
uv run python main.py --text
# Should print: Voice AI Agent ... Session #1 started.
# Ctrl+C to exit
```

---

## 6. Install as a systemd service (auto-start on boot)

```bash
# Install the service file (substitute your username)
sudo cp ~/ni/scripts/apex.service /etc/systemd/system/apex@ubuntu.service

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable apex@ubuntu
sudo systemctl start apex@ubuntu

# Verify it's running
sudo systemctl status apex@ubuntu
journalctl -u apex@ubuntu -f   # live logs
```

The `apex@ubuntu` service name is `apex@<username>` — it uses `%i` in the unit file
to fill in the username so WorkingDirectory and ExecStart resolve correctly.

---

## 7. Connect your laptop's awareness watchers (optional, hybrid mode)

The cloud VM runs the always-on scheduler, cortex, and dashboard. Your laptop
runs the screen/clipboard/file watchers and forwards events.

On your **laptop**, start Apex normally:
```bash
uv run python main.py --text
```

Both instances share **the same Tailscale network** and the same `DASHBOARD_TOKEN`.
Open `http://<oracle-tailscale-ip>:7860` in your browser (add `?token=whowantstobeking`).
The laptop Apex and the cloud Apex have separate SQLite DBs for now — full
brain-sync is a future milestone.

---

## 8. Update PUBLIC_BASE_URL

Now that your always-on host has a stable Tailscale address, set it in `.env`
on the Oracle VM:

```bash
echo "PUBLIC_BASE_URL=http://$(tailscale ip -4):7860" >> ~/ni/.env
sudo systemctl restart apex@ubuntu
```

Or if you have a Cloudflare named tunnel pointing at the Oracle VM, use the
stable HTTPS URL instead.

---

## Verification

```bash
# From your phone (on WiFi or cellular), open:
http://<oracle-tailscale-ip>:7860?token=whowantstobeking

# Apex loads and responds even when your laptop is off ✓
```

Check systemd survived a reboot:
```bash
sudo reboot
# wait 30 seconds
ssh ubuntu@<tailscale-ip>
systemctl status apex@ubuntu   # should show active (running)
```
