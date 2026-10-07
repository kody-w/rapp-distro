#!/usr/bin/env python3
"""Verify the canonical kernel.json pin against the live grail. Stdlib only."""

import argparse
import datetime
import hashlib
import json
import os
import pathlib
import re
import sys
import urllib.error
import urllib.parse
import urllib.request


REQUIRED_KEYS = {"kernel", "sha", "version", "path", "kernel_blob"}
OPTIONAL_KEYS = {
    "pinned",
    "ui_path",
    "ui_blob",
    "soul_path",
    "soul_blob",
    "contract",
    "rule",
    "vendored",
}
HEX40 = re.compile(r"[0-9a-f]{40}")
HEX64 = re.compile(r"[0-9a-f]{64}")
REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")


class PinError(Exception):
    pass


def request_bytes(url):
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "rapp-distro-pin-checker"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.read()
    except (OSError, urllib.error.HTTPError) as exc:
        raise PinError(f"cannot read {url}: {exc}") from exc


def request_json(url):
    try:
        return json.loads(request_bytes(url))
    except json.JSONDecodeError as exc:
        raise PinError(f"invalid JSON from {url}: {exc}") from exc


def raw(kernel, sha, path):
    quoted = urllib.parse.quote(path, safe="/")
    return request_bytes(f"https://raw.githubusercontent.com/{kernel}/{sha}/{quoted}")


def git_blob(data):
    header = f"blob {len(data)}\0".encode()
    return hashlib.sha1(header + data).hexdigest()


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def safe_repo_path(value, field):
    if not isinstance(value, str) or not value or value.startswith("/"):
        raise PinError(f"{field} must be a relative repository path")
    parts = pathlib.PurePosixPath(value).parts
    if ".." in parts or "." in parts:
        raise PinError(f"{field} must not contain '.' or '..'")
    return value


def resolve_commit(kernel, ref):
    quoted = urllib.parse.quote(ref, safe="")
    data = request_json(f"https://api.github.com/repos/{kernel}/commits/{quoted}")
    sha = data.get("sha")
    if not isinstance(sha, str) or not HEX40.fullmatch(sha):
        raise PinError(f"{kernel}@{ref} did not resolve to a commit")
    return sha


def choose_pin_path():
    if os.path.isfile("kernel.json"):
        return "kernel.json"
    if os.path.isfile("KERNEL_PIN.json"):
        print("KERNEL_PIN.json is legacy; run: python3 check_kernel_pin.py --convert")
        return None
    if os.path.isfile("kernel.example.json"):
        print("kernel.json not found; verifying kernel.example.json")
        return "kernel.example.json"
    raise PinError("kernel.json not found")


def load_pin(path):
    try:
        with open(path, encoding="utf-8") as handle:
            pin = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise PinError(f"{path}: cannot load pin: {exc}") from exc
    if not isinstance(pin, dict):
        raise PinError(f"{path}: pin must be a JSON object")
    return pin


def check_blob_pair(pin, path_key, blob_key):
    has_path = path_key in pin
    has_blob = blob_key in pin
    if has_path != has_blob:
        raise PinError(f"{path_key} and {blob_key} must be present together")
    if not has_path:
        return None
    path = safe_repo_path(pin[path_key], path_key)
    expected = pin[blob_key]
    if not isinstance(expected, str) or not HEX40.fullmatch(expected):
        raise PinError(f"{blob_key} must be a 40-hex git blob")
    actual = git_blob(raw(pin["kernel"], pin["sha"], path))
    if actual != expected:
        raise PinError(f"{blob_key} mismatch for {path}: expected {expected}, got {actual}")
    return path


def verify(path):
    pin = load_pin(path)
    keys = set(pin)
    missing = sorted(REQUIRED_KEYS - keys)
    extra = sorted(keys - REQUIRED_KEYS - OPTIONAL_KEYS)
    if missing:
        raise PinError(f"{path}: missing required keys: {', '.join(missing)}")
    if extra:
        raise PinError(f"{path}: unsupported keys: {', '.join(extra)}")

    kernel = pin["kernel"]
    commit = pin["sha"]
    version = pin["version"]
    kernel_path = safe_repo_path(pin["path"], "path")
    kernel_blob = pin["kernel_blob"]
    if not isinstance(kernel, str) or not REPOSITORY.fullmatch(kernel):
        raise PinError("kernel must be an owner/repository name")
    if not isinstance(commit, str) or not HEX40.fullmatch(commit):
        raise PinError("sha must be a 40-hex commit")
    if not isinstance(version, str) or not version:
        raise PinError("version must be a non-empty string")
    if not isinstance(kernel_blob, str) or not HEX40.fullmatch(kernel_blob):
        raise PinError("kernel_blob must be a 40-hex git blob")

    resolved = resolve_commit(kernel, commit)
    if resolved != commit:
        raise PinError(f"sha resolved to a different commit: {resolved}")
    kernel_bytes = raw(kernel, commit, kernel_path)
    actual_kernel_blob = git_blob(kernel_bytes)
    if actual_kernel_blob != kernel_blob:
        raise PinError(
            f"kernel_blob mismatch for {kernel_path}: expected {kernel_blob}, got {actual_kernel_blob}"
        )

    version_path = str(pathlib.PurePosixPath(kernel_path).parent / "VERSION")
    actual_version = raw(kernel, commit, version_path).decode("utf-8").strip()
    if actual_version != version:
        raise PinError(f"version mismatch: expected {version}, got {actual_version}")

    checked_pairs = [
        value
        for value in (
            check_blob_pair(pin, "ui_path", "ui_blob"),
            check_blob_pair(pin, "soul_path", "soul_blob"),
        )
        if value
    ]

    vendored = pin.get("vendored", {})
    if not isinstance(vendored, dict):
        raise PinError("vendored must be an object mapping grail paths to sha256")
    for vendored_path, expected in sorted(vendored.items()):
        vendored_path = safe_repo_path(vendored_path, "vendored path")
        if not isinstance(expected, str) or not HEX64.fullmatch(expected):
            raise PinError(f"vendored hash for {vendored_path} must be 64-hex sha256")
        upstream = raw(kernel, commit, vendored_path)
        upstream_hash = sha256(upstream)
        if upstream_hash != expected:
            raise PinError(
                f"vendored pin mismatch for {vendored_path}: expected {expected}, got {upstream_hash}"
            )
        try:
            with open(vendored_path, "rb") as handle:
                local_hash = sha256(handle.read())
        except OSError as exc:
            raise PinError(f"vendored copy missing: {vendored_path}: {exc}") from exc
        if local_hash != expected:
            raise PinError(
                f"vendored copy drifted for {vendored_path}: expected {expected}, got {local_hash}"
            )

    print(f"PASS commit {kernel}@{commit}")
    print(f"PASS kernel {kernel_path} blob {kernel_blob}")
    print(f"PASS version {version} from {version_path}")
    for checked in checked_pairs:
        print(f"PASS pinned blob {checked}")
    for vendored_path in sorted(vendored):
        print(f"PASS vendored {vendored_path}")
    print(f"PASS {path}")
    return 0


def convert():
    if os.path.exists("kernel.json"):
        raise PinError("kernel.json already exists; refusing to overwrite it")
    legacy_path = "KERNEL_PIN.json"
    if not os.path.isfile(legacy_path):
        raise PinError("KERNEL_PIN.json not found")
    legacy = load_pin(legacy_path)
    legacy_kernel = legacy.get("kernel")
    if not isinstance(legacy_kernel, dict):
        raise PinError("KERNEL_PIN.json: unsupported legacy shape")
    kernel = legacy_kernel.get("grail")
    ref = legacy_kernel.get("tag")
    frozen = legacy_kernel.get("frozen", {})
    if not isinstance(kernel, str) or not REPOSITORY.fullmatch(kernel):
        raise PinError("KERNEL_PIN.json: kernel.grail is invalid")
    if not isinstance(ref, str) or not ref:
        raise PinError("KERNEL_PIN.json: kernel.tag is invalid")
    if not isinstance(frozen, dict):
        raise PinError("KERNEL_PIN.json: kernel.frozen must be an object")

    commit = resolve_commit(kernel, ref)
    kernel_path = "rapp_brainstem/brainstem.py"
    kernel_bytes = raw(kernel, commit, kernel_path)
    version_path = "rapp_brainstem/VERSION"
    version = raw(kernel, commit, version_path).decode("utf-8").strip()
    vendored = {}
    for vendored_path in sorted(frozen):
        vendored_path = safe_repo_path(vendored_path, "kernel.frozen path")
        vendored[vendored_path] = sha256(raw(kernel, commit, vendored_path))

    converted = {
        "kernel": kernel,
        "sha": commit,
        "version": version,
        "path": kernel_path,
        "kernel_blob": git_blob(kernel_bytes),
        "pinned": datetime.date.today().isoformat(),
    }
    if vendored:
        converted["vendored"] = vendored
    with open("kernel.json", "w", encoding="utf-8") as handle:
        json.dump(converted, handle, indent=2)
        handle.write("\n")
    print(f"converted KERNEL_PIN.json to kernel.json at {kernel}@{commit}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--convert",
        action="store_true",
        help="convert a legacy KERNEL_PIN.json into kernel.json",
    )
    arguments = parser.parse_args(argv)
    try:
        if arguments.convert:
            return convert()
        path = choose_pin_path()
        return 1 if path is None else verify(path)
    except PinError as exc:
        print(f"FAIL {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
