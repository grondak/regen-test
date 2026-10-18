# Session 2 — Computer anatomy, the OS, and why Linux on tiny computers

**Repo support:** No. Nothing in the repo covers this; teach it live on the Pi.

**Concept (20 min):** CPU, RAM, storage, OS, kernel/user space, process, filesystem, network interface. Why Linux is useful on tiny computers.
**Demo (20 min):** boot and network the Pi; log in; `uname`, `hostname`, `ip`, `free`, `df`, `ls`, `/proc`.

## 10 bullets to work from
1. Start with the physical Pi on the table: point at the CPU/SoC, RAM, the SD card (storage), the Ethernet/Wi-Fi interface, the power. Everything else is software.
2. The five jobs: compute (CPU), working memory (RAM, lost on power-off), durable storage (SD/SSD), input/output, network. Quote the sizes of this Pi's RAM and card.
3. What an OS does: shares the hardware between programs, hides device differences, enforces who may touch what.
4. Kernel space vs user space: programs ask the kernel (system calls) to read a file, open a socket, start a process. Mention that a crashed program does not take the machine down.
5. A process is a running program with its own memory and an ID. Foreshadow session 4 and the TinyWMS server.
6. The filesystem is the OS's way to name storage; everything is a path. Foreshadow session 3.
7. Why Linux on tiny machines: free, small, runs headless, scriptable, the same on a Pi and a cloud server. The skills transfer unchanged to EC2 in session 7.
8. Live: boot the Pi, find its IP from the router or `hostname -I`, SSH in from the laptop. First "it's a computer you talk to over a network" moment.
9. Live, one command at a time, say what each shows: `uname -a` (kernel and CPU type), `hostname`, `ip addr` (interface and address), `free -h` (RAM), `df -h` (storage), `ls /`, `cat /proc/cpuinfo`, `cat /proc/meminfo`, `ls /proc | head`.
10. `/proc` is the kernel's live status shown as files; connect it to the idea that "everything is a file". Have students run the same commands on their own machine or a shared Pi and compare the answers. These outputs are the baseline you repeat on EC2 in session 7.
