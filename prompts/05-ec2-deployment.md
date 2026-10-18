# Stage 5: Make it deployable to EC2

Add minimal deployment instructions/scripts for running the existing TinyWMS HTTP application on Amazon EC2 Linux. Do not redesign the application. Preserve exactly the same application and JSON behavior students used on Raspberry Pi.

Document SSH, environment configuration, process startup and required network port. Update `docs/architecture.md` with Raspberry Pi and EC2 deployment variants and explicitly identify what stayed the same.

Required deployment artifacts for this stage:
- `deploy/ec2/run_inventory_server.sh` with concrete startup commands from stage root assumptions.
- `deploy/ec2/environment.example` documenting required environment variables.
- `deploy/ec2/README.md` (or equivalent section in stage README) with exact connect, configure, run, verify (`curl`), and cleanup/stop commands.

In `docs/architecture.md` "Component Assembly Map," mark this as a deployment-boundary shift: the HTTP app component is reused, while hosting/operations components are added. Keep dependencies and contracts explicit.

The stage README must include concrete operator/student steps: purpose, key files/scripts, deploy/run
commands, validation commands, cleanup/teardown, continuity note, and a "Component assembly update" section. No placeholder README output.
