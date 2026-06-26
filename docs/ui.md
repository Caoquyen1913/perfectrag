# Browser wizard

Next.js 15 SPA for the users who prefer a browser over a terminal.

## Architecture

```
Browser → Next.js :3001 → (rewrites /api/*) → FastAPI :7777 → perfectrag core
```

- UI source in `ui/` (published separately as `perfectrag-ui` npm pkg + Docker image).
- Backend in `src/perfectrag/webserver.py` — same functions the CLI uses.
- REST proxy via Next.js rewrites; no CORS issues in dev.

## Running

```bash
# terminal 1: backend
perfectrag web --no-open

# terminal 2: UI
cd ui
pnpm install
pnpm dev
```

Open `http://localhost:3001`.

## Pages

- `/` — hardware detection + entry point
- `/wizard` — 4-step form: use-case → recipe preview → addons → scaffold
- `/dashboard` — doctor checks + live service table (auto-refreshes)

## Production

```bash
cd ui && pnpm build
docker build -t perfectrag/ui:latest .
docker push perfectrag/ui:latest
```

Or run behind any reverse proxy. Set `PERFECTRAG_API_URL` to your backend.

## Extending

Add a page under `ui/src/app/<name>/page.tsx`. Endpoints you need? Add to
`src/perfectrag/webserver.py` — functions there just delegate to existing core modules.
