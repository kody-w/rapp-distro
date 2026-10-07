#!/usr/bin/env bash
# Scaffold an unmodified pinned kernel plus a userland.
#
#   bash spawn-distro.sh <distro-path> [kernel-ref]
#   curl -fsSL https://raw.githubusercontent.com/kody-w/rapp-distro/main/spawn-distro.sh | bash -s my-distro
set -euo pipefail

DEST="${1:?usage: spawn-distro.sh <distro-path> [kernel-ref]}"
NAME="$(basename "$DEST")"
GRAIL="kody-w/rapp-installer"
DISTRO_REPO="kody-w/rapp-distro"
REF="${2:-main}"
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd || true)"

SHA="$(python3 - "$GRAIL" "$REF" <<'PY'
import json
import sys
import urllib.parse
import urllib.request

repo, ref = sys.argv[1:3]
url = f"https://api.github.com/repos/{repo}/commits/{urllib.parse.quote(ref, safe='')}"
request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "rapp-distro-spawn"})
with urllib.request.urlopen(request, timeout=60) as response:
    value = json.load(response)["sha"]
if len(value) != 40:
    raise SystemExit(f"{repo}@{ref} did not resolve to a commit")
print(value)
PY
)"
echo "spawning distro '$NAME' on kernel $GRAIL@$SHA"

mkdir -p "$DEST/rapp_brainstem/agents" "$DEST/.github/workflows"
cd "$DEST"

for f in rapp_brainstem/brainstem.py rapp_brainstem/agents/basic_agent.py rapp_brainstem/VERSION; do
  curl -fsSL "https://raw.githubusercontent.com/$GRAIL/$SHA/$f" -o "$f"
done

python3 - "$GRAIL" "$SHA" <<'PY'
import datetime
import hashlib
import json
import sys

grail, commit = sys.argv[1:3]
kernel_path = "rapp_brainstem/brainstem.py"
vendored_paths = [
    kernel_path,
    "rapp_brainstem/agents/basic_agent.py",
    "rapp_brainstem/VERSION",
]
kernel = open(kernel_path, "rb").read()
pin = {
    "kernel": grail,
    "sha": commit,
    "version": open("rapp_brainstem/VERSION", encoding="utf-8").read().strip(),
    "path": kernel_path,
    "kernel_blob": hashlib.sha1(f"blob {len(kernel)}\0".encode() + kernel).hexdigest(),
    "pinned": datetime.date.today().isoformat(),
    "vendored": {
        path: hashlib.sha256(open(path, "rb").read()).hexdigest()
        for path in vendored_paths
    },
}
with open("kernel.json", "w", encoding="utf-8") as handle:
    json.dump(pin, handle, indent=2)
    handle.write("\n")
PY

# starter USERLAND (yours to edit — this is the distro)
cat > soul.md <<EOF
You are $NAME, a RAPP distro running an unmodified kernel pinned at $SHA.
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

# Use the checkout's files for local spawning; piped installs fetch the published standard.
if [ -n "$SOURCE_DIR" ] && [ -f "$SOURCE_DIR/check_kernel_pin.py" ]; then
  cp "$SOURCE_DIR/check_kernel_pin.py" check_kernel_pin.py
  cp "$SOURCE_DIR/.github/workflows/kernel-freeze.yml" .github/workflows/kernel-freeze.yml
else
  curl -fsSL "https://raw.githubusercontent.com/$DISTRO_REPO/main/check_kernel_pin.py" -o check_kernel_pin.py
  curl -fsSL "https://raw.githubusercontent.com/$DISTRO_REPO/main/.github/workflows/kernel-freeze.yml" -o .github/workflows/kernel-freeze.yml
fi

cat > README.md <<EOF
# $NAME — a RAPP distro

Pinned to kernel \`$GRAIL@$SHA\`, **unmodified** (verified by the \`kernel-freeze\` CI).
Userland: \`soul.md\` (persona) + \`rapp_brainstem/agents/\` (your agents). Spec:
[rapp-distro/1.0](https://github.com/$DISTRO_REPO). Pin, don't fork.

Run it with the kernel's own start path. To upgrade, re-vendor from a new full commit and update \`kernel.json\`.
EOF

echo ""
echo "distro '$NAME' scaffolded (kernel $SHA, freeze CI installed)."
echo "   next:  cd $NAME && git init && gh repo create $NAME --public --source=. --push"
