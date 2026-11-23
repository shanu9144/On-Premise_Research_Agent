# Fieldnotes frontend

Vite + React app with two pages: **Research** (ask a question, read the digest and sources) and **History** (every saved answer, loaded on demand). Routing uses the URL hash (`#/` and `#/history`), so it works on any static host.

## Local development

```powershell
npm install
npm run dev
```

It expects the API from the repository root on `http://127.0.0.1:8000`. To use another API, copy `.env.example` to `.env.local` and set:

```dotenv
VITE_API_URL=https://your-api.example.com
```

## API contract

Every request sends an `X-Client-Id` header (a random ID stored in `localStorage`) that scopes history to the browser.

- `POST /search` with `{ query, provider, depth }` returns `{ id, digest, sources }`. Each source has `title`, `domain`, `url`, `snippet` and `tag`.
- `GET /history` returns `{ items }`, `GET /history/{id}` returns the full entry, and `DELETE /history/{id}` removes it.

See the [main README](../README.md) for setup.

## Deployment

- **Vercel:** root directory `frontend`, build command `npm run build`, output directory `dist`. [vercel.json](vercel.json) rewrites all paths to `index.html`.
- **Cloudflare Pages:** same settings.

Set `VITE_API_URL` in the deployment environment, and set `CORS_ORIGINS` on the API to this site's origin.

## Checks

```powershell
npx eslint src
npm run build
```
