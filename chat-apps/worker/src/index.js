// Worker jarvis-chat-apps (chat-apps/README.md): Jarvis Chat's Android app at chat.deyaochen.com/apps/android.apk, from the edge.
// The APK is the object android.apk in R2 bucket jarvis-chat-apps, which DE0CH/aviary's app-android workflow
// replaces after every green build on main. Behind the Access app "Jarvis 4 chat" (infra/cloudflare.py); it checks
// Access's token itself too (authenticate by token). Each Cloudflare location keeps the file in its cache under the
// object's ETag, so a download comes from the edge and a new upload is served from the next request on.
import { verifyAccess } from "./auth.js"; // the same check as DE0CH/yyc-code nametags/worker/src/auth.js

const FILES = { "/apps/android.apk": { key: "android.apk", type: "application/vnd.android.package-archive" } };

export async function handle(request, env, ctx, { cache = caches.default, verify = verifyAccess } = {}) {
  const url = new URL(request.url);
  const file = FILES[url.pathname];
  if (!file) return new Response("Not found", { status: 404 });
  if (request.method !== "GET" && request.method !== "HEAD") return new Response("Method not allowed", { status: 405 });
  try {
    const who = await verify(request.headers.get("Cf-Access-Jwt-Assertion"), { team: env.ACCESS_TEAM, aud: env.ACCESS_AUD });
    if (who.kind !== "user") throw new Error("not a person");
  } catch {
    return new Response("Forbidden", { status: 403 });
  }
  const head = await env.APPS.head(file.key);
  if (!head) return new Response("Not built yet", { status: 404 });
  const headers = {
    "content-type": file.type,
    "content-disposition": `attachment; filename="${env.DOWNLOAD_NAME}"`,
    etag: head.httpEtag,
    "last-modified": head.uploaded.toUTCString(),
    // a browser asks again each time; the edge copy below is what makes that cheap
    "cache-control": "private, no-cache",
  };
  if (request.method === "HEAD") return new Response(null, { headers: { ...headers, "content-length": String(head.size) } });
  // the edge copy: one per object version, never shared beyond this Worker (the key is not the public URL)
  const cacheKey = new Request(`https://apps-cache.internal/${file.key}?v=${encodeURIComponent(head.etag)}`);
  let cached = await cache.match(cacheKey);
  if (!cached) {
    const object = await env.APPS.get(file.key, { onlyIf: { etagMatches: head.etag } });
    if (!object || !object.body) return new Response("Changed while reading, try again", { status: 503 });
    const [toCache, toClient] = object.body.tee();
    ctx.waitUntil(cache.put(cacheKey, new Response(toCache, {
      headers: { "content-length": String(object.size), "cache-control": "public, max-age=31536000, immutable" },
    })));
    return new Response(toClient, { headers: { ...headers, "content-length": String(object.size) } });
  }
  return new Response(cached.body, { headers: { ...headers, "content-length": cached.headers.get("content-length") } });
}

export default { fetch: (request, env, ctx) => handle(request, env, ctx) };
