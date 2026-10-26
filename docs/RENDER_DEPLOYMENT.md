# Render public demo: prepared, not deployed

The checked-in [Render Blueprint](../render.yaml) builds only `frontend/dist-demo` as a static site. It has no Python service, server API, Git binary, repository path selector, GitHub credential, Ollama endpoint or model. The browser loads `demo-data.json`, generated solely from original synthetic fixtures with `python scripts/export_demo.py`; “Replay demo briefing” replays a labeled precomputed result. It does not perform Gemma inference. The static app disables local collection, remote sync, fetch and transcript import. A browser test checks that the page makes zero `/api` requests.

To review locally:

```sh
python scripts/export_demo.py
npm --prefix frontend ci
npm --prefix frontend run build:demo
npm --prefix frontend exec -- vite preview --host 127.0.0.1 --port 4173 --outDir dist-demo
```

Open `http://127.0.0.1:4173`. For the browser contract test, set `AWAY_PUBLIC_DEMO=1 AWAY_E2E_URL=http://127.0.0.1:4173` and run `npm --prefix frontend run test:e2e` in another terminal.

When the user authorizes publication: put this directory in its own public Git repository, review `frontend/public/demo-data.json` and `frontend/dist-demo` for synthetic-only content, connect that repository to Render as a Blueprint, inspect the rendered site and its network requests, then record the actual `.onrender.com` URL in the submission. The [official Render Blueprint spec](https://render.com/docs/blueprint-spec) documents `type: web`, `runtime: static`, `buildCommand` and `staticPublishPath`. A `.tech` domain is connected only after the user has obtained and authorized a specific domain; no domain or Render service has been created here.

The full local app remains a separate process on `127.0.0.1`. Do not deploy its FastAPI server publicly: it accepts selected local file paths and is designed for one computer. The public demo can illustrate the UI, evidence links, PR categories, session history and editable handoff, but it cannot prove live inference or GitHub access.
