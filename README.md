# deyao-ai

Deyao's own deployments (Deyao, 2026-11-13; until then this repo was DE0CH/services): what he runs for himself and
how each is set up for him. The code of a product lives in its own repo with nothing of a deployment in it
(DE0CH/aviary and DE0CH/claudecodeui for the chat, which YYC deploys too from DE0CH/YYC); the platform is
DE0CH/jarvis4 (the kernel, the router, the session machines, the cluster). What differs for Deyao (pins, branding,
settings, Cloudflare) is here.

Everything here is a tenant of Jarvis 4's cluster, in the namespace `services`, applied by Flux from this repo's
`k8s/` as a service account that can change nothing outside that namespace (DE0CH/jarvis4
`k8s/cluster/tenants/services.yaml` makes the namespace, its quota and that account).

## Transcript search (`search/`, `k8s/search/`)

Hybrid keyword + semantic search over every Claude session transcript of every Jarvis on the Storage Box
(`claude-records/`: archives, `.live/` copies of running sessions, Jarvis 1's `.paused/` snapshots) and the task
records. One SQLite index on a volume, two replicas, one writer (lease in the database); the index is copied to
`claude-records/.services/search.db.gz` daily and a new volume is seeded from it.

Reached only at **https://search.deyaochen.com**, behind the Cloudflare Access app "Transcript search" through this
repo's own tunnel `services` (`k8s/edge`):
- Deyao: the page at `/` in a browser (his email).
- Sessions: `scripts/transcript-search.py` in DE0CH/claude-env, with the Access service token `transcript-search`
  (`SEARCH_ACCESS_ID` / `SEARCH_ACCESS_SECRET` in the `default` store).

API (all GET unless noted; JSON):
- `/search?q=…` — `mode` hybrid|keyword|semantic, `kind` msg,tool,doc, `state` live,paused,archive, `after`/`before`
  YYYY-MM-DD, `session` (title or uuid), `limit` ≤50, `rerank` (default on), `group=1` (best sessions), `full=1`.
- `/context?id=N&before=3&after=3` — the chunks around hit N (≤30 each side).
- `/status` — index size, the last crawl and its error, replicas, memory.
- `POST /reindex` (`?full=1` rebuilds; embeddings are cached by text hash) — a crawl now instead of within 5 min.

## dsh web UI (`dsh-web/`, `k8s/dsh-web/`)

The persistent web UI of Jarvis 4's `dsh` sessions (DeepSeek Harness from DE0CH/deepseek-harness, DE0CH/jarvis4
`session-image/base/harness-dsh.sh`): **https://dsh.deyaochen.com/s/<session id>/**, behind the Access app "DeepSeek
Harness" (Deyao's email). A stateless Node proxy, two replicas: it forwards the page, the API, the plugin scripts and the
WebSocket to the session's own origin `https://<session id>-s.deyaochen.com/` with the Access service token `dsh-web`
(`DSH_WEB_ACCESS_ID/SECRET`, Secret dsh-web-secrets), keeps redirects and dsh's cookie under `/s/<id>/`, serves the UI's
versioned static files from its own cache, and answers a paused or gone session with a page that says so.

## The chat (`k8s/chat/`)

Jarvis 4's chat at **https://chat.deyaochen.com** (DE0CH/jarvis4 `aviary/README.md`): aviary's pigeon and magpie (the
same builds as YYC AI's), the app bundle `pigeon-app` (DE0CH/claudecodeui), Jarvis 4's hermit-jarvis and their Postgres
`chat-db`; `.github/workflows/chat-pin.yml` pins the newest builds every 15 minutes. What is Deyao's own about it lives
here, never in aviary or the app:

- **Settings** (`k8s/chat/settings.json`): the chat's name and language, the models a conversation's menu offers
  (the first is the default) with each one's thinking levels, its context window when Claude Code does not know it,
  and the OpenRouter hosts of an OpenRouter model. hermit-jarvis reads it at its start and hands it to each session
  machine's gateway at boot (DE0CH/jarvis4 `aviary/src/settings.rs`, which refuses a file it cannot use); a change
  rolls hermit. The Jarvis 4 app's own New session picker is the router's (DE0CH/jarvis4 `router/harness.go`
  `modelCatalog`): a model added here is added there too.
- **Branding** (`k8s/chat/branding/`: the logo, the tab icons, the home-screen icons, the web manifest). The app is one
  build for every deployment and holds neutral files under `/branding/` (claudecodeui docs/paseo-ui.md "Branding");
  pigeon's initContainer `branding` copies these over them. After changing a file run `infra/branding.py`, which
  writes `k8s/chat/branding.yaml` (the ConfigMap, as binaryData) and the files' hash into pigeon's pod template, and
  commit both. Not a kustomize generator: Flux leaves image files out of what it builds from. Not a mount over the
  bundle: the bundle is read-only in pigeon and a mount point it lacks cannot be made.

## Cloudflare (tofu)

Deyao's Cloudflare account as code, so far its Access organisation: the one login page of every Access app of the
account (name, Jarvis 4 icon, colours, header and footer). `cloudflare/tofu/*.tf` (OpenTofu, Cloudflare provider
5.28.1) is applied by the GitHub workflow `.github/workflows/cloudflare.yml` on every push touching it and every 30
minutes, which also reverts dashboard edits. Secrets (Actions, from the store `infra`, set with `gh secret set` and
`SERVICES_CI_SECRETS_TOKEN`): `CF_ACCESS_ORG_TOKEN` (token `deyao-access-org`, Access Organizations Write+Read) and
`DEYAO_TOFU_R2_*` (token `deyao-tofu-state`). State: R2 bucket `deyao-tofu-state` on Deyao's account, key
`services/cloudflare/terraform.tfstate`. Plan locally with the R2 key as `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` and
`TF_VAR_cloudflare_api_token=$CF_ACCESS_ORG_TOKEN tofu plan` in `cloudflare/tofu`.

## Setup

- `infra/cloudflare.py OUT` — tunnel, Access app, service token, DNS (idempotent; `CF_JARVIS2_INFRA_TOKEN`,
  `CLOUDFLARE_API`).
- `infra/secrets.py search STORAGEBOX_HOST STORAGEBOX_USER STORAGEBOX_PASSWORD OPENROUTER_API`,
  `infra/secrets.py tunnel token=env:TUNNEL_TOKEN` and
  `infra/secrets.py dsh-web CF_ACCESS_CLIENT_ID=env:DSH_WEB_ACCESS_ID CF_ACCESS_CLIENT_SECRET=env:DSH_WEB_ACCESS_SECRET` — the Secrets, SOPS-encrypted to the cluster's age key
  (`keys/cluster-age.pub`).
- `.github/workflows/search.yml` and `dsh-web.yml` build and pin the images; the GHCR packages `services-search` and
  `services-dsh-web` are public.
