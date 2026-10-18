# TinyWMS pick-ticket worker deployment

This directory packages the long-running pick-ticket worker as a user service.

## What it does
- runs `src/pick_ticket_worker.py` in long-lived mode
- restarts the worker if it fails
- keeps the ticket file and state file in a per-user writable directory
- uses the existing SQS consumer helper instead of reimplementing queue receive/delete behavior

## Files
- `tinywms-pick-ticket-worker.service.in` - systemd user-service template
- `install_user_service.sh` - installs the rendered user-service file for the current checkout
- `environment.example` - example environment variables for the worker

## Install
1. Copy or edit the example environment file.
2. Run the installer from inside the repository checkout:
   ```bash
   ./deploy/pick-ticket-worker/install_user_service.sh
   ```
3. Reload systemd and enable the user service.

The installer resolves the current stage path from the repository checkout so the service points at the files you are actually running.

## Run the service
Start and inspect the worker with user-systemd commands:

```bash
systemctl --user daemon-reload
systemctl --user enable --now tinywms-pick-ticket-worker.service
systemctl --user status tinywms-pick-ticket-worker.service
journalctl --user -u tinywms-pick-ticket-worker.service -f
```

## Observe output
The worker appends durable tickets to the configured output file. To watch the file live while the service is running:

```bash
tail -f /path/to/pick-tickets.txt
```

## Stop and clean up
```bash
systemctl --user stop tinywms-pick-ticket-worker.service
systemctl --user disable tinywms-pick-ticket-worker.service
rm -f ~/.config/systemd/user/tinywms-pick-ticket-worker.service
systemctl --user daemon-reload
```

If you created a custom state or ticket directory for the exercise, remove those files too.
