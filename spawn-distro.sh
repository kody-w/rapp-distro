#!/usr/bin/env bash
# spawn-distro.sh — scaffold a RAPP distro (rapp-distro/1.0): an unmodified pinned kernel + a userland.
# This is the "remaster a Linux ISO" button. Permissionless: no registry, no central anything.
#
#   bash spawn-distro.sh <distro-name> [kernel-tag]
#   curl -fsSL https://raw.githubusercontent.com/kody-w/rapp-distro/main/spawn-distro.sh | bash -s my-distro
set -euo pipefail

NAME="${1:?usage: spawn-distro.sh <distro-name> [kernel-tag]}"
GRAIL="kody-w/rapp-installer"
DISTRO_REPO="kody-w/rapp-distro"

# resolve the kernel tag: arg, else the grail's latest vX.Y.Z tag
TAG="${2:-}"
if [ -z "$TAG" ]; then
  TAG=$(curl -fsSL "https://api.github.com/repos/$GRAIL/tags" \
        | grep -oE '"name": *"v[0-9]+\.[0-9]+\.[0-9]+"' | grep -oE 'v[0-9]+\.[0-9]+\.[0-9]+' | head -1)
fi
[ -n "$TAG" ] || { echo "could not resolve a grail kernel tag"; exit 1; }
echo "🌱 spawning distro '$NAME' on kernel $GRAIL@$TAG"

mkdir -p "$NAME/rapp_brainstem/agents" "$NAME/.github/workflows"
cd "$NAME"

# vendor the FROZEN kernel set at the tag — unmodified
for f in rapp_brainstem/brainstem.py rapp_brainstem/agents/basic_agent.py rapp_brainstem/VERSION; do
  curl -fsSL "https://raw.githubusercontent.com/$GRAIL/$TAG/$f" -o "$f"
done

# write KERNEL_PIN.json with the real frozen hashes
python3 - "$NAME" "$GRAIL" "$TAG" <<'PY'
import sys, json, hashlib
name, grail, tag = sys.argv[1:4]
frozen = {f: hashlib.sha256(open(f, "rb").read()).hexdigest()
          for f in ["rapp_brainstem/brainstem.py", "rapp_brainstem/agents/basic_agent.py", "rapp_brainstem/VERSION"]}
json.dump({"spec": "rapp-distro/1.0", "distro": name,
           "kernel": {"grail": grail, "tag": tag, "frozen": frozen}, "channel": "lts"},
          open("KERNEL_PIN.json", "w"), indent=2)
PY

# starter USERLAND (yours to edit — this is the distro)
cat > soul.md <<EOF
You are $NAME, a RAPP distro running an unmodified kernel pinned at $TAG.
Edit me — soul.md is your distro's persona. Add agents under rapp_brainstem/agents/.
EOF

cat > rapp_brainstem/agents/hello_agent.py <<'EOF'
from agents.basic_agent import BasicAgent


class HelloAgent(BasicAgent):
    def __init__(self):
        self.name = "Hello"
        self.metadata = {"name": self.name, "description": "Say hello from this distro.",
                         "parameters": {"type": "object", "properties": {}}}
        super().__init__(name=self.name, metadata=self.metadata)

    def perform(self, **kwargs):
        return "hello from this distro — userland agent, unmodified kernel"
EOF

# drop in the freeze CI + checker so "unmodified kernel" is PROVEN, not promised
curl -fsSL "https://raw.githubusercontent.com/$DISTRO_REPO/main/check_kernel_pin.py" -o check_kernel_pin.py
curl -fsSL "https://raw.githubusercontent.com/$DISTRO_REPO/main/.github/workflows/kernel-freeze.yml" -o .github/workflows/kernel-freeze.yml

cat > README.md <<EOF
# $NAME — a RAPP distro

Pinned to kernel \`$GRAIL@$TAG\`, **unmodified** (verified by the \`kernel-freeze\` CI).
Userland: \`soul.md\` (persona) + \`rapp_brainstem/agents/\` (your agents). Spec:
[rapp-distro/1.0](https://github.com/$DISTRO_REPO). Pin, don't fork.

Run it with the kernel's own start path; bump the kernel by changing \`kernel.tag\` in \`KERNEL_PIN.json\`.
EOF

echo ""
echo "✅ distro '$NAME' scaffolded (kernel $TAG, freeze CI installed)."
echo "   next:  cd $NAME && git init && gh repo create $NAME --public --source=. --push"
