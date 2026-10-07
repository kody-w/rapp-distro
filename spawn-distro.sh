#!/usr/bin/env bash
# Scaffold an unmodified pinned kernel plus a userland.
#
#   bash spawn-distro.sh <distro-path> [kernel-version]
#   curl -fsSL https://raw.githubusercontent.com/kody-w/rapp-distro/main/spawn-distro.sh | bash -s my-distro
set -euo pipefail

DEST="${1:?usage: spawn-distro.sh <distro-path> [kernel-version]}"
NAME="$(basename "$DEST")"
GRAIL="kody-w/rapp-installer"
DISTRO_REPO="kody-w/rapp-distro"
VERSION="${2:-}"
GITHUB_API_BASE="${RAPP_GITHUB_API_BASE:-https://api.github.com}"
SCRIPT_SOURCE="${BASH_SOURCE[0]:-}"
SOURCE_DIR=""
if [ -n "$SCRIPT_SOURCE" ] && [ -f "$SCRIPT_SOURCE" ]; then
  SOURCE_DIR="$(cd "$(dirname "$SCRIPT_SOURCE")" && pwd)"
fi

SHA="$(python3 - "$GRAIL" "$VERSION" "$GITHUB_API_BASE" <<'PY'
import json
import re
import sys
import urllib.parse
import urllib.request

repo, version, api_base = sys.argv[1:4]
base = f"{api_base.rstrip('/')}/repos/{repo}"
headers = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "rapp-distro-spawn",
}


def read_json(url):
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def fail(message):
    print(message, file=sys.stderr)
    raise SystemExit(1)


try:
    if not version:
        value = read_json(f"{base}/commits/main").get("sha")
    else:
        tags = []
        page = 1
        while True:
            batch = read_json(f"{base}/tags?per_page=100&page={page}")
            if not isinstance(batch, list):
                fail("could not read grail tags")
            tags.extend(batch)
            if len(batch) < 100:
                break
            page += 1

        by_name = {}
        for item in tags:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            commit = item.get("commit")
            if isinstance(name, str) and isinstance(commit, dict):
                sha = commit.get("sha")
                if isinstance(sha, str):
                    by_name[name] = sha
        stripped = version[1:] if version.startswith("v") else version
        candidates = (
            version,
            f"v{stripped}",
            f"brainstem-{stripped}",
            f"brainstem-v{stripped}",
        )
        value = next(
            (by_name[candidate] for candidate in dict.fromkeys(candidates) if candidate in by_name),
            None,
        )
        if value is None:
            available = [
                name for name in by_name
                if isinstance(name, str) and name.startswith("brainstem-v")
            ]

            def version_key(name):
                match = re.fullmatch(r"brainstem-v(\d+(?:\.\d+)*)", name)
                if match:
                    return (0, tuple(int(part) for part in match.group(1).split(".")), "")
                return (1, (), name)

            listed = ", ".join(sorted(available, key=version_key))
            fail(f"version {version} not found; available brainstem versions: {listed}")
except (OSError, TypeError, ValueError, json.JSONDecodeError) as error:
    fail(f"could not resolve grail version: {error}")

if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{40}", value) is None:
    fail("grail version did not resolve to a commit")
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
if [ -n "$SOURCE_DIR" ] \
   && [ -f "$SOURCE_DIR/check_kernel_pin.py" ] \
   && [ -f "$SOURCE_DIR/.github/workflows/kernel-freeze.yml" ]; then
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
