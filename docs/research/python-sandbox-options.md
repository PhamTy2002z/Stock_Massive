# Research: sandbox options for running untrusted, LLM-authored Python

Resolves issue #29 (part of the #16 Intelligent Quant map). Feeds the yes/no
decision in #33: **should we run LLM-authored Python at all?** The question is not
"which vendor is nicest" — it is whether the operational cost and the security
floor are acceptable for a small internal `docker-compose` (`db`, `redis`, `api`)
that today runs FastAPI, and separately for a hypothetical production deployment
with external users.

Method: primary sources only — official docs and source for CPython, nsjail,
gVisor, Docker, Pyodide, Firecracker, e2b, Modal, Cloudflare, Judge0, the Linux
man-pages/kernel docs, and published CVE/advisory records for each escape class.
Empirical latency and one escape proof were run locally on this repo's own
`stockmassive-api:latest` image (Docker Engine 29.1.3, runc 1.3.4, macOS host /
Linux VM) on 2026-08-12. Blog summaries are used only where they restate a vendor
primary and are labelled; anything not confirmable from a primary is marked
**unverified**.

## TL;DR — the security floor and the recommendation

There is a hard split, and it is the whole answer:

1. **In-process restriction is not a boundary — it is theatre.** CPython's own
   documentation retired restricted execution in 2003 as unfixable; RestrictedPython
   and PEP 578 both say in writing they are not sandboxes. I reproduced the classic
   `__builtins__={}` escape locally in **8 lines** — it reached `os.getuid()` and
   `os.listdir('/')` with no imports and no builtins. Do not ship this as the
   isolation layer for LLM-authored code. Ever.

2. **The real floor is OS-level: a per-call container with a locked-down config,
   and for untrusted code a kernel-independent layer (gVisor) or a microVM on top.**
   A plain hardened Docker container shares the host kernel; container escapes are a
   live, recurring CVE class (runc CVE-2019-5736, CVE-2024-21626; cgroup
   CVE-2022-0492). gVisor interposes its own kernel so a guest exploit must first
   defeat the Sentry *and* its seccomp jail; a microVM (Firecracker) puts a
   hardware virtualization boundary in the path.

**Recommendation for the internal `docker-compose` deployment (named default):**
**Self-hosted per-call Docker container, hardened, running the existing
`stockmassive-api` image, ideally under the gVisor (`runsc`) runtime.** It reuses
the image that already has `numpy`/`pandas`/`matplotlib`, costs $0 in new vendors,
adds no new data-egress surface, and — measured here — adds **~0.45–0.7 s** of
startup per call, which is negligible next to LLM token latency. gVisor is a
one-line runtime swap on the Linux host and buys a second kernel boundary; where it
cannot run (e.g. a non-Linux CI box), the hardened-runc profile in §7 is the
fallback floor. Keep the in-process/RestrictedPython option **off the table**.

**If the answer were "we need this in production for external users":** **a managed
Firecracker-microVM sandbox — e2b (or Modal Sandboxes)**. External, adversarial
users make kernel-sharing unacceptable and make sandbox-escape response somebody
else's full-time job; a microVM boundary plus a vendor security team is worth the
~$0.50–1 per 1000 short executions (§8). Self-hosting the same safety (Firecracker
+ jailer + orchestration) is possible but is a standing infra project, not a
feature.

## The seven options at a glance

| Option | Boundary type | Startup / call | Mem/CPU ceiling | Egress control | FS isolation | numpy/pandas/scipy | Data in / results out | Fit here |
|---|---|---|---|---|---|---|---|---|
| **1. In-process restricted builtins / RestrictedPython** | none (same interpreter) | ~0 ms | none (soft, bypassable) | none | none | yes (host env) | in-memory | **Never** — not a boundary (proven below) |
| **2. Subprocess + seccomp / nsjail** | 1 kernel (syscall filter + namespaces) | tens of ms | rlimit/cgroup | netns (`CLONE_NEWNET`) | mount ns + chroot | if host has them | files/pipes | Linux-only building block; DIY |
| **3. gVisor (`runsc`)** | 1.5 (own kernel + seccomp) | ~sub-second (perf overhead on syscall-heavy) | runsc/OCI limits | netstack or `--network none` | independent VFS | via container image | files/stdio (OCI) | **Strong self-host floor (Linux)** |
| **4. Per-call Docker container (hardened)** | 1 shared kernel | **0.45–0.7 s (measured)** | `--memory`/`--cpus`/`--pids-limit` | `--network none` | image + `--read-only`+`tmpfs` | **yes — already in our image** | bind-mount / stdio | **Default for internal** |
| **5. WASM (Pyodide)** | strong (WASM VM, no syscalls) | ~1–2 s runtime init (unverified exact) | JS heap / host | none by default (no sockets) | virtual MEMFS only | numpy/scipy yes; **pandas via extra recipe** | JS↔Python bridge | Good for pure math; no threads/sockets/subprocess |
| **6. Managed microVM (e2b / Modal)** | 2 (hardware virt) | **<200 ms (e2b, vendor)** | vendor plan | vendor allowlist/block | full VM | yes (custom template) | SDK upload / stdout+files | **Production choice** |
| **7. Judge0 (self-host)** | container (isolate) | fast | per-submission limits | config flag | isolate | if image has them | REST API | Escape-CVE history; needs privileged worker |

## 1. In-process restriction (restricted builtins / RestrictedPython) — a false floor

This is the option that looks cheapest and is the one that ends the whole design if
chosen. Every primary source that ever tried it disowns it:

- **CPython itself withdrew restricted execution.** The stdlib `rexec`/`Bastion`
  framework was *disabled* in Python 2.3: "these modules have been disabled due to
  various known and not readily fixable security holes."
  (<https://docs.python.org/2/library/restricted.html>)
- **PEP 578** (audit hooks) states plainly: "This is not sandboxing, as this
  proposal does not attempt to prevent malicious behavior," and has a "Why Not A
  Sandbox" section explaining that restricting CPython functionality has repeatedly
  failed. (<https://peps.python.org/pep-0578/>)
- **RestrictedPython's own docs:** "RestrictedPython is not a sandbox system or a
  secured environment." (<https://restrictedpython.readthedocs.io/en/latest/>)

**Proof (run locally, this repo, CPython 3.12).** With `exec(code, {"__builtins__":
{}})` — the textbook "locked" namespace — the following payload, using only literals
and attribute access, walked the class hierarchy to a live module's `__globals__`
and recovered `os`:

```python
subs = ().__class__.__base__.__subclasses__()
mods = [s for s in subs if s.__init__.__class__.__name__ == 'function']
for s in mods:
    g = s.__init__.__globals__
    if 'sys' in g:
        os_mod = g['sys'].modules['os']; break
os_mod.getuid(); os_mod.listdir('/')
```

Output: `os.getuid() -> 501`, `os.listdir('/') -> ['home','usr','bin','etc',...]`.
No `import`, no builtins, no tricks beyond attribute access. This is the canonical
Python sandbox-escape class and it is unpatched-by-design, because the object graph
*is* the language. **Known escape classes:** `().__class__.__base__.__subclasses__()`
walks; `__globals__`/`__builtins__` recovery; generator/frame introspection;
`gc.get_objects()`; C-extension re-entry. **Minimum safe configuration per primary
sources: there isn't one — the primary sources say do not use it as a boundary.**
Operating cost is near-zero and that is exactly the trap.

## 2. Subprocess + seccomp / nsjail — the Linux building block

The honest self-hosted primitive underneath options 3/4. It is a *toolkit*, not a
turnkey product.

- **seccomp-bpf** filters syscalls via BPF. The kernel doc is explicit about its
  limits: "System call filtering isn't a sandbox. It provides a clearly defined
  mechanism for minimizing the exposed kernel surface." BPF **cannot dereference
  pointers**, so it can only inspect scalar syscall arguments (no path/string
  inspection), and it warns architecture number-checking is mandatory (x32/compat
  ABI bypasses). (<https://www.kernel.org/doc/html/latest/userspace-api/seccomp_filter.html>)
- **nsjail** (Google, "not an official Google product") composes namespaces (UTS,
  MOUNT, PID, IPC, NET, USER, CGROUP, TIME), cgroups v1/v2, rlimits, and Kafel
  seccomp policies into one launcher. (<https://github.com/google/nsjail>)
- **Startup:** tens of ms — it is a `clone()`+`execve()`, no image pull.
- **Egress:** a fresh empty `NET` namespace = no network. **FS:** mount namespace +
  chroot/pivot_root to a minimal tree. **Ceilings:** rlimits + cgroups.
- **pandas/numpy/scipy:** only if the chroot/tree you build contains them — you
  assemble the environment yourself.
- **Escape classes / caveats:** it leans on **unprivileged user namespaces**, which
  are themselves an attack-surface expander — the man-page notes unprivileged userns
  lets a process hold `CAP_SYS_ADMIN` *inside* the namespace and has produced its own
  CVE history (the `setgroups()` fix in Linux 3.19).
  (<https://man7.org/linux/man-pages/man7/user_namespaces.7.html>) A wrong seccomp
  allowlist (e.g. leaving `io_uring`, `ptrace`, `clone` with certain flags,
  `unshare`) reopens escape paths.
- **Fit:** correct, free, Linux-only, and entirely DIY. For our purpose it is better
  consumed *through* Docker/gVisor (which apply sane defaults) than hand-rolled.

## 3. gVisor (`runsc`) — the strongest self-hostable floor

gVisor runs the workload against **its own userspace kernel (the Sentry)** written
in Go, not the host kernel directly.

- **Security model (primary):** "applications are not able to directly craft
  specific arguments or flags for the host System API, or interact directly with
  host primitives"; "Every supported call has an independent implementation in the
  Sentry." The Sentry is *itself* confined by seccomp and minimal host surface — a
  two-layer boundary. (<https://gvisor.dev/docs/architecture_guide/security/>)
- **What it does NOT protect against (primary, stated):** "gVisor does not provide
  protection against hardware side channels," and "A sandbox is not a substitute for
  a secure architecture." (same page)
- **CVE bar (primary):** a reported escape only counts as a gVisor CVE if it "cross[es]
  the sandbox boundary," is not attacker-configured, and is gVisor-specific — and
  must defeat **both** the Sentry and its Linux seccomp jail.
  (<https://gvisor.dev/security/>) As of this research the GitHub Security Advisories
  list for `google/gvisor` shows **no published advisories**
  (<https://github.com/google/gvisor/security/advisories>). gVisor documents it was
  **not vulnerable** to container-escape CVE-2020-14386 because it disables raw
  sockets and doesn't implement `PACKET_RX_RING`.
  (<https://gvisor.dev/docs/architecture_guide/security/>)
- **Integration:** installs as a Docker runtime — `docker run --runtime=runsc ...`.
  (<https://gvisor.dev/docs/user_guide/quick_start/docker/>) So the hardened-Docker
  recipe in §7 becomes gVisor by changing one flag.
- **Requirements:** **Linux host**; platforms are KVM (best on bare metal), systrap
  (default since 2023, works in VMs), ptrace (legacy).
  (<https://gvisor.dev/docs/architecture_guide/platforms/>,
  <https://gvisor.dev/docs/user_guide/production/>)
- **Cost:** performance overhead is structural on syscall-heavy workloads — the perf
  guide notes small operations pay large relative overhead while CPU-bound and
  disk-bound work is near-native. (<https://gvisor.dev/docs/architecture_guide/performance/>)
  Quant math (numpy/pandas number-crunching) is CPU-bound, i.e. the cheap case.
- **Minimum safe config (primary):** default netstack (not host passthrough — host
  passthrough is "for semi-trusted" workloads only), don't mount host paths, keep
  the default seccomp jail. pandas/numpy/scipy: whatever the container image ships.

## 4. Per-call Docker container (hardened) — the internal default

A single shared host kernel, hardened with Docker's own controls. This is the
pragmatic floor and, crucially, it reuses the image we already build.

- **Docker's own position (primary):** namespaces give "the first and most
  straightforward form of isolation"; the daemon "requires `root` privileges";
  "only trusted users should be allowed to control your Docker daemon"; and — the
  key caveat — "the default set of capabilities and mounts given to a container may
  provide incomplete isolation, either independently, or when used in combination
  with kernel vulnerabilities." (<https://docs.docker.com/engine/security/>)
- **Default seccomp** blocks ~44 of 300+ syscalls, including `bpf`, `kexec_load`,
  `io_uring_*`, and namespace calls "due to security vulnerabilities that can be
  exploited to break out of containers."
  (<https://docs.docker.com/engine/security/seccomp/>)
- **userns-remap** maps container-root to an unprivileged host UID: "If a process
  attempts to escalate privilege outside of the namespace, the process is running as
  an unprivileged high-number UID on the host."
  (<https://docs.docker.com/engine/security/userns-remap/>)
- **Ceilings / egress / FS (primary flag semantics):** `--memory`, `--cpus`,
  `--pids-limit` (fork-bomb guard), `--network none` (no egress), `--read-only` +
  `--tmpfs /tmp:noexec,nosuid`, `--cap-drop ALL`, `--security-opt no-new-privileges`,
  `--user`. (<https://docs.docker.com/reference/cli/docker/container/run/>,
  <https://docs.docker.com/engine/containers/resource_constraints/>)
- **pandas/numpy/matplotlib:** **already present** — verified in
  `stockmassive-api:latest`: numpy 2.2.6, pandas 2.3.3, matplotlib 3.11.1, Python
  3.12.13. **scipy / scikit-learn / statsmodels / pyarrow are NOT installed** — add
  to the image if the tool surface needs them.
- **Data in / results out:** stdin/argv/env in; stdout + a writable `tmpfs` (or a
  read-only bind of an input file) out; **plots** via `matplotlib.use("Agg")` +
  `savefig` to `tmpfs`, read back as PNG bytes — measured working under the full
  hardened profile below.
- **Measured latency (this repo, 5 runs each, warm image):**

  | Scenario | Per-call wall time |
  |---|---|
  | `docker run alpine true` (runtime floor) | ~0.21–0.26 s |
  | `python -c pass` on api image | ~0.22–0.29 s |
  | `import pandas, numpy` (unhardened) | ~0.51–0.87 s |
  | **`import pandas, numpy` (full hardened flags)** | **~0.45–0.50 s** |
  | hardened + matplotlib Agg + `savefig` PNG | ~0.66–0.75 s |

  So the *isolation* adds essentially nothing over the container floor; the cost is
  the ~0.2 s runtime start plus import time, and it is dwarfed by LLM latency.
  (Docker Engine 29.1.3; default runtime `runc` 1.3.4; builtin seccomp + AppArmor
  confirmed via `docker info`.)
- **Known escape classes (primary CVEs):**
  - **runc CVE-2019-5736** (CVSS 8.6) — overwrite the host `runc` binary via
    `/proc/self/exe` from inside a container → host root.
    (<https://nvd.nist.gov/vuln/detail/CVE-2019-5736>)
  - **runc CVE-2024-21626** (CVSS 8.6) — leaked file descriptor to host
    `/sys/fs/cgroup`; `cwd=/proc/self/fd/N` escapes to the host filesystem.
    (<https://github.com/opencontainers/runc/security/advisories/GHSA-xr7r-f8xq-vfvv>)
  - **cgroups v1 CVE-2022-0492** (CVSS 7.8) — `release_agent` abuse escalates and
    "bypass[es] the namespace isolation."
    (<https://nvd.nist.gov/vuln/detail/CVE-2022-0492>)
  These are why kernel-sharing is the residual risk: a container is only as strong as
  the runc/kernel version underneath it.
- **Minimum config considered safe (synthesised from Docker primaries):**
  `--network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m --cap-drop ALL
  --security-opt no-new-privileges --pids-limit 64 --memory 512m --cpus 1 --user <nonroot>`,
  keep the default seccomp profile, enable userns-remap on the daemon, keep runc
  patched, and (for the untrusted tier) add `--runtime=runsc`.

## 5. WASM / Pyodide — strong isolation, but a different Python

Pyodide is CPython compiled to WebAssembly. The WASM VM has **no syscalls and no
ambient host access**, so the isolation story is strong *by construction* — but the
runtime is constrained.

- **Constraints (primary):** "The following modules can be imported, but are not
  functional due to the limitations of the WebAssembly VM: multiprocessing,
  threading" and sockets; `ssl` is a non-OpenSSL stub; many stdlib modules
  (`fcntl`, `resource`, `subprocess`-relevant, etc.) are removed.
  (<https://pyodide.org/en/stable/usage/wasm-constraints.html>, fetched from the repo
  source `docs/usage/wasm-constraints.md`)
- **Scientific stack:** **numpy and scipy build in** (confirmed:
  `pyodide/pyodide-recipes/packages` contains `numpy`, `scipy`, `pandas`,
  `matplotlib`, `scikit-learn`, `statsmodels`, `pyarrow` — 334 recipes total).
  numpy/scipy are core; **pandas/matplotlib/sklearn load as extra packages** at
  runtime (download + init cost). No threads means some libraries need patches.
- **FS / data:** an in-memory virtual filesystem (MEMFS) only; data crosses the
  JS↔Python bridge; **plots** render to the virtual FS as PNG and are read back over
  the bridge.
- **Egress:** none by default — no sockets; the only network is host-mediated
  `fetch` (browser CORS applies). This is a *feature* for untrusted code.
- **Startup:** runtime init on the order of ~1–2 s plus per-package load;
  exact figure **unverified** here (no local WASM bench run).
- **Escape classes:** escaping WASM itself means a bug in the host WASM engine
  (V8/Wasmtime) — a much narrower, well-funded surface than the Linux kernel. The
  practical risk moves to resource exhaustion (memory/CPU) and the host embedding.
- **Cloudflare Python Workers** are the managed Pyodide form: beta, `python_workers`
  flag required, in-memory ephemeral FS, no threading/multiprocessing; package set is
  the Pyodide set. (<https://developers.cloudflare.com/workers/languages/python/>,
  <https://developers.cloudflare.com/workers/languages/python/stdlib/>,
  <https://developers.cloudflare.com/workers/languages/python/packages/>)
- **Fit:** excellent for *pure numerical* tool calls with no OS needs; awkward if the
  quant code expects threads, real sockets, subprocess, or the full pandas/pyarrow
  path without load-time cost. A viable **in-process-safe** option that a later
  iteration could embed directly in `apps/api` via `pyodide`/`wasmtime`.

## 6. Managed microVM sandboxes (e2b, Modal) — the production answer

These put a **hardware-virtualization boundary** (Firecracker microVM) between guest
code and host, and hand the escape-response burden to a vendor.

- **e2b:** open-source infra (Firecracker + Nomad + Consul, Terraform-deployed;
  <https://github.com/e2b-dev/infra>); "isolated sandboxes that let agents safely
  execute code"; Firecracker described as "a microVM made to run untrusted
  workflows." **Startup "less than 200 ms"** for same-region sandboxes
  (<https://e2b.dev/>). Data in via SDK `sandbox.commands.run()` / file upload;
  results via stdout/stderr and file download (<https://docs.e2b.dev/>). Custom
  Templates bake in pandas/numpy/scipy. Self-hostable on AWS/GCP.
  (<https://github.com/e2b-dev/E2B>)
- **Modal Sandboxes:** `modal.Sandbox.create()` with `cpu` (fractional cores, with
  optional hard limit), `memory` (MiB, request/limit), `timeout` (default **300 s**,
  up to 24 h), `workdir`; egress via `block_network=True` ("Drops all outbound
  traffic"), `outbound_cidr_allowlist`, and beta `outbound_domain_allowlist`
  (TLS-443, wildcards). Data via stdout/stdin, mounted Volumes, `sandbox.exec()`.
  (<https://modal.com/docs/reference/modal.Sandbox>,
  <https://modal.com/docs/guide/sandbox>, <https://modal.com/docs/guide/sandbox-networking>)
  Modal does not publish a single cold-start latency number in its docs (**startup
  figure unverified**); it documents filesystem/memory snapshots for faster starts.
- **Escape classes:** a Firecracker escape must defeat the VMM. Firecracker's design
  treats "all vCPU threads … as running malicious code," ships a **minimal device
  model** (VirtIO net/block, serial, partial keyboard — nothing else), and runs
  behind a **jailer** that drops privileges + a per-thread **seccomp filter loaded
  before any guest code runs**.
  (<https://github.com/firecracker-microvm/firecracker/blob/main/docs/design.md>)
  Residual risk is hardware side channels and VMM 0-days — the vendor's problem to
  patch, and a much smaller surface than a shared Linux kernel.
- **Fit:** the right answer when users are external/adversarial — you rent a
  hardware boundary and a security team. Overkill and an unnecessary data-egress
  dependency for an internal-only tool.

## 7. Judge0 — capable but scarred; not for this

Judge0 is a self-hostable REST execution engine (90+ languages) built on IOI
`isolate`. (<https://github.com/judge0/judge0>) It is designed for autograder-style
untrusted submissions, so on paper it fits. But its **advisory history is exactly
the escape story we're trying to avoid**:

- **CVE-2024-28185 / CVE-2024-28189** — symlink tricks (`run_script` / `chown` on a
  symlink) achieve **unsandboxed code execution**, and because the worker runs with
  the **`privileged` flag**, an attacker can "mount the Linux host filesystem" and
  take the host. (<https://nvd.nist.gov/vuln/detail/CVE-2024-28185>,
  <https://github.com/judge0/judge0/security/advisories/GHSA-h9g2-45c8-89cf>)
- **CVE-2024-29021** (CVSS 9.0) — default config (`ALLOW_ENABLE_NETWORK` on, default
  Postgres password) → SSRF → SQL injection into resource-limit fields → unsandboxed
  RCE as root. (<https://github.com/judge0/judge0/security/advisories/GHSA-q7vg-26pg-v5hr>)

Fixed in v1.13.1, but the pattern — privileged worker container + unsafe defaults —
means adopting Judge0 is adopting its threat model. For a single-language
(Python) need we already have the image for, it adds a GPLv3 service and a worse
security floor than a hardened container. **Skip.**

## Self-hosted vs managed — for *our* deployment

Our stack is `docker-compose` with `db` (postgres:16-alpine), `redis` (redis:7-alpine),
and `api` (`stockmassive-api`, which already carries numpy/pandas/matplotlib). The
FastAPI process can shell out to `docker run` (Docker-out-of-Docker via the mounted
socket) or, better, submit jobs to a small sidecar executor.

- **Self-hosted (per-call container / gVisor):** $0 new spend, no new data-egress
  surface (matters — #16/#17 treat egress and injection as first-order risks),
  reuses our image and Python versions, measured ~0.45–0.7 s/call. Cost is
  operational: someone must keep runc/kernel patched and the launch flags correct.
  Mounting the Docker socket into `api` is itself a privilege (`docker.sock` = host
  root per Docker's own warning), so the executor should be a **separate, minimal
  service**, not `api` itself.
- **Managed (e2b/Modal):** offloads the boundary and its CVE response, but adds a
  third-party dependency, sends code (and possibly market data) off-box, needs
  network egress from `api`, and costs per call. For an internal tool with a fixed
  symbol universe and trusted-ish LLM output, that trade is not worth it — **until**
  the audience becomes external.

## Rough cost per 1000 executions (managed options, from published pricing)

Assume a short quant call: ~1 vCPU, ~1 GiB RAM, ~3 s billed wall time (startup +
compute). Prices are per published pages on 2026-08-12; do your own reconciliation
before committing.

| Vendor | Unit price (primary) | Per exec (~1 vCPU·1 GiB·3 s) | Per 1000 | Notes |
|---|---|---|---|---|
| **Modal Sandbox** | CPU $0.00003942/core·s + mem $0.00000667/GiB·s (Sandbox rate) | ~$0.00014 | **~$0.14** | + $0 Starter plan, $30 free credit; min 0.125 core. (<https://modal.com/pricing>) |
| **e2b** | CPU $0.000014/s (1 vCPU) + RAM $0.0000045/GiB·s | ~$0.000055 | **~$0.06** | Hobby free + one-time $100 credit; Pro $150/mo; concurrency caps. (<https://e2b.dev/pricing>) |
| **Cloudflare Containers** (Sandbox SDK) | vCPU $0.000020/s + mem $0.0000025/GiB·s + free monthly allowances | ~$0.000068 | **~$0.07** | needs $5/mo Workers Paid; 375 vCPU-min + 25 GiB-h included/mo. (<https://developers.cloudflare.com/containers/pricing/>) |

These are compute-only floors; real per-1000 cost rises with longer/heavier jobs,
egress, and idle sandbox time (Modal default 300 s lifetime unless you terminate
early). At internal volumes the dollar cost is immaterial — the reason to self-host
is control and egress, not price. At external-user scale, price and the security
team both argue for managed.

## Verdict

- **Should we run LLM-authored Python at all (input to #33)?** Technically yes,
  *only* on an OS-level boundary. The in-process option that would have made it
  trivial is disowned by its own authors and broken in 8 lines — so "yes" is
  conditional on standing up a container/microVM executor, which is real work but
  bounded.
- **Internal `docker-compose` default:** **per-call hardened Docker container using
  the existing `stockmassive-api` image, under the gVisor `runsc` runtime where the
  host allows it**, launched from a *separate minimal executor service* (never by
  giving `api` the docker socket casually). Add scipy/sklearn to the image if the
  tool surface needs them. Latency ~0.45–0.7 s/call, $0 new spend, no new egress.
- **Production / external users:** **managed Firecracker microVM — e2b (default) or
  Modal Sandboxes** — for the hardware boundary and vendor-owned escape response, at
  ~$0.06–0.14 per 1000 short executions plus plan fees.
- **Rejected:** in-process/RestrictedPython (not a boundary), hand-rolled
  nsjail/seccomp (correct but DIY; use it *via* Docker/gVisor), Judge0 (privileged
  worker + escape-CVE history). **Pyodide/WASM** is a strong future option for
  pure-math tool calls but constrained (no threads/sockets/subprocess; pandas loads
  at runtime cost).
