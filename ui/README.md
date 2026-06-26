# perfectrag-ui

Next.js 15 browser wizard for perfectRAG. Talks to the Python backend
(`perfectrag.webserver`) over REST.

## Dev

```bash
# terminal 1: backend
perfectrag web --no-open

# terminal 2: ui
cd ui
pnpm install
pnpm dev      # http://localhost:3001
```

## Production

```bash
cd ui && pnpm build && pnpm start
# or build a Docker image and ship to GHCR
```

`PERFECTRAG_API_URL` env var overrides the backend host (default: `http://localhost:7777`).
