#!/usr/bin/env python3
"""Check that the LLM provider keys in .env are accepted, before spending a live run on them.

Calls each provider's `GET /v1/models` — authenticated but free (no tokens), so it's safe
to run before every comparison/smoke script. The app itself surfaces a rejected key only
as a generic "502 Upstream ... API error", which hides that the cause is a bad key.

Also compares each key against the running `api` container's environment (when it's up):
editing .env doesn't reach the container until it's recreated (`docker compose up -d api`),
so a key can be valid on disk yet stale where the app actually uses it.

Stdlib-only, matching every other hand-run script in scripts/.

Usage:
  python3 scripts/check_api_keys.py      # or: make check-keys
Exit code 0 if every configured key is accepted (and in sync with the container), else 1.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"

PROVIDERS = {
    "OPENAI_API_KEY": {
        "url": "https://api.openai.com/v1/models",
        "headers": lambda key: {"Authorization": f"Bearer {key}"},
    },
    "ANTHROPIC_API_KEY": {
        "url": "https://api.anthropic.com/v1/models",
        "headers": lambda key: {"x-api-key": key, "anthropic-version": "2023-06-01"},
    },
}


def load_env_value(name: str) -> str:
    """Read `name` from .env, falling back to the environment.

    .env comes first (unlike the other scripts' loaders) because it's what the api
    container actually reads via `env_file` — a different key exported in the shell
    would otherwise get tested instead of the one the app uses."""
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            if line.startswith(f"{name}="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return os.environ.get(name, "")


def container_value(name: str) -> str | None:
    """The value of `name` inside the running api container, or None if it isn't reachable."""
    try:
        out = subprocess.run(
            ["docker", "compose", "exec", "-T", "api", "printenv", name],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=ENV_PATH.parent,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip()


def fingerprint(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()[:8]


def check_key(name: str, key: str) -> tuple[bool, str]:
    spec = PROVIDERS[name]
    request = urllib.request.Request(spec["url"], headers=spec["headers"](key))
    try:
        with urllib.request.urlopen(request, timeout=15) as resp:
            return True, f"accepted (HTTP {resp.status})"
    except urllib.error.HTTPError as e:
        hint = {401: "invalid, revoked or expired key", 403: "key lacks permission"}.get(e.code, "")
        return False, f"rejected (HTTP {e.code}{' — ' + hint if hint else ''})"
    except (urllib.error.URLError, TimeoutError) as e:
        return False, f"unreachable ({e})"


def main() -> int:
    ok = True
    for name in PROVIDERS:
        key = load_env_value(name)
        if not key:
            print(f"{name:<18} MISSING  not set in env or .env")
            ok = False
            continue
        accepted, detail = check_key(name, key)
        status = "OK      " if accepted else "FAIL    "
        print(f"{name:<18} {status} {detail}  [key …{key[-4:]}, sha {fingerprint(key)}]")
        ok &= accepted

        in_shell = os.environ.get(name)
        if in_shell and in_shell != key:
            print(
                f"{'':<18} NOTE     shell exports a different {name} "
                f"(sha {fingerprint(in_shell)}) — the app uses .env, "
                f"but scripts run outside Docker may pick up the shell one"
            )

        in_container = container_value(name)
        if in_container is None:
            print(f"{'':<18}          (api container not running — skipped sync check)")
        elif in_container != key:
            print(
                f"{'':<18} STALE    api container has a different key "
                f"(sha {fingerprint(in_container) if in_container else 'empty'}) — "
                f"run `docker compose up -d api` to pick up .env"
            )
            ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
