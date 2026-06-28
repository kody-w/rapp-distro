# rapp-distro/1.0 — the RAPP distro standard

> **A RAPP distro is to the brainstem what Ubuntu is to Linux:** the *unmodified kernel*, pinned to a
> version, plus a *userland*. This spec makes "spawn a distro" a precise, permissionless act — so the
> kernel stays one sacred thing and the variety lives in the distros, exactly the shape that made Linux
> rule compute.

## 1. Definitions

- **The kernel (the grail).** The single-file brainstem — [`kody-w/rapp-installer`](https://github.com/kody-w/rapp-installer), spec `rapp-agent/1.0`. It is `rapp_brainstem/brainstem.py` + `rapp_brainstem/agents/basic_agent.py` + `rapp_brainstem/VERSION`. It is **sacred, minimal, and changed only in the grail**, version-bumped and tagged immutably.
- **The frozen ABI (never break userspace).** The kernel's contract to agents: a class extending `BasicAgent` with a `metadata` dict (OpenAI function schema) and `perform(**kwargs) -> str`, auto-discovered from `agents/**/*_agent.py`, invoked over `POST /chat`. An agent written for any kernel version runs on every later kernel, forever.
- **A distro.** The unmodified kernel (pinned to a grail tag) + a **userland**: `soul.md`, `agents/`, `index.html`/branding, bundled specs, docs — everything that is *not* the frozen kernel. [`kody-w/RAPP`](https://github.com/kody-w/RAPP) is the **reference distro** (pins kernel `v0.6.0`).
- **The userspace = agents.** Drop-in `*_agent.py` files are the only unit of extension — the distro's "packages." Never a kernel edit.

## 2. The frozen kernel set

Exactly these files must be **byte-identical** to the pinned grail tag. Everything else is userland.

```
rapp_brainstem/brainstem.py
rapp_brainstem/agents/basic_agent.py
rapp_brainstem/VERSION
```

`soul.md`, `index.html`, `agents/*` (beyond `basic_agent.py`), and all docs/specs are **userland** — a
distro owns them. (This matches the kernel's own rule: *only `soul.md` may change*, and agents are the
extension.)

## 3. `KERNEL_PIN.json` — the pin (every distro has exactly one)

```json
{
  "spec": "rapp-distro/1.0",
  "distro": "my-distro",
  "kernel": {
    "grail": "kody-w/rapp-installer",
    "tag": "v0.6.0",
    "frozen": {
      "rapp_brainstem/brainstem.py":            "<sha256>",
      "rapp_brainstem/agents/basic_agent.py":   "<sha256>",
      "rapp_brainstem/VERSION":                 "<sha256>"
    }
  },
  "channel": "lts"
}
```

- **`kernel.tag`** — the immutable grail tag this distro pins (e.g. `v0.6.0`). Like a Linux distro pinning an upstream kernel release.
- **`kernel.frozen`** — the sha256 of each frozen file *at that tag*. The pin cannot lie: CI re-derives them from the grail tag.
- **`channel`** — `lts` (pin a fixed tag; bump deliberately) or `rolling` (CI bumps the pin to the grail's newest tag automatically). Distro's choice, exactly like Linux.

## 4. The freeze invariant (the one law)

> **A distro's frozen kernel set MUST be byte-identical to the grail at its pinned tag.**

CI proves it on every push/PR (`check_kernel_pin.py`):

```
for f in kernel.frozen:
    assert sha256(distro/f)            == kernel.frozen[f]      # the distro ships what it pinned
    assert sha256(grail @ tag / f)     == kernel.frozen[f]      # the pin is honest to the grail
```

Pass → the distro ships an **unmodified** kernel (a true distro). Fail → it **modified** the kernel (a
**fork**, which is drift). Pin, don't fork. `rapp-god` watches the same hashes ecosystem-wide.

## 5. Spawning a distro (permissionless)

```bash
curl -fsSL https://raw.githubusercontent.com/kody-w/rapp-distro/main/spawn-distro.sh | bash -s my-distro
# or pin a specific kernel:  ... | bash -s my-distro v0.6.0
```

This scaffolds `./my-distro/`: the frozen kernel vendored at the chosen tag, a `KERNEL_PIN.json`, a starter
userland (`soul.md` + a hello agent), and the freeze CI. Push it to any GitHub repo and it's a live distro —
no permission, no registry, no central anything. **That is the adoption flywheel.**

## 6. Bumping the kernel

To adopt a newer kernel: change `kernel.tag` to the new grail tag and re-derive `kernel.frozen` (re-vendor
the frozen files). The frozen ABI guarantees every existing agent keeps working — *the kernel never breaks
userspace*. `rolling` distros do this automatically.

## 7. How it composes

- The kernel/distro split is the foundation's [Linux philosophy](https://github.com/kody-w/rapp-spine/blob/main/FOUNDATION.md) (§2a). The kernel is `rapp-agent/1.0`; distros are how the estate gets variety without forking the atom.
- A distro's userland is the rest of the estate: agents from `RAR`/`RAPP_Store`/`RAPP_Sense_Store`, eggs (`rapp-egg/2.0` `scale` field), neighborhoods, the tiers. A distro is a *curated userland over a pinned kernel*.
- Trust is the canonical model: GitHub-collaborator + `sha256` content-addressing. No new identity layer — the pin's hashes are content addresses; the grail tag is immutable.

---

*One kernel, sacred and tiny. A thousand distros, each a curated userland on top. Pin, don't fork.*
