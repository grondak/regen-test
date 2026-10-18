# Session 8 — Networking: IP, ports, TCP, DNS, firewalls

**Repo support:** Partly. No networking material exists, but the server from stage 05 is the thing you break and fix.

**Concept (20 min):** IP, ports, TCP, DNS, routing, public/private address, subnet intuition, firewall/security group.
**Demo (20 min):** intentionally break EC2 access, then use `ss`, `curl localhost`, IP/DNS and security-group rules to locate the break.

## Setup
EC2 instance from session 7, with the TinyWMS server running via `deploy/ec2/run_inventory_server.sh` in `05-ec2-deployment/`. Security group open for SSH only.

## 10 bullets to work from
1. Start from the failure everyone saw last session: `curl` works on the instance, but the same address fails from the laptop. Same server, same request, different result.
2. Layers in one sentence each: IP address picks the machine, TCP port picks the program, TCP makes the connection reliable, HTTP is the conversation inside it.
3. Public vs private address: the instance has both. `ip addr` shows only the private one; the public one is NAT'd. A subnet is a block of addresses (CIDR like `10.0.1.0/24`); give the intuition, skip the math.
4. DNS turns names into addresses: `dig` or `nslookup example.com`, `getent hosts <name>`. The browser used a name; `curl` to a bare IP skips DNS. Practice telling "DNS broke" from "network broke".
5. The diagnostic ladder, bottom to top. Is the process running (`ps aux | grep http_server`)? Is it listening, and on which address and port (`ss -ltnp`; look for `0.0.0.0:8000`)? Does it answer locally (`curl -i localhost:8000/inventory`)? Does it answer on the private IP? Does it answer from the outside?
6. Break 1: stop the server; `curl` from the laptop gives "connection refused", and `ss -ltn` shows nothing on 8000. Refused means the machine answered and nothing was listening.
7. Break 2: start it on a different port (`TINYWMS_PORT=9000`); `ss` shows 9000 and the old URL is refused. The fix is a client-side or config-side change, not a firewall.
8. Break 3: the one that matters. Server running and listening on `0.0.0.0:8000`, `curl localhost` works, but the outside request **hangs** until timeout. A timeout (no answer at all) is the signature of a firewall dropping packets. Open TCP 8000 in the security group (ideally only to your IP) and watch it work. Contrast refused vs timeout out loud.
9. Break 4 (optional): remove the rule for SSH from your IP and lose your own session; explain why changing a security group is dangerous and why the instance stays running anyway.
10. Wrap with the checklist students keep: process → listening address/port → local curl → security group/firewall → name resolution. This ladder is the same debugging path for every later hop (API Gateway, RDS, SQS).

## Note
- Python's `BaseHTTPRequestHandler` logs each request to stdout. Watch the server terminal during each break: a request that reaches the server prints a line; a blocked request prints nothing. That is the clearest proof the firewall is the problem.
