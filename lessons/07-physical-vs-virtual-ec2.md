# Session 7 — Physical vs virtual computers, and EC2

**Stage:** `05-ec2-deployment` · **Repo support:** Partly (it covers running the server on the instance; launching the instance is manual)

**Concept (20 min):** physical vs virtual computer; image, instance, CPU/RAM/storage; IaaS; region/AZ at useful depth.
**Demo (20 min):** launch EC2; SSH; repeat a few Session 2 Linux commands.

## Run sheet

**Manual part (AWS console, nothing in the repo does this):**
1. Launch an instance: Amazon Linux AMI, a small instance type (t3.micro or similar), a new key pair (download the `.pem`), a security group that allows **SSH (22) only** from your IP. Note the region and Availability Zone shown on the instance.
2. `chmod 400 key.pem` (callback to session 3: ssh refuses a key that others can read), then
```bash
ssh -i key.pem ec2-user@<public-ip>
```
3. Repeat session 2 on the instance: `uname -a`, `hostname`, `ip addr`, `free -h`, `df -h`, `cat /proc/cpuinfo | head`. Same Linux, different hardware answer. Note the private address on the interface vs the public IP you used to connect (session 8 depends on this).

**Repo part: put the app on the instance and run it.** Get the code there however you prefer (`git clone` of your fork, or `scp -r`). Then, on the instance, from `05-ec2-deployment/`:
```bash
cp deploy/ec2/environment.example deploy/ec2/environment     # TINYWMS_PORT=8000, TINYWMS_INVENTORY_FILE=data/inventory.json
set -a; . deploy/ec2/environment; set +a                      # export every variable in the file
bash deploy/ec2/run_inventory_server.sh                       # exec python3 src/http_server.py
```
Second SSH session, or a background run:
```bash
curl -i http://127.0.0.1:8000/inventory                       # works on the instance
```
The same URL from your laptop does **not** work yet; leave that for session 8.

Walk the 6-line wrapper `deploy/ec2/run_inventory_server.sh`: `set -euo pipefail`, `cd` to the repo root, defaults for two variables, `export`, `exec python3 src/http_server.py` (the shell replaces itself with the server process; check with `ps`).

Clean up: `pkill -f src/http_server.py`, `rm -f deploy/ec2/environment`, and **terminate the instance** (or stop it) so it stops billing.

## Talking points (the concept half)
- A virtual machine is a program pretending to be a computer, sharing real hardware with other customers. The image is the starting disk; the instance type is how much CPU/RAM you rent.
- IaaS: AWS runs the building, power, hardware and hypervisor; you run the OS and everything above it, including patching.
- Region = a geographic area; Availability Zone = a separate data center in it. Pick the region near you, put things you want to survive failures in more than one AZ.
- Cost: instances bill while running. Make "terminate it" part of every session's end.

## Caveats
- The README's block begins with `ssh ...` and then lists more commands; everything after the `ssh` runs on the instance. Say so out loud.
- Nothing in the repo copies the code to the instance, creates the key pair or the security group.
- The server binds `0.0.0.0`, which is exactly why the security group is what stands between it and the internet.
