"""Security headers, output sanitization and protection middleware."""

import html
import re

_HTML_TAGS = re.compile(r"<[^>]+>")


def get_security_headers() -> dict[str, str]:
    """Return production OWASP-compliant security headers."""
    return {
        "Content-Security-Policy": "default-src 'self'; frame-ancestors 'none'; object-src 'none';",
        "Strict-Transport-Security": "max-age=63072000; includeSubDomains; preload",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "geolocation=(), camera=(), microphone=()",
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
    }


def sanitize_output(text: str) -> str:
    """Escape and neutralize dangerous HTML/script tags from responses."""
    if not isinstance(text, str):
        return ""
    # Strip script tags completely
    stripped = re.sub(r"(?i)<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>", "", text)
    # Escape any remaining raw HTML entities
    return html.escape(stripped, quote=True)
