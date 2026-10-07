# rapp-distro — spawn a RAPP distro the way you'd spin a Linux distro

**A RAPP distro is the unmodified [brainstem](https://github.com/kody-w/rapp-installer) kernel, pinned to a
version, plus a userland.** The kernel stays one sacred thing; the variety lives in the distros. This is the
shape that made Linux rule compute — RAPP adopts it deliberately ([the philosophy](https://github.com/kody-w/rapp-spine/blob/main/FOUNDATION.md#2a-the-kerneldistro-model--the-linux-philosophy)).

> Standard: **[SPEC.md](SPEC.md)** (`rapp-distro/1.0`) · Pin format: **[kernel.example.json](kernel.example.json)** · Verifier: **[check_kernel_pin.py](check_kernel_pin.py)**

## Spawn one (permissionless — no registry, no central anything)

```bash
curl -fsSL https://raw.githubusercontent.com/kody-w/rapp-distro/main/spawn-distro.sh | bash -s my-distro
# pin a specific full commit:  ... | bash -s my-distro 0e43ee580e78c150b1c59002456822d2e779388e
```

You get `./my-distro/`: the frozen kernel vendored at the pinned commit, a `kernel.json`, a starter userland
(`soul.md` + a hello agent), and the **freeze CI**. Push it to any GitHub repo and it's a live distro.

## The model (Linux, exactly)

| Linux | RAPP |
|---|---|
| the kernel | the **brainstem** (`rapp-installer` = the grail) |
| syscall ABI — *never break userspace* | the **agent ABI** (`metadata` + `perform`, `/chat`, auto-discovery) |
| modules / userspace | **agents** (`*_agent.py`) |
| a distro (Ubuntu/Fedora/Arch) | the unmodified kernel (pinned) + a **userland** |
| LTS pinning an old kernel | a distro keeps one full 40-hex commit until it deliberately upgrades |

## The one law: the freeze invariant

> A distro's **frozen kernel set** (`brainstem.py` + `agents/basic_agent.py` + `VERSION`) MUST be
> **byte-identical** to the grail at its pinned tag.

`check_kernel_pin.py` (run by `kernel-freeze.yml` on every push) proves the commit, kernel git blob, version,
and every vendored sha256 against the live grail. Match → an unmodified kernel (a true distro). Mismatch →
a **fork** (drift). **Pin, don't fork.** Upgrade by re-vendoring from a new full commit.

Legacy repos fail with one conversion instruction. Run `python3 check_kernel_pin.py --convert` to map the old
`KERNEL_PIN.json` record into `kernel.json`, then verify and commit the new pin.

---

*One kernel, sacred and tiny. A thousand distros, each a curated userland on top.*
