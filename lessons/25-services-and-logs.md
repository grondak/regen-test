# Session 25 — Services, logs and files, with an operational purpose

**Stage:** `15-pick-ticket-worker` · **Repo support:** Yes (systemd files exist; they need a Linux machine and a real queue, so I could not run them on this Mac) · **Run on:** the Pi or an EC2 instance, from `20-final-walkthrough/`

**Concept (20 min):** services, logs and files revisited; background execution and observation.
**Demo (20 min):** install and start the worker as a service; submit a browser order; watch `tail -f pick-tickets.txt`.

## Run sheet
Everything here is in `deploy/pick-ticket-worker/` (files: `tinywms-pick-ticket-worker.service.in`, `install_user_service.sh`, `environment.example`, `README.md`).

**Step 1: read the unit file together.** `ExecStart=/usr/bin/env python3 -m src.pick_ticket_worker ${TINYWMS_QUEUE_URL} ${TINYWMS_TICKET_FILE} --state-file ... --wait-time-seconds ... --max-number-of-messages ...`; `EnvironmentFile`; `WorkingDirectory` (filled in with the repo path by the installer); `Restart=on-failure` and `RestartSec=5`; `KillSignal=SIGTERM`; `WantedBy=default.target`. Tie each line back to sessions 4 and 7 (environment, working directory, exit code, signals).

**Step 2: configure.** The unit reads `%E/tinywms-pick-ticket-worker.env`, which for a user service is `~/.config/tinywms-pick-ticket-worker.env`. The README says only "copy or edit the example environment file", so do this explicitly:
```bash
mkdir -p ~/.config /var/tmp/tinywms
cp deploy/pick-ticket-worker/environment.example ~/.config/tinywms-pick-ticket-worker.env
# edit it: set TINYWMS_QUEUE_URL=... (the SQS URL), keep the ticket and state paths under /var/tmp/tinywms
```
The worker also needs AWS credentials to reach SQS. On EC2 attach a role (session 10); on the Pi you must put access keys somewhere (`aws configure`), which is the credentials-vs-roles lesson made concrete.

**Step 3: install and start, then watch it.**
```bash
./deploy/pick-ticket-worker/install_user_service.sh      # renders the unit into ~/.config/systemd/user, then enable --now
systemctl --user status tinywms-pick-ticket-worker.service
journalctl --user -u tinywms-pick-ticket-worker.service -f      # the worker's stdout: ticket lines and message metadata
tail -f /var/tmp/tinywms/pick-tickets.txt                       # the durable output file
```
Place an order from the browser (stack from sessions 12–16 deployed) and watch the ticket line appear in both places.

**Step 4: operate it.**
```bash
pkill -f pick_ticket_worker            # kill it: systemd restarts it after 5 seconds (Restart=on-failure)
systemctl --user restart tinywms-pick-ticket-worker.service
systemctl --user stop tinywms-pick-ticket-worker.service        # SIGTERM; the worker finishes its batch
```
A user service stops when you log out unless lingering is enabled (`loginctl enable-linger $USER`); mention it if the demo is over SSH.

**Step 5: clean up** with the commands in the README's "Stop and clean up".

## Talking points
- A service is a process someone else supervises: start at boot, restart on crash, collect its output. systemd does for the worker what you did by hand with `&` and `tail -f` in session 4.
- Logs vs files: the journal is for operators (what is the process doing); the ticket file is the product.

## No AWS handy?
Run the offline version of the same worker (`lessons/support/worker_demo.py`, session 24) and skip the systemd steps; or use systemd with the placeholder queue and show the worker failing and restarting.
