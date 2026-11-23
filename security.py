import os
import re
import secrets
import sys
import unicodedata
from functools import lru_cache

from web_search.config.settings import ROOT, setting

POLICY_FILE = ROOT / "SECURITY_POLICY.md"
CANARY = "CANARY-" + secrets.token_hex(8)
REFUSAL_PREFIX = "REFUSED:"
GENERIC_REJECTION = "This request can't be processed. Please rephrase it as a research question about a lawful topic."
SECRET_NAMES = ("GROQ_API_KEY", "TAVILY_API_KEY", "EXA_API_KEY", "FIRECRAWL_API_KEY", "TURSO_AUTH_TOKEN", "OLLAMA_API_KEY")


class QueryRejected(ValueError):
    """Raised when a question or an answer violates the security policy."""


@lru_cache(maxsize=1)
def load_policy():
    """The policy is mandatory: the app refuses to start without it."""
    text = POLICY_FILE.read_text(encoding="utf-8").strip()
    if not text:
        raise RuntimeError(f"{POLICY_FILE.name} is empty")
    return text.replace("{{CANARY}}", CANARY)


def _normalize(text):
    text = unicodedata.normalize("NFKC", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Cf")
    return re.sub(r"\s+", " ", text).strip().lower()


GAP = r"[^.\n]{0,40}"
BLOCKED = {
    "prompt_override": re.compile(rf"\b(ignore|disregard|forget|override|bypass)\b{GAP}\b(previous|prior|above|earlier|all|your|the)\b{GAP}\b(instructions?|prompts?|rules?|polic(y|ies)|guidelines?|restrictions?)"),
    "prompt_extraction": re.compile(rf"\b(reveal|show|print|repeat|output|display|leak|dump|recite|tell me|what (is|are))\b{GAP}(system prompt|(your|the) (hidden |internal |initial |original |secret )?(instructions?|prompt|rules|polic(y|ies))|developer message|security polic)"),
    "secret_request": re.compile(rf"\b(give|show|reveal|print|send|dump|leak|expose|tell|what('s| is| are))\b{GAP}\b(your|the server'?s?|this (app|server|system)'?s?|backend)\b{GAP}\b(api[ _-]?keys?|secrets?|tokens?|passwords?|credentials|env(ironment)? (variables?|file)|\.env)"),
    "jailbreak": re.compile(r"\b(dan mode|developer mode|do anything now|jailbreak(ed)?|you are now (free|unrestricted)|pretend (that )?you (have no|are not bound))\b"),
    "weapons": re.compile(rf"\b(how to|steps? to|instructions? (for|to)|synthesi[sz]e|synthesis of|make|build|manufacture|produce|recipe for)\b{GAP}\b(nerve agent|sarin|vx gas|anthrax|ricin|bioweapon|biological weapon|chemical weapon|dirty bomb|nuclear (bomb|weapon)|pipe bomb|explosives?|bomb)\b"),
    "malware": re.compile(rf"\b(write|create|build|code|develop|generate)\b{GAP}\b(ransomware|keylogger|malware|botnet|phishing (kit|page|site|email)|credential (stealer|harvester)|ddos (tool|script))\b"),
    "doxxing": re.compile(rf"\b(dox+(ing)?|stalk)\b|\b(find|get|look up|locate)\b{GAP}\b(home address|private address|personal phone)\b"),
    "self_harm": re.compile(r"\b(how to|ways to|best way to|easiest way to)\b[^.\n]{0,20}\b(kill myself|commit suicide|end my life)\b"),
    "minors": re.compile(r"\b(child|minor|underage|teen)\b[^.\n]{0,20}\b(porn|sexual|nude)"),
}


def _log(code):
    print(f"Security: rejected input ({code})", file=sys.stderr)


def injection_score(text):
    """Optional (PROMPT_GUARD=on). Groq's free Prompt Guard 2 returns a 0-1 jailbreak score, but it also flags
    some legitimate security questions, so it is off by default. Returns None if disabled or unavailable."""
    api_key = setting("GROQ_API_KEY")
    if not api_key or setting("PROMPT_GUARD", "off").lower() not in {"on", "1", "true"}:
        return None
    try:
        from groq import Groq

        reply = Groq(api_key=api_key, timeout=10).chat.completions.create(
            model="meta-llama/llama-prompt-guard-2-86m", messages=[{"role": "user", "content": text[:1800]}])
        return float(reply.choices[0].message.content)
    except Exception as error:  # Fail open: the rules and the policy prompt still apply.
        print(f"Security: prompt guard unavailable ({type(error).__name__})", file=sys.stderr)
        return None


def screen_query(query):
    """Reject unsafe questions before any search credits are spent."""
    if any(unicodedata.category(ch) == "Cc" and ch not in "\n\t\r" for ch in query):
        _log("control_characters")
        raise QueryRejected(GENERIC_REJECTION)
    normalized = _normalize(query)
    for code, pattern in BLOCKED.items():
        if pattern.search(normalized):
            _log(code)
            raise QueryRejected(GENERIC_REJECTION)
    score = injection_score(query)
    if score is not None and score >= float(setting("PROMPT_GUARD_THRESHOLD", "0.9")):
        _log("prompt_guard")
        raise QueryRejected(GENERIC_REJECTION)
    return query


SECRET_PATTERNS = [re.compile(p) for p in (
    r"gsk_[A-Za-z0-9]{20,}", r"tvly-[A-Za-z0-9_-]{16,}", r"\bsk-[A-Za-z0-9_-]{20,}", r"\bAKIA[0-9A-Z]{16}\b",
    r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}", r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
)]


def _secret_values():
    values = {setting(name) for name in SECRET_NAMES}
    values |= {value for name, value in os.environ.items() if re.search(r"KEY|TOKEN|SECRET|PASSWORD", name) and value}
    return {value for value in values if len(value) >= 8}


def check_answer(text):
    """Block answers that leak the policy or secrets, and honour the model's own refusals."""
    stripped = text.strip()
    if stripped.upper().startswith(REFUSAL_PREFIX):
        raise QueryRejected(stripped[len(REFUSAL_PREFIX):].strip() or GENERIC_REJECTION)
    lowered = text.lower()
    if CANARY.lower() in lowered or "fieldnotes security policy" in lowered or "internal marker" in lowered:
        _log("policy_leak")
        raise QueryRejected(GENERIC_REJECTION)
    for value in _secret_values():
        text = text.replace(value, "[redacted]")
    for pattern in SECRET_PATTERNS:
        text = pattern.sub("[redacted]", text)
    return text
