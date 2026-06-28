# rapp-distro — spawn a RAPP distro the way you'd spin a Linux distro

**A RAPP distro is the unmodified [brainstem](https://github.com/kody-w/rapp-installer) kernel, pinned to a
version, plus a userland.** The kernel stays one sacred thing; the variety lives in the distros. This is the
shape that made Linux rule compute — RAPP adopts it deliberately ([the philosophy](https://github.com/kody-w/rapp-spine/blob/main/FOUNDATION.md#2a-the-kerneldistro-model--the-linux-philosophy)).

> Standard: **[SPEC.md](SPEC.md)** (`rapp-distro/1.0`) · Pin format: **[KERNEL_PIN.example.json](KERNEL_PIN.example.json)** · Verifier: **[check_kernel_pin.py](check_kernel_pin.py)**

## Spawn one (permissionless — no registry, no central anything)

```bash
curl -fsSL https://raw.githubusercontent.com/kody-w/rapp-distro/main/spawn-distro.sh | bash -s my-distro
# pin a specific kernel:  ... | bash -s my-distro v0.6.0
```

You get `./my-distro/`: the frozen kernel vendored at the pinned tag, a `KERNEL_PIN.json`, a starter userland
(`soul.md` + a hello agent), and the **freeze CI**. Push it to any GitHub repo and it's a live distro.

## The model (Linux, exactly)

| Linux | RAPP |
|---|---|
| the kernel | the **brainstem** (`rapp-installer` = the grail) |
| syscall ABI — *never break userspace* | the **agent ABI** (`metadata` + `perform`, `/chat`, auto-discovery) |
| modules / userspace | **agents** (`*_agent.py`) |
| a distro (Ubuntu/Fedora/Arch) | the unmodified kernel (pinned) + a **userland** |
| LTS pinning an old kernel | the reference distro [`kody-w/RAPP`](https://github.com/kody-w/RAPP) pins `v0.6.0` |

## The one law: the freeze invariant

> A distro's **frozen kernel set** (`brainstem.py` + `agents/basic_agent.py` + `VERSION`) MUST be
> **byte-identical** to the grail at its pinned tag.

`check_kernel_pin.py` (run by `kernel-freeze.yml` on every push) proves it: it re-derives the hashes from the
grail tag and from your repo. Match → an unmodified kernel (a true distro). Mismatch → a **fork** (drift).
**Pin, don't fork.** Bump the kernel by changing `kernel.tag`; the frozen ABI means every agent keeps working.

---

*One kernel, sacred and tiny. A thousand distros, each a curated userland on top.*
