#!/usr/bin/env python3
"""Write one of the services' Secrets into git, SOPS-encrypted to the cluster's age key (keys/cluster-age.pub); Flux
decrypts them (the cluster's GitRepository services, DE0CH/jarvis4 k8s/cluster/tenants/services.yaml).

    infra/secrets.py PART KEY[=SRC] …

Each part is one Secret in k8s/secrets/, rewritten whole each run, so name every key of it (only the cluster can read
the old values back). The part's pod gets its annotation bumped so it restarts with the new Secret. SRC is `env:VAR`
(default `env:KEY`) or `file:PATH`.
  search   search.enc.yaml, Secret search-secrets — STORAGEBOX_HOST/USER/PASSWORD, OPENROUTER_API
  tunnel   tunnel.enc.yaml, Secret tunnel-token — token=env:TUNNEL_TOKEN (infra/cloudflare.py)
  dsh-web  dsh-web.enc.yaml, Secret dsh-web-secrets — CF_ACCESS_CLIENT_ID=env:DSH_WEB_ACCESS_ID,
           CF_ACCESS_CLIENT_SECRET=env:DSH_WEB_ACCESS_SECRET (infra/cloudflare.py)
  chat-pigeon, chat-magpie, chat-hermit   the chat's services (k8s/chat), Secrets of the same names; every key from
           infra/chat-keys.py's file (`set -a; . FILE; set +a` first)
  chat-db-magpie, chat-db-hermit          chat-db's role logins (basic-auth: username, password)
  chat-db-s3                              chat-db's Barman store: ACCESS_KEY_ID, SECRET_ACCESS_KEY
Prints names only, never a value."""
import hashlib, json, os, re, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NS = "services"
PARTS = {  # part → (file, Secret name, manifest under k8s/ whose pod restarts, annotation)
    "search": ("search.enc.yaml", "search-secrets", "search/search.yaml", "services/secrets-rev-search"),
    "tunnel": ("tunnel.enc.yaml", "tunnel-token", "edge/cloudflared.yaml", "services/secrets-rev-tunnel"),
    "dsh-web": ("dsh-web.enc.yaml", "dsh-web-secrets", "dsh-web/dsh-web.yaml", "services/secrets-rev-dsh-web"),
    "chat-pigeon": ("chat-pigeon.enc.yaml", "chat-pigeon", "chat/pigeon.yaml", "services/secrets-rev-chat-pigeon"),
    "chat-magpie": ("chat-magpie.enc.yaml", "chat-magpie", "chat/magpie.yaml", "services/secrets-rev-chat-magpie"),
    "chat-hermit": ("chat-hermit.enc.yaml", "chat-hermit", "chat/hermit.yaml", "services/secrets-rev-chat-hermit"),
    # CloudNativePG reads these itself (no pod to restart)
    "chat-db-magpie": ("chat-db-magpie.enc.yaml", "chat-db-magpie", None, None),
    "chat-db-hermit": ("chat-db-hermit.enc.yaml", "chat-db-hermit", None, None),
    "chat-db-s3": ("chat-db-s3.enc.yaml", "chat-db-s3", None, None),
}
SECRET_TYPES = {"chat-db-magpie": "kubernetes.io/basic-auth", "chat-db-hermit": "kubernetes.io/basic-auth"}


def value(src):
    kind, _, ref = src.partition(":")
    if kind == "env":
        v = os.environ.get(ref)
        if not v:
            raise SystemExit(f"{ref} is not set")
        return v
    if kind == "file":
        return open(ref).read()
    raise SystemExit(f"bad source {src}")


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in PARTS:
        raise SystemExit(__doc__)
    part, args = sys.argv[1], sys.argv[2:]
    fname, secret, manifest, ann = PARTS[part]
    data = {}
    for a in args:
        k, _, src = a.partition("=")
        data[k] = value(src or "env:" + k)
    doc = {"apiVersion": "v1", "kind": "Secret", "metadata": {"name": secret, "namespace": NS},
           "type": SECRET_TYPES.get(part, "Opaque"), "stringData": data}
    recipient = open(os.path.join(ROOT, "keys/cluster-age.pub")).read().strip()
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as t:
        json.dump(doc, t)
    try:
        enc = subprocess.run(["sops", "--encrypt", "--age", recipient, "--encrypted-regex", "^(data|stringData)$",
                              "--input-type", "json", "--output-type", "yaml", t.name], check=True, capture_output=True, text=True).stdout
    finally:
        os.unlink(t.name)
    out = os.path.join(ROOT, "k8s/secrets", fname)
    open(out, "w").write(enc)
    if manifest is None:
        print(f"ok: k8s/secrets/{fname} ({', '.join(sorted(data))})")
        return
    rev = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:12]
    mpath = os.path.join(ROOT, "k8s", manifest)
    m = open(mpath).read()
    m2 = re.sub(rf'({re.escape(ann)}: )"[0-9a-f]*"', rf'\g<1>"{rev}"', m)
    if m2 == m and f'{ann}: "{rev}"' not in m:
        raise SystemExit(f"no {ann} annotation in k8s/{manifest}")
    open(mpath, "w").write(m2)
    print(f"ok: k8s/secrets/{fname} ({', '.join(sorted(data))}); k8s/{manifest} {ann}={rev}")


if __name__ == "__main__":
    main()
