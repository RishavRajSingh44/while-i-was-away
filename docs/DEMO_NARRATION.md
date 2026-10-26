# Synthetic demo narration (about 20 seconds)

The accompanying silent screen recording uses only invented Northstar data. The public preview replays a precomputed briefing; it does not contact GitHub, read my laptop, or run Gemma.

“While I Was Away puts my next step first after a break. Every citation opens its source. This synthetic workspace shows a staged cache fix, four distinct PR states, and a selected agent conversation. Historical test claims remain labelled as reports. I can replay the precomputed demo briefing and edit its handoff. In the installed app, local Git and authenticated GitHub supply evidence, while Gemma runs locally through Ollama.”

To reproduce the recording after `npm --prefix frontend ci` and `npm --prefix frontend run build:demo`, start `cd frontend && ./node_modules/.bin/vite preview --host 127.0.0.1 --port 4173 --outDir dist-demo` in one terminal, then run `node e2e/record-demo.mjs` from `frontend/` in another. The script writes `docs/demo/while-i-was-away-demo.webm`; it records no microphone audio. Record this narration separately over the video if publishing. Review the exported file before upload.
