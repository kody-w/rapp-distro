#!/usr/bin/env python3
"""check_kernel_pin.py — enforce the rapp-distro/1.0 freeze invariant.

A distro's frozen kernel set MUST be byte-identical to the grail at its pinned tag.
Run in CI on every push/PR. Exit 0 = unmodified kernel (a true distro); exit 1 = the
kernel was modified (a FORK = drift). Stdlib only.
"""
import hashlib
import json
import os
import sys
import urllib.request


def sha(b):
    return hashlib.sha256(b).hexdigest()


def get(url):
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            return r.read()
    except Exception:
        return None


def pin_path():
    # A spawned distro has KERNEL_PIN.json. The standard repo itself ships only the reference pin,
    # KERNEL_PIN.example.json, so its own kernel-freeze CI verifies that pin is honest to the grail.
    if os.path.exists("KERNEL_PIN.json") or not os.path.exists("KERNEL_PIN.example.json"):
        return "KERNEL_PIN.json"
    return "KERNEL_PIN.example.json"


def main():
    path = pin_path()
    if not os.path.exists(path):
        print("KERNEL_PIN.json not found: every distro has exactly one pin (see SPEC.md section 3)")
        return 1
    if path != "KERNEL_PIN.json":
        print(f"no KERNEL_PIN.json here: verifying the reference pin {path}\n")
    pin = json.load(open(path))
    if pin.get("spec") != "rapp-distro/1.0":
        print(f"{path}: not a rapp-distro/1.0 pin")
        return 1
    k = pin["kernel"]
    grail, tag, frozen = k["grail"], k["tag"], k["frozen"]
    print(f"distro '{pin.get('distro')}' pins kernel {grail}@{tag} (channel: {pin.get('channel', 'lts')})\n")
    ok = True
    for f, want in frozen.items():
        # (2) the pin is honest to the grail tag — ALWAYS required
        g = get(f"https://raw.githubusercontent.com/{grail}/{tag}/{f}")
        gs = sha(g) if g is not None else "UNREACHABLE"
        # (1) if the distro VENDORS the kernel, the vendored copy must match — else pin-and-pull (skip)
        local = open(f, "rb").read() if os.path.exists(f) else None
        ls = sha(local) if local is not None else "not-vendored"
        good = (gs == want) and (local is None or ls == want)
        ok = ok and good
        print(f"  {'OK  ' if good else 'FAIL'} {f}")
        print(f"        pinned={want[:16]}  grail@{tag}={gs[:16] if gs != 'UNREACHABLE' else gs}  distro={ls[:16] if local is not None else ls}")
    print("\n✅ unmodified kernel — a true rapp-distro/1.0" if ok
          else "\n❌ kernel MODIFIED or pin dishonest — this is a FORK, not a distro (pin, don't fork)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
