# Third-party notices

This application is original MIT-licensed code. It has no copied source, UI assets or branding from the reference projects. Attributions below identify installed/runtime dependencies and research references; their own licenses continue to apply. Exact direct and transitive package versions used for validation are in `requirements.lock` and `frontend/package-lock.json`.

| Component | Role | License/source |
|---|---|---|
| React, React DOM | Browser UI | MIT, [React](https://github.com/facebook/react/blob/main/LICENSE) |
| Vite, TypeScript, Vitest, ESLint, Playwright | Build, types and tests | MIT/Apache-2.0 as their respective package notices state; [Vite](https://github.com/vitejs/vite/blob/main/LICENSE), [TypeScript](https://github.com/microsoft/TypeScript/blob/main/LICENSE.txt), [Playwright](https://github.com/microsoft/playwright/blob/main/LICENSE) |
| FastAPI, Starlette, Pydantic, Uvicorn, HTTPX | Local API and validation | MIT/BSD/Apache-2.0 per package licenses; [FastAPI](https://github.com/fastapi/fastapi/blob/master/LICENSE), [Pydantic](https://github.com/pydantic/pydantic/blob/main/LICENSE) |
| SQLite, Python standard library | Local persistence and tools | SQLite public domain; Python PSF License |
| Git and GitHub CLI | External local executables; no vendored binary | Git GPL-2.0; GitHub CLI MIT. Their licenses remain with their distributions. |
| Ollama | External local inference runtime; no vendored binary | MIT, [source](https://github.com/ollama/ollama/blob/main/LICENSE) |
| Gemma 3 4B | User-installed model weights; not bundled | [Gemma Terms of Use](https://ai.google.dev/gemma/terms), including use restrictions and distribution terms. Gemma weights are open-weight, not OSI-licensed software. |
| Entire CLI and Claude Code | Optional existing user data sources; no dependency or bundled binary | Entire CLI MIT; Claude Code native data format is internal. Sources and exact revisions in [references](docs/REFERENCES.md). |

No model weights, token, transcript, repository code, or remote PR data is bundled in the public static demo. Its fixtures are original synthetic data.
