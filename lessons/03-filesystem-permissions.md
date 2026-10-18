# Session 3 — Filesystem tree, users, permissions, sudo

**Repo support:** No. Teach it live on the Pi. (The inventory files from later sessions give you realistic things to chmod, see bullet 8.)

**Concept (20 min):** filesystem tree, paths, `/home`, `/etc`, `/var`, users/groups, ownership, permissions, `sudo`.
**Demo (20 min):** navigate real Linux; create, move, copy and delete files; show a permissions failure, then fix it.

## 10 bullets to work from
1. One tree, one root `/`. No drive letters. Draw the top levels: `/home`, `/etc`, `/var`, `/tmp`, `/usr`, `/proc`.
2. What lives where: user files in `/home`, configuration in `/etc`, changing data and logs in `/var`, scratch in `/tmp`. Name the TinyWMS equivalents you will use later: code in the home directory, service config in `/etc/systemd` or `~/.config/systemd/user`, logs under `/var` or the journal.
3. Paths: absolute vs relative, `.` and `..`, `~`, `pwd`, `cd`, `ls -la`. Tab completion.
4. Make, copy, move, delete: `mkdir`, `touch`, `cp`, `mv`, `rm`, `rm -r` (and why `rm -rf /` jokes are not funny). Stress that there is no trash can.
5. Reading files: `cat`, `less`, `head`, `tail`. Use the course's own `inventory.json` as the file everyone reads.
6. Users and groups: `whoami`, `id`, `/etc/passwd` (what is and is not in it), root vs ordinary users.
7. Permissions: read the `ls -l` string (`-rw-r--r-- user group`), owner/group/other, r/w/x, why directories need `x`.
8. Live failure: create a file, `chmod 000` it, show `Permission denied`, fix with `chmod 644`. Then try to write a file in `/etc` or `/var/log` as the normal user and fail.
9. `sudo`: run one command as root, show the same write now succeeds, then explain why you do not live in a root shell and why `sudo` is a power you grant, not a default.
10. Close with a mini-exercise students do themselves: make `~/tinywms/data`, copy `inventory.json` into it, make it read-only, try to edit it, fix it. This is the same file session 5 loads from Python.
