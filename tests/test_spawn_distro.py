#!/usr/bin/env python3
"""Network regression checks for the documented distro spawn path."""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = pathlib.Path(os.environ.get("SPAWN_DISTRO_SCRIPT", ROOT / "spawn-distro.sh"))
EXPECTED_SHA = "e08d33c712bcee4ddac19a0d26d5ac6b530995ef"
RAW_MAIN = "https://raw.githubusercontent.com/kody-w/rapp-distro/main"


def run_spawn(work, destination, version=None, stdin=False, env=None):
    command = ("bash", "-s", destination) if stdin else ("bash", os.fspath(SCRIPT), destination)
    if version is not None:
        command += (version,)
    return subprocess.run(
        command,
        cwd=work,
        input=SCRIPT.read_text(encoding="utf-8") if stdin else None,
        text=True,
        capture_output=True,
        check=False,
        timeout=180,
        env={**os.environ, **(env or {})},
    )


def check_spawn(distro):
    return subprocess.run(
        (sys.executable, "check_kernel_pin.py"),
        cwd=distro,
        text=True,
        capture_output=True,
        check=False,
        timeout=180,
    )


class SpawnDistroTests(unittest.TestCase):
    def test_spawner_publishes_only_the_canonical_pin_and_main_assets(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("KERNEL_PIN", source)
        self.assertIn(
            "https://raw.githubusercontent.com/$DISTRO_REPO/main/check_kernel_pin.py",
            source,
        )
        self.assertIn(
            "https://raw.githubusercontent.com/$DISTRO_REPO/main/.github/workflows/kernel-freeze.yml",
            source,
        )

    def test_documented_version_resolves_to_commit_and_checks(self):
        with tempfile.TemporaryDirectory(prefix="rapp-distro-version-") as temporary:
            work = pathlib.Path(temporary)
            completed = run_spawn(work, "old-distro", "v0.6.15")
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            distro = work / "old-distro"
            pin = json.loads((distro / "kernel.json").read_text(encoding="utf-8"))
            self.assertEqual(pin["sha"], EXPECTED_SHA)
            self.assertEqual(pin["version"], "0.6.15")
            self.assertFalse((distro / "KERNEL_PIN.json").exists())
            check = check_spawn(distro)
            self.assertEqual(check.returncode, 0, check.stdout + check.stderr)

    def test_no_version_pins_the_live_main_commit(self):
        with tempfile.TemporaryDirectory(prefix="rapp-distro-main-") as temporary:
            work = pathlib.Path(temporary)
            completed = run_spawn(work, "main-distro")
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            distro = work / "main-distro"
            pin = json.loads((distro / "kernel.json").read_text(encoding="utf-8"))
            request = urllib.request.Request(
                "https://api.github.com/repos/kody-w/rapp-installer/commits/main",
                headers={"Accept": "application/vnd.github+json", "User-Agent": "rapp-distro-test"},
            )
            with urllib.request.urlopen(request, timeout=60) as response:
                expected = json.load(response)["sha"]
            self.assertEqual(pin["sha"], expected)
            self.assertFalse((distro / "KERNEL_PIN.json").exists())
            check = check_spawn(distro)
            self.assertEqual(check.returncode, 0, check.stdout + check.stderr)

    def test_unknown_version_is_one_plain_line_and_writes_nothing(self):
        with tempfile.TemporaryDirectory(prefix="rapp-distro-missing-") as temporary:
            work = pathlib.Path(temporary)
            completed = run_spawn(work, "missing-distro", "v9.9.9")
            lines = (completed.stdout + completed.stderr).splitlines()
            self.assertEqual(completed.returncode, 1)
            self.assertEqual(len(lines), 1, lines)
            self.assertRegex(
                lines[0],
                r"^version v9\.9\.9 not found; available brainstem versions: "
                r"brainstem-v[0-9]",
            )
            self.assertNotIn("Traceback", lines[0])
            self.assertFalse((work / "missing-distro").exists())

    def test_stdin_unknown_version_is_still_exactly_one_line(self):
        with tempfile.TemporaryDirectory(prefix="rapp-distro-stdin-missing-") as temporary:
            work = pathlib.Path(temporary)
            completed = run_spawn(work, "missing-distro", "v9.9.9", stdin=True)
            lines = (completed.stdout + completed.stderr).splitlines()
            self.assertEqual(completed.returncode, 1)
            self.assertEqual(len(lines), 1, lines)
            self.assertNotIn("BASH_SOURCE", lines[0])
            self.assertNotIn("unbound variable", lines[0])
            self.assertFalse((work / "missing-distro").exists())

    def test_stdin_execution_ignores_checker_files_in_the_callers_cwd(self):
        with tempfile.TemporaryDirectory(prefix="rapp-distro-stdin-") as temporary:
            work = pathlib.Path(temporary)
            poison = b"caller-local checker must not be copied\n"
            (work / "check_kernel_pin.py").write_bytes(poison)
            workflow = work / ".github" / "workflows" / "kernel-freeze.yml"
            workflow.parent.mkdir(parents=True)
            workflow.write_bytes(b"caller-local workflow must not be copied\n")

            completed = run_spawn(work, "piped-distro", "v0.6.15", stdin=True)
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            distro = work / "piped-distro"
            with urllib.request.urlopen(f"{RAW_MAIN}/check_kernel_pin.py", timeout=60) as response:
                expected_checker = response.read()
            with urllib.request.urlopen(
                f"{RAW_MAIN}/.github/workflows/kernel-freeze.yml", timeout=60
            ) as response:
                expected_workflow = response.read()
            self.assertEqual((distro / "check_kernel_pin.py").read_bytes(), expected_checker)
            self.assertEqual(
                (distro / ".github/workflows/kernel-freeze.yml").read_bytes(),
                expected_workflow,
            )
            self.assertNotEqual((distro / "check_kernel_pin.py").read_bytes(), poison)
            self.assertFalse((distro / "KERNEL_PIN.json").exists())

    def test_prerelease_tags_do_not_break_the_available_version_line(self):
        class Tags(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_GET(self):
                if not self.path.startswith("/repos/kody-w/rapp-installer/tags?"):
                    self.send_error(404)
                    return
                body = json.dumps([
                    {
                        "name": "brainstem-v0.6.15",
                        "commit": {"sha": EXPECTED_SHA},
                    },
                    {
                        "name": "brainstem-v0.7.0-rc1",
                        "commit": {"sha": "f" * 40},
                    },
                ]).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Tags)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory(prefix="rapp-distro-prerelease-") as temporary:
                work = pathlib.Path(temporary)
                completed = run_spawn(
                    work,
                    "missing-distro",
                    "v9.9.9",
                    env={"RAPP_GITHUB_API_BASE": f"http://127.0.0.1:{server.server_port}"},
                )
                lines = (completed.stdout + completed.stderr).splitlines()
                self.assertEqual(completed.returncode, 1)
                self.assertEqual(len(lines), 1, lines)
                self.assertEqual(
                    lines[0],
                    "version v9.9.9 not found; available brainstem versions: "
                    "brainstem-v0.6.15, brainstem-v0.7.0-rc1",
                )
                self.assertNotIn("Traceback", lines[0])
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
