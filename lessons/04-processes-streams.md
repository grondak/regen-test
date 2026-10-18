# Session 4 — Processes, streams, pipes, signals, services and logs

**Stage:** `02-linux-visible` · **Repo support:** Yes · **Run from:** `02-linux-visible/`

**Concept (20 min):** processes, stdin/stdout/stderr, pipes, redirection, signals, services and logs.
**Demo (20 min):** `ps`, `grep`, `kill`, a pipeline, and a long-running process you can watch.

## Run sheet (every command below was run and works)

**Step 1: three streams and an exit code.** `linux_visible.py` has three subcommands, `env`, `echo` and `fail`.
```bash
printf 'hello from stdin\n' | python3 src/linux_visible.py echo       # stdin -> stdout through a pipe
python3 src/linux_visible.py fail; echo "exit code: $?"               # message on stderr, exit code 3
python3 src/linux_visible.py fail 2>/dev/null; echo "exit code: $?"   # hide stderr: the failure is still visible in $?
python3 src/linux_visible.py fail 2>errors.txt; cat errors.txt        # redirect stderr to a file
```

**Step 2: environment variables are inherited by child processes.**
```bash
python3 src/linux_visible.py env                          # prints  unset
TINYWMS_DEMO=visible python3 src/linux_visible.py env     # prints the value, for this one command only
```

**Step 3: a long-running process, a log file, and `tail -f`.** The watcher appends a snapshot of the inventory every 2 seconds.
```bash
python3 src/inventory_watcher.py data/inventory.json /tmp/tinywms-watch.log &    # & = background
cat /tmp/tinywms-watch.log
tail -f /tmp/tinywms-watch.log        # in a second terminal; Ctrl+C stops tail, not the watcher
```

**Step 4: find it, filter it, stop it.**
```bash
ps aux | grep inventory_watcher | grep -v grep     # the pipeline: ps output -> grep
pgrep -f inventory_watcher                         # just the PID
kill <PID>                                         # SIGTERM; Ctrl+C is SIGINT
kill -9 <PID>                                      # SIGKILL, last resort: process cannot clean up
rm /tmp/tinywms-watch.log
```
Edit `data/inventory.json` (change a quantity or add an item) while the watcher runs and watch the `count`/`skus` in the log change. The watcher only logs SKU names and the count, so an edit to a quantity will not show; add or remove an item instead.

**Services and logs** are introduced here only as an idea (a process nobody is babysitting that writes to a log). Session 25 does it properly with systemd.

## Talking points
- Every process has three standard streams. The shell connects them: `|` joins one process's stdout to another's stdin; `>` and `2>` redirect to files.
- Exit code 0 = success, anything else = failure. Scripts and systemd both rely on it.
- A signal is a message to a process. SIGINT (Ctrl+C) and SIGTERM ask nicely; SIGKILL cannot be caught.
- Callback to remember: the pick-ticket worker in session 24 handles SIGTERM so `systemctl stop` shuts it down cleanly.

## Caveat
- `inventory_watcher.py` never exits on its own; students must stop it or they leave a process running.
