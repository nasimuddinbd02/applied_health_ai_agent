"""Safety helper: PII redaction + lightweight emergency detection."""

import re


class SafetyGuard:
    _EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
    _PHONE_RE = re.compile(r"(?:\+?\d[\s\-().]?){9,}\d")

    _EMERGENCY_TERMS = (
        "not breathing", "can't breathe", "cannot breathe", "collapsed", "seizure",
        "seizing", "unconscious", "bleeding heavily", "won't stop bleeding", "hit by",
        "poison", "toxic", "bloat", "blue gums", "choking",
    )

    def redact(self, text: str) -> str:
        """Mask emails/phone numbers before writing to AuditEvent.summary."""
        if not text:
            return text
        text = self._EMAIL_RE.sub("[email]", text)
        text = self._PHONE_RE.sub("[phone]", text)
        return text

    def looks_like_emergency(self, text: str) -> bool:
        low = (text or "").lower()
        return any(term in low for term in self._EMERGENCY_TERMS)
