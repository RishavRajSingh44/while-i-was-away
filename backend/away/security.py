"""Boundaries shared by collectors, storage and the HTTP service."""
import re
from urllib.parse import urlsplit

from starlette.responses import JSONResponse

SECRET_PATTERNS = [
    (re.compile(r'''(?i)((?:["']?)(?:api[_-]?key|access[_-]?token|auth[_-]?token|password|passwd|client[_-]?secret|secret[_-]?key|aws_secret_access_key|github_token|gh_token)(?:["']?)\s*[=:]\s*)(?:"[^"\r\n]*"|'[^'\r\n]*'|[^\s,;}]+)'''), r"\1[REDACTED]"),
    (re.compile(r"-----BEGIN [^-]*PRIVATE KEY-----[\s\S]*?(?:-----END [^-]*PRIVATE KEY-----|$)"), "[REDACTED PRIVATE KEY]"),
    (re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9_]{12,}|github_pat_[A-Za-z0-9_]{12,}|sk-[A-Za-z0-9_-]{12,}|AKIA[A-Z0-9]{16})\b"), "[REDACTED TOKEN]"),
    (re.compile(r"(?i)(\b(?:api[_-]?key|access[_-]?token|auth[_-]?token|password|passwd|client[_-]?secret|secret[_-]?key)\b\s*[=:]\s*)[\"']?[^\s,;\"']+[\"']?"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(\bauthorization\s*:\s*(?:bearer|basic)\s+)\S+"), r"\1[REDACTED]"),
    (re.compile(r"(https?://)[^\s/@]+:[^\s/@]+@"), r"\1[REDACTED]@"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"), "[REDACTED JWT]"),
]


def redact(text: str) -> str:
    for pattern, replacement in SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def clean(value):
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, list):
        return [clean(item) for item in value]
    if isinstance(value, dict):
        return {key: ("[REDACTED]" if re.fullmatch(r"(?i)(password|token|api_key|secret|authorization)", key) else clean(item)) for key, item in value.items()}
    return value


class LocalBoundary:
    """Reject rebinding, cross-origin requests and browser form mutations."""
    def __init__(self, app, port=8765, development=False):
        self.app = app
        self.hosts = {f"127.0.0.1:{port}", f"localhost:{port}", f"[::1]:{port}"}
        self.origins = {f"http://{host}" for host in self.hosts}
        if development:
            self.origins |= {"http://127.0.0.1:5173", "http://localhost:5173"}

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        raw = scope.get("headers", [])
        headers = {k.decode().lower(): v.decode() for k, v in raw}
        host = headers.get("host", "").lower()
        origin = headers.get("origin")
        reason = None
        if len([1 for k, _ in raw if k.lower() == b"host"]) != 1 or host not in self.hosts:
            reason = "Untrusted Host header"
        elif origin and origin not in self.origins:
            reason = "Untrusted Origin"
        elif headers.get("sec-fetch-site") == "cross-site":
            reason = "Cross-site requests are not allowed"
        elif scope["method"] not in {"GET", "HEAD", "OPTIONS"}:
            if headers.get("x-away-client") != "1" or headers.get("content-type", "").split(";")[0] != "application/json":
                reason = "Mutations require JSON and X-Away-Client: 1"
        if reason:
            return await JSONResponse({"detail": reason}, status_code=403)(scope, receive, send)
        total = 0

        async def bounded_receive():
            nonlocal total
            message = await receive()
            total += len(message.get("body", b""))
            if total > 3 * 1024 * 1024:
                raise ValueError("Request exceeds the 3 MB limit")
            return message

        async def secured_send(message):
            if message["type"] == "http.response.start":
                message["headers"] += [
                    (b"x-content-type-options", b"nosniff"),
                    (b"referrer-policy", b"no-referrer"),
                    (b"cache-control", b"no-store"),
                    (b"content-security-policy", b"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"),
                ]
            await send(message)
        await self.app(scope, bounded_receive, secured_send)


def local_ollama_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"} or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {"", "/"}:
        raise ValueError("Ollama must use a loopback HTTP address without credentials or a path")
    return value.rstrip("/")
