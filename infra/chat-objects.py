#!/usr/bin/env python3
"""Object storage for Jarvis 4's chat (k8s/chat): the buckets deyao-chat-magpie (magpie's blobs) and deyao-chat-db
(chat-db's Barman store), and the credential "deyao-chat" that may use those two and nothing else. Hetzner project
"Cloud Code" (2827255), as DE0CH/jarvis4 infra/objects-key.py does for the router's. Values never print.

S3 credentials exist only in the Hetzner Console (no API): `generate` drives a Chrome over CDP (CDP, default
http://127.0.0.1:9333, e.g. a headed google-chrome on Xvfb with --remote-debugging-port=9333), logged in as
HETZNER_USER / HETZNER_PASSWORD. The admin key HETZNER_S3_* makes the buckets and the policies. Run everything under
`session-secret --keys HETZNER_USER,HETZNER_PASSWORD,HETZNER_S3_ENDPOINT,HETZNER_S3_REGION,HETZNER_S3_ACCESS_KEY,
HETZNER_S3_SECRET_KEY --exec`. The new keys live in FILE (~/.jarvis/deyao-chat-s3.env, mode 600) until `store`.

A Hetzner S3 credential can do everything in the project unless a bucket policy denies it, so:
  - the new key gets a Deny of s3:* (Sid NoDeyaoChatKey) on every bucket but its two;
  - the two new buckets get a copy of every other key's confining Deny already in the project (the Sids No*Key, such as
    the router's NoJarvis4ObjectsKey), or those keys could use them.

  chat-objects.py login      log the Console in
  chat-objects.py buckets    make the two buckets (kept if they exist), copy the other keys' Denies onto them
  chat-objects.py generate   a new credential "deyao-chat" → FILE (refuses if FILE exists)
  chat-objects.py policies   NoDeyaoChatKey on every other bucket names the new key
  chat-objects.py test       what the new key may do (wait ~1 min after `policies`)
  chat-objects.py store      the key into the Jarvis 4 store `chat` (CHAT_S3_ACCESS_KEY / _SECRET_KEY), then shred FILE
"""
import os, sys

# infra/secrets.py sits beside this script: keep the script's folder off the path so `secrets` is Python's own
sys.path = [p for p in sys.path if os.path.abspath(p or '.') != os.path.dirname(os.path.abspath(__file__))]
import json, os, re, secrets, subprocess, sys, time

FILE = os.path.expanduser("~/.jarvis/deyao-chat-s3.env")
CDP = os.environ.get("CDP", "http://127.0.0.1:9333")
PROJECT = "2827255"
URL = f"https://console.hetzner.com/projects/{PROJECT}/security/s3-credentials"
NAME = "deyao-chat"
MINE = ["deyao-chat-magpie", "deyao-chat-db"]
SID = "NoDeyaoChatKey"


def client(ak, sk):
    import boto3
    from botocore.config import Config
    return boto3.client("s3", endpoint_url=os.environ["HETZNER_S3_ENDPOINT"], region_name=os.environ["HETZNER_S3_REGION"],
                        aws_access_key_id=ak, aws_secret_access_key=sk,
                        config=Config(s3={"addressing_style": "virtual"}, retries={"max_attempts": 2}))


def admin():
    return client(os.environ["HETZNER_S3_ACCESS_KEY"], os.environ["HETZNER_S3_SECRET_KEY"])


def newkey():
    v = dict(l.strip().split("=", 1) for l in open(FILE) if "=" in l)
    return v["ACCESS_KEY"], v["SECRET_KEY"]


def policy_of(s3, b):
    from botocore.exceptions import ClientError
    try:
        return json.loads(s3.get_bucket_policy(Bucket=b)["Policy"])
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code == "NoSuchBucket":
            return None  # listed, but in another location than this endpoint's
        if code != "NoSuchBucketPolicy":
            raise
        return {"Version": "2012-10-17", "Statement": []}


def page(pw):
    ctx = pw.chromium.connect_over_cdp(CDP).contexts[0]
    return ctx.pages[0] if ctx.pages else ctx.new_page()


def login():
    from playwright.sync_api import sync_playwright
    u, p = os.environ["HETZNER_USER"], os.environ["HETZNER_PASSWORD"]
    with sync_playwright() as pw:
        pg = page(pw)
        pg.goto(URL, wait_until="commit", timeout=120000)
        for _ in range(6):
            time.sleep(4)
            f = pg.locator("#_username")
            if f.count() and f.is_visible():
                for sel, val in (("#_username", u), ("#_password", p)):
                    pg.locator(sel).click(); pg.keyboard.press("Control+A"); pg.keyboard.press("Delete")
                    pg.locator(sel).type(val, delay=30)
                pg.keyboard.press("Enter"); time.sleep(10); continue
            if f"console.hetzner.com/projects/{PROJECT}" in pg.url and "Log in to your account" not in pg.locator("body").inner_text()[:300]:
                print("ok: logged in"); return
            if "accounts.hetzner.com" in pg.url:
                pg.goto(URL, wait_until="commit", timeout=120000)
        raise SystemExit("not logged in: " + pg.url.split("?")[0])


def buckets():
    from botocore.exceptions import ClientError
    s3 = admin()
    have = [x["Name"] for x in s3.list_buckets()["Buckets"]]
    for b in MINE:
        if b not in have:
            s3.create_bucket(Bucket=b)
            print(f"ok: bucket {b} made")
    # every other key's confining Deny (Sid No*Key, not ours), as it stands on the project's other buckets
    others = {}
    for b in have:
        if b in MINE:
            continue
        for st in (policy_of(s3, b) or {"Statement": []})["Statement"]:
            sid = st.get("Sid", "")
            if re.fullmatch(r"No[A-Za-z0-9]+Key", sid) and sid != SID and st.get("Effect") == "Deny":
                others.setdefault(sid, st["Principal"])
    for b in MINE:
        j = policy_of(s3, b)
        keep = [st for st in j["Statement"] if st.get("Sid") not in others]
        j["Statement"] = keep + [{"Sid": sid, "Effect": "Deny", "Principal": pr, "Action": "s3:*",
                                  "Resource": [f"arn:aws:s3:::{b}", f"arn:aws:s3:::{b}/*"]} for sid, pr in sorted(others.items())]
        if j["Statement"]:
            s3.put_bucket_policy(Bucket=b, Policy=json.dumps(j))
        print(f"ok: {b}: the other keys' Denies ({', '.join(sorted(others)) or 'none'})")


def generate():
    from playwright.sync_api import sync_playwright
    if os.path.exists(FILE):
        raise SystemExit(f"{FILE} exists: store or shred it first")
    os.makedirs(os.path.dirname(FILE), mode=0o700, exist_ok=True)
    with sync_playwright() as pw:
        pg = page(pw)
        pg.goto(URL, wait_until="commit", timeout=120000); pg.get_by_role("button", name="Generate credentials").first.wait_for(timeout=120000)
        pg.get_by_role("button", name="Generate credentials").first.click(); time.sleep(2)
        inp = pg.locator('[data-test="create-s3-credentials-description"] [data-test="input"]')
        inp.click(); inp.type(NAME, delay=40); time.sleep(1)
        pg.get_by_role("button", name="Generate credentials").last.click()
        for _ in range(20):
            time.sleep(1)
            if pg.locator("hc-click-to-show").count():
                break
        else:
            raise SystemExit("no credentials dialog")
        ak = next((t.strip() for t in pg.locator(".click-to-copy__content").all_inner_texts()
                   if re.fullmatch(r"[A-Z0-9]{20}", t.strip())), "")
        pg.locator(".click-to-show").first.click()
        sk = ""
        for _ in range(10):
            time.sleep(0.7)
            raw = pg.evaluate("document.querySelector('hc-click-to-show').textContent")
            raw = raw.replace("Click to show", "").replace("Some random text that is long", "").strip()
            if len(raw) == 40 and " " not in raw:
                sk = raw; break
        if not (ak and sk):
            raise SystemExit("couldn't read the new keys off the dialog")
        with os.fdopen(os.open(FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as f:
            f.write(f"ACCESS_KEY={ak}\nSECRET_KEY={sk}\n")
        pg.keyboard.press("Escape")
        print(f"ok: {NAME} generated (access key {ak[:4]}…) → {FILE}")


def policies():
    s3, (new, _) = admin(), newkey()
    arn = f"arn:aws:iam:::user/p{PROJECT}:" + new
    for b in [x["Name"] for x in s3.list_buckets()["Buckets"]]:
        j = policy_of(s3, b)
        if j is None:
            print(f"skipped: {b} (another location)")
            continue
        rest = [st for st in j["Statement"] if st.get("Sid") != SID]
        if b in MINE:
            if len(rest) != len(j["Statement"]):
                j["Statement"] = rest
                s3.put_bucket_policy(Bucket=b, Policy=json.dumps(j)) if rest else s3.delete_bucket_policy(Bucket=b)
            print(f"ok: {b}: the key's own bucket")
            continue
        j["Statement"] = rest + [{"Sid": SID, "Effect": "Deny", "Principal": {"AWS": arn}, "Action": "s3:*",
                                  "Resource": [f"arn:aws:s3:::{b}", f"arn:aws:s3:::{b}/*"]}]
        s3.put_bucket_policy(Bucket=b, Policy=json.dumps(j))
        print(f"ok: {b} {SID}: the new key is denied s3:* ({len(rest)} other statement(s) kept)")


def test():
    from botocore.exceptions import ClientError
    s3, adm = client(*newkey()), admin()
    t = f"zz-permission-test/{secrets.token_hex(8)}"
    others = [x["Name"] for x in adm.list_buckets()["Buckets"] if x["Name"] not in MINE]
    rows = []

    def check(name, expect, fn):
        try:
            fn(); res = "allowed"
        except ClientError as e:
            res = "refused (" + e.response["Error"].get("Code", "?") + ")"
        rows.append((name, res, res.startswith(expect)))
    for B in MINE:
        check(f"put on {B}", "allowed", lambda B=B: s3.put_object(Bucket=B, Key=t, Body=b"x"))
        check(f"get on {B}", "allowed", lambda B=B: s3.get_object(Bucket=B, Key=t)["Body"].read())
        check(f"delete on {B}", "allowed", lambda B=B: s3.delete_object(Bucket=B, Key=t))
    for O in others:
        check(f"list {O}", "refused", lambda O=O: s3.list_objects_v2(Bucket=O, MaxKeys=1))
        check(f"put on {O}", "refused", lambda O=O: s3.put_object(Bucket=O, Key=t, Body=b"x"))
    for name, res, ok in rows:
        print(f"{'PASS' if ok else 'FAIL'}  {name}: {res}")
    for b in MINE + others:
        r = adm.list_object_versions(Bucket=b, Prefix="zz-permission-test/")
        for x in r.get("Versions", []) + r.get("DeleteMarkers", []):
            adm.delete_object(Bucket=b, Key=x["Key"], VersionId=x["VersionId"])
    if not all(ok for _, _, ok in rows):
        raise SystemExit("some checks failed (a policy write takes up to a minute to reach every gateway: re-run)")
    print(f"ok: everything on {', '.join(MINE)}, nothing anywhere else")


def store():
    ce = os.environ.get("CLAUDE_ENV", os.path.expanduser("~/workspace/claude-env"))
    ak, sk = newkey()
    for k, v in (("CHAT_S3_ACCESS_KEY", ak), ("CHAT_S3_SECRET_KEY", sk)):
        p = os.path.join(os.path.dirname(FILE), k)
        with os.fdopen(os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as f:
            f.write(v)
        try:
            why = ("Jarvis 4 chat's Hetzner S3 " + ("access key" if "ACCESS" in k else "secret key") +
                   " (credential deyao-chat, project Cloud Code): buckets deyao-chat-magpie and deyao-chat-db only, denied"
                   " on every other bucket (DE0CH/services infra/chat-objects.py); magpie's MAGPIE_S3_* and chat-db's"
                   " Secret chat-db-s3")
            subprocess.run(["jarvis", "put-key", "chat", k, "--explain", why], stdin=open(p), check=True)
        finally:
            subprocess.run(["shred", "-u", p], check=True)
    print("ok: CHAT_S3_ACCESS_KEY / _SECRET_KEY in the store chat")


if __name__ == "__main__":
    cmds = {"login": login, "buckets": buckets, "generate": generate, "policies": policies, "test": test, "store": store}
    a = sys.argv[1:]
    if not a or a[0] not in cmds:
        raise SystemExit(__doc__)
    cmds[a[0]]()
