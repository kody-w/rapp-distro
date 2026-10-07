# rapp-distro/1.0 — the RAPP distro standard

> **A RAPP distro is to the brainstem what Ubuntu is to Linux:** the unmodified kernel, pinned to one
> immutable commit, plus a userland.

## 1. Definitions

- **The kernel (the grail).** [`kody-w/rapp-installer`](https://github.com/kody-w/rapp-installer).
- **The frozen ABI.** The kernel contract to agents: `metadata`, `perform(**kwargs)`, auto-discovery, and
  `POST /chat`.
- **A distro.** The unmodified kernel at one full commit plus everything the distro owns around it.
- **Userspace.** Soul, agents, sidecars, branding, docs, and other files outside the pinned grail copies.

## 2. The one pin: `kernel.json`

Every distro uses exactly this shape:

```json
{
  "kernel": "kody-w/rapp-installer",
  "sha": "0e43ee580e78c150b1c59002456822d2e779388e",
  "version": "0.6.16",
  "path": "rapp_brainstem/brainstem.py",
  "kernel_blob": "3f7102ff508c813bb6494511fc32a421a633e418",
  "pinned": "2026-10-07"
}
```

Required keys:

- `kernel`: the grail repository as `owner/repository`.
- `sha`: the full 40-hex commit. Never store a tag or branch; those names can move.
- `version`: the exact contents of `rapp_brainstem/VERSION` at `sha`.
- `path`: the grail path to the kernel entry point.
- `kernel_blob`: `git rev-parse <sha>:<path>`, the git blob identity used by hubs.

Optional keys:

- `pinned`: the pin date.
- `ui_path` with `ui_blob`, and `soul_path` with `soul_blob`.
- `contract` and `rule`.
- `vendored`: an object mapping each copied grail path to its sha256 at `sha`.

No other keys are allowed. A distro that copies grail files lists every copy in `vendored`, at the same
repository-relative path, and each local copy must be byte-identical to the grail.

## 3. The freeze invariant

`check_kernel_pin.py` proves, against the live grail:

1. all required keys exist and no unsupported keys do;
2. `sha` resolves to the exact commit named;
3. the git blob for `path` equals `kernel_blob`;
4. the grail `VERSION` at `sha` equals `version`;
5. optional UI and soul blob pairs are honest; and
6. every `vendored` sha256 matches both the grail bytes and the distro copy.

Pass means the distro stands on an unmodified kernel. Fail means the pin is dishonest, stale, or the distro
has forked a vendored kernel file.

## 4. Spawning a distro

```bash
curl -fsSL https://raw.githubusercontent.com/kody-w/rapp-distro/main/spawn-distro.sh | bash -s my-distro
# or resolve and pin a release version once:
curl -fsSL https://raw.githubusercontent.com/kody-w/rapp-distro/main/spawn-distro.sh |
  bash -s my-distro v0.6.15
```

For a supplied version `V`, the spawner tries the grail tags `V`, `v${V#v}`,
`brainstem-${V#v}`, and `brainstem-v${V#v}` in that order. It pins the resolved full commit, reads
`version` from the grail `VERSION` file at that commit, vendors the frozen kernel set, writes only
`kernel.json`, and installs the checker and CI workflow. With no version, it pins the current `main`
commit.

## 5. Upgrading

Resolve the intended grail revision to a full commit, re-vendor every copied grail file, then update
`sha`, `version`, `kernel_blob`, and every `vendored` hash together. Run the checker before committing.

## 6. Legacy conversion

If only the former uppercase pin exists, the checker fails with the exact conversion command:

```bash
python3 check_kernel_pin.py --convert
```

The converter resolves the legacy tag to a full commit, recomputes the canonical fields from the grail,
maps the old frozen file set into `vendored`, and writes `kernel.json`. It never overwrites an existing
canonical pin.

---

*One kernel, sacred and tiny. A thousand distros, each a curated userland on top. Pin, don't fork.*
