#!/usr/bin/env python3
"""Every random credential of Jarvis 4's chat (k8s/chat; DE0CH/jarvis4 aviary/README.md), made once and written to OUT
(mode 600) as KEY=VALUE lines, so the three services' Secrets agree (a pair token is <CALLER>_TOKEN_<CALLEE> on one side
and <CALLEE>_ACCEPT_<CALLER> on the other). Prints names only.

    infra/chat-keys.py OUT [--keep OLD]

--keep OLD carries every value OLD already has (a rerun after adding a key changes nothing else). Then, with the
values outside this file in the env (MAGPIE_S3_*, HERMIT_JARVIS_ACCESS_*, HERMIT_ACCESS_AUD):
    set -a; . OUT; set +a
    infra/secrets.py chat-pigeon PIGEON_TOKEN_MAGPIE PIGEON_TOKEN_HERMIT PIGEON_TOKEN_MODEL PIGEON_VIEW_AS_KEYS PIGEON_BLOB_KEYS
    infra/secrets.py chat-magpie MAGPIE_DATABASE_URL MAGPIE_S3_ENDPOINT MAGPIE_S3_REGION MAGPIE_S3_BUCKET \\
      MAGPIE_S3_ACCESS_KEY_ID MAGPIE_S3_SECRET_ACCESS_KEY MAGPIE_ACCEPT_PIGEON MAGPIE_ACCEPT_GATEWAY MAGPIE_ACCEPT_HERMIT \\
      MAGPIE_ACCEPT_ADMIN MAGPIE_TOKEN_HERMIT
    infra/secrets.py chat-hermit HERMIT_DATABASE_URL HERMIT_TOKEN_KEYS HERMIT_JARVIS_URL HERMIT_JARVIS_ACCESS_ID \\
      HERMIT_JARVIS_ACCESS_SECRET HERMIT_OWNER HERMIT_ACCESS_TEAM HERMIT_ACCESS_AUD HERMIT_ACCEPT_PIGEON \\
      HERMIT_ACCEPT_MAGPIE HERMIT_ACCEPT_GATEWAY HERMIT_ACCEPT_ADMIN MODEL_ACCEPT_PIGEON HERMIT_TOKEN_MAGPIE \\
      GATEWAY_TOKEN_MAGPIE GATEWAY_TOKEN_HERMIT
    infra/secrets.py chat-db-magpie username=env:DB_MAGPIE_USER password=env:DB_MAGPIE_PASSWORD
    infra/secrets.py chat-db-hermit username=env:DB_HERMIT_USER password=env:DB_HERMIT_PASSWORD
"""
import os, sys

# infra/secrets.py sits beside this script: keep the script's folder off the path so `secrets` is Python's own
sys.path = [p for p in sys.path if os.path.abspath(p or '.') != os.path.dirname(os.path.abspath(__file__))]
import base64, os, secrets, sys


def b64url32():
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=")


def main():
    if len(sys.argv) not in (2, 4) or (len(sys.argv) == 4 and sys.argv[2] != "--keep"):
        raise SystemExit(__doc__)
    old = {}
    if len(sys.argv) == 4:
        for line in open(sys.argv[3]):
            k, _, v = line.rstrip("\n").partition("=")
            if k:
                old[k] = v
    v = dict(old)

    def put(k, make):
        if k not in v:
            v[k] = make()
        return v[k]

    pair = lambda caller, callee: put(f"{caller}_TOKEN_{callee}", b64url32)  # noqa: E731
    # pigeon → magpie, hermit, model; the gateway → magpie, hermit; hermit → magpie; magpie → hermit; an admin's tools
    v["MAGPIE_ACCEPT_PIGEON"] = pair("PIGEON", "MAGPIE")
    v["HERMIT_ACCEPT_PIGEON"] = pair("PIGEON", "HERMIT")
    v["MODEL_ACCEPT_PIGEON"] = pair("PIGEON", "MODEL")
    v["MAGPIE_ACCEPT_GATEWAY"] = pair("GATEWAY", "MAGPIE")
    v["HERMIT_ACCEPT_GATEWAY"] = pair("GATEWAY", "HERMIT")
    v["MAGPIE_ACCEPT_HERMIT"] = pair("HERMIT", "MAGPIE")
    v["HERMIT_ACCEPT_MAGPIE"] = pair("MAGPIE", "HERMIT")
    v["MAGPIE_ACCEPT_ADMIN"] = pair("ADMIN", "MAGPIE")
    v["HERMIT_ACCEPT_ADMIN"] = pair("ADMIN", "HERMIT")
    put("PIGEON_VIEW_AS_KEYS", b64url32)
    put("PIGEON_BLOB_KEYS", b64url32)
    put("HERMIT_TOKEN_KEYS", lambda: "1:" + b64url32())
    put("DB_MAGPIE_USER", lambda: "magpie")
    put("DB_HERMIT_USER", lambda: "hermit")
    put("DB_MAGPIE_PASSWORD", lambda: secrets.token_hex(24))
    put("DB_HERMIT_PASSWORD", lambda: secrets.token_hex(24))
    # aviary's Rust clients: sslmode=require (aviary-pg requires TLS whatever the URL says)
    v["MAGPIE_DATABASE_URL"] = f"postgres://magpie:{v['DB_MAGPIE_PASSWORD']}@chat-db-rw.services.svc.cluster.local:5432/magpie?sslmode=require"
    v["HERMIT_DATABASE_URL"] = f"postgres://hermit:{v['DB_HERMIT_PASSWORD']}@chat-db-rw.services.svc.cluster.local:5432/hermit?sslmode=require"
    put("HERMIT_JARVIS_URL", lambda: "https://jarvis4.deyaochen.com")
    put("HERMIT_OWNER", lambda: "chendeyao000@gmail.com")
    put("HERMIT_ACCESS_TEAM", lambda: "de0ch.cloudflareaccess.com")
    put("MAGPIE_S3_BUCKET", lambda: "deyao-chat-magpie")
    put("MAGPIE_S3_ENDPOINT", lambda: "https://fsn1.your-objectstorage.com")
    put("MAGPIE_S3_REGION", lambda: "fsn1")
    out = sys.argv[1]
    fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.writelines(f"{k}={val}\n" for k, val in sorted(v.items()))
    print(f"ok: {out}: {', '.join(sorted(v))} ({len(set(v) - set(old))} new)")


if __name__ == "__main__":
    main()
