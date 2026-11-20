# Jarvis Chat's app downloads

`https://chat.deyaochen.com/apps/android.apk`: the newest Jarvis Chat Android app (`dev.de0ch.jarvis4chat`), the button in
Jarvis Chat's Settings → General → Apps on an Android phone (DE0CH/claudecodeui docs/paseo-ui.md "The Android app").

- **Where it comes from:** DE0CH/claudecodeui's `yyc-android` workflow builds and tests the signed APK on every push and,
  on main, puts it in the R2 bucket `jarvis-chat-apps` (object `android.apk`; token `jarvis-chat-apps-upload`, that
  bucket only). The bucket was made once with the `deyao-tofu-state` token (S3 CreateBucket, 2026-11-20).
- **How it is served:** the Worker `jarvis-chat-apps` (`worker/`, its route in `worker/wrangler.jsonc`) checks Access's
  token (the Access app "Jarvis 4 chat", which covers the whole host) and answers from the Cloudflare location's cache,
  keyed by the object's ETag, so the file comes from the edge and a new upload is served from the next request.
- **Deploys:** `.github/workflows/jarvis-chat-apps.yml` (`npm test`, then `wrangler deploy` on main).
