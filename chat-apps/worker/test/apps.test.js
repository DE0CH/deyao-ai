import { test } from "node:test";
import assert from "node:assert/strict";
import { handle } from "../src/index.js";

const ENV_BASE = { ACCESS_TEAM: "de0ch", ACCESS_AUD: "aud", DOWNLOAD_NAME: "Jarvis-Chat.apk" };

function bucket() {
  const objects = new Map();
  let gets = 0;
  return {
    objects,
    gets: () => gets,
    put(key, text, etag) { objects.set(key, { text, etag, uploaded: new Date("2026-11-20T00:00:00Z") }); },
    async head(key) {
      const o = objects.get(key);
      return o && { etag: o.etag, httpEtag: `"${o.etag}"`, size: o.text.length, uploaded: o.uploaded };
    },
    async get(key, { onlyIf } = {}) {
      gets += 1;
      const o = objects.get(key);
      if (!o || (onlyIf?.etagMatches && onlyIf.etagMatches !== o.etag)) return null;
      return { body: new Response(o.text).body, size: o.text.length };
    },
  };
}
function edgeCache() {
  const m = new Map();
  return { async match(r) { const v = m.get(r.url); return v && new Response(v.body, v.init); },
           async put(r, resp) { m.set(r.url, { body: await resp.text(), init: { headers: resp.headers } }); } };
}
const person = async () => ({ kind: "user", email: "staff@example.com" });
const ctx = () => { const waits = []; return { waits, waitUntil: (p) => waits.push(p) }; };
const req = (path, init = {}) => new Request(`https://chat.deyaochen.com${path}`, init);

test("refuses a request without a good Access token", async () => {
  const APPS = bucket(); APPS.put("android.apk", "APK1", "e1");
  const refuse = async () => { throw new Error("no access token"); };
  const r = await handle(req("/apps/android.apk"), { ...ENV_BASE, APPS }, ctx(), { cache: edgeCache(), verify: refuse });
  assert.equal(r.status, 403);
});

test("refuses a service token: the download is for people", async () => {
  const APPS = bucket(); APPS.put("android.apk", "APK1", "e1");
  const service = async () => ({ kind: "service", commonName: "x" });
  const r = await handle(req("/apps/android.apk"), { ...ENV_BASE, APPS }, ctx(), { cache: edgeCache(), verify: service });
  assert.equal(r.status, 403);
});

test("serves the APK as a download to a signed-in person", async () => {
  const APPS = bucket(); APPS.put("android.apk", "APK1", "e1");
  const r = await handle(req("/apps/android.apk"), { ...ENV_BASE, APPS }, ctx(), { cache: edgeCache(), verify: person });
  assert.equal(r.status, 200);
  assert.equal(r.headers.get("content-type"), "application/vnd.android.package-archive");
  assert.equal(r.headers.get("content-disposition"), 'attachment; filename="Jarvis-Chat.apk"');
  assert.equal(await r.text(), "APK1");
});

test("the second download comes from the edge copy, and a new upload is served at once", async () => {
  const APPS = bucket(); APPS.put("android.apk", "APK1", "e1");
  const cache = edgeCache();
  const c1 = ctx();
  await (await handle(req("/apps/android.apk"), { ...ENV_BASE, APPS }, c1, { cache, verify: person })).text();
  await Promise.all(c1.waits);
  const second = await handle(req("/apps/android.apk"), { ...ENV_BASE, APPS }, ctx(), { cache, verify: person });
  assert.equal(await second.text(), "APK1");
  assert.equal(APPS.gets(), 1, "read from R2 once");
  APPS.put("android.apk", "APK2", "e2");
  const third = await handle(req("/apps/android.apk"), { ...ENV_BASE, APPS }, ctx(), { cache, verify: person });
  assert.equal(await third.text(), "APK2");
});

test("404 before the first upload and for any other path", async () => {
  const APPS = bucket();
  const env = { ...ENV_BASE, APPS };
  assert.equal((await handle(req("/apps/android.apk"), env, ctx(), { cache: edgeCache(), verify: person })).status, 404);
  assert.equal((await handle(req("/apps/other"), env, ctx(), { cache: edgeCache(), verify: person })).status, 404);
});

test("HEAD answers the size without a body", async () => {
  const APPS = bucket(); APPS.put("android.apk", "APK1", "e1");
  const r = await handle(req("/apps/android.apk", { method: "HEAD" }), { ...ENV_BASE, APPS }, ctx(), { cache: edgeCache(), verify: person });
  assert.equal(r.status, 200);
  assert.equal(r.headers.get("content-length"), "4");
});
