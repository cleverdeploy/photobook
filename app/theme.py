"""AI-generated per-album visual themes via the Claude API.

Given an album title we ask Claude for a small, strict JSON theme: a palette,
a pair of Google fonts, a handful of emoji motifs, and a one-line tagline. The
album page renders entirely from this dict, so a bad/empty response must never
break the page — every field is sanitised and there's a deterministic fallback.
"""
from __future__ import annotations

import hashlib
import re
from typing import Optional

from pydantic import BaseModel, Field

from . import config

# Curated allowlist — these are the only families we load from Google Fonts, so
# the model must pick from them. Anything else is replaced during sanitisation.
HEADING_FONTS = [
    "Fraunces", "Playfair Display", "Lobster", "Pacifico", "Abril Fatface",
    "Bebas Neue", "Comfortaa", "Righteous", "Caveat", "Bungee", "Cinzel",
    "Yeseva One", "Archivo Black", "Shrikhand", "Sora",
]
BODY_FONTS = [
    "Inter", "Nunito", "Work Sans", "Lora", "Karla", "Mulish", "Rubik",
    "Source Sans 3", "DM Sans", "Quicksand",
]
PATTERNS = ["scatter", "confetti", "corners", "border"]

_HEX_RE = re.compile(r"^#?[0-9a-fA-F]{6}$")
_HEX3_RE = re.compile(r"^#?[0-9a-fA-F]{3}$")

DEFAULT_THEME = {
    "description": "A shared photo album — add your pictures!",
    "bg": "#0f1115",
    "surface": "#1b1e26",
    "accent": "#a78bfa",
    "accent2": "#f0abfc",
    "text": "#f5f5f7",
    "heading_font": "Fraunces",
    "body_font": "Inter",
    "motifs": ["📸", "✨", "🖼️", "📷", "🌟", "💫"],
    "pattern": "scatter",
}


class _ThemeModel(BaseModel):
    """Schema the model fills in. Kept flat; validated again after parsing."""

    description: str = Field(description="A short, warm one-line tagline for the album (max ~90 chars).")
    bg: str = Field(description="Page background colour as a 6-digit hex like #101418. Should be a deep, rich tone that fits the theme.")
    surface: str = Field(description="Card/surface colour as 6-digit hex, slightly lighter than bg.")
    accent: str = Field(description="Primary accent colour (buttons, links) as 6-digit hex. Vivid and on-theme.")
    accent2: str = Field(description="Secondary accent colour as 6-digit hex.")
    text: str = Field(description="Main text colour as 6-digit hex with strong contrast against bg.")
    heading_font: str = Field(description="A display font name chosen from the provided heading list.")
    body_font: str = Field(description="A readable font name chosen from the provided body list.")
    motifs: list[str] = Field(description="Exactly 6 single emoji that evoke the theme (e.g. gardening -> 🪴🌱🌻🐝🧤🌷).")
    pattern: str = Field(description="One of: scatter, confetti, corners, border.")


def _system_prompt() -> str:
    return (
        "You are a tasteful visual art director for a photo-sharing app. "
        "Given an album title, design a cohesive, attractive dark-mode theme that "
        "evokes the album's subject. Themes should feel hand-crafted and specific: "
        "a gardening album gets earthy greens and plant emoji (🪴🌱🌻); a beach "
        "holiday gets warm sands and ocean blues (🏖️🌊🐚); a birthday gets festive "
        "brights (🎂🎈🎉).\n\n"
        "Rules:\n"
        "- All colours are 6-digit hex (#rrggbb). Use a DARK background (deep, not black) "
        "with light, high-contrast text. Keep accents vivid and harmonious.\n"
        f"- heading_font MUST be one of: {', '.join(HEADING_FONTS)}.\n"
        f"- body_font MUST be one of: {', '.join(BODY_FONTS)}.\n"
        "- motifs MUST be exactly 6 single emoji that clearly represent the subject.\n"
        f"- pattern MUST be one of: {', '.join(PATTERNS)}.\n"
        "- description is a short, friendly tagline (no quotes, max ~90 chars)."
    )


def _norm_hex(value: str, default: str) -> str:
    if not isinstance(value, str):
        return default
    v = value.strip()
    if _HEX_RE.match(v):
        return ("#" + v.lstrip("#")).lower()
    if _HEX3_RE.match(v):
        s = v.lstrip("#")
        return ("#" + "".join(c * 2 for c in s)).lower()
    return default


def _sanitise(data: dict) -> dict:
    out = dict(DEFAULT_THEME)
    out["bg"] = _norm_hex(data.get("bg", ""), DEFAULT_THEME["bg"])
    out["surface"] = _norm_hex(data.get("surface", ""), DEFAULT_THEME["surface"])
    out["accent"] = _norm_hex(data.get("accent", ""), DEFAULT_THEME["accent"])
    out["accent2"] = _norm_hex(data.get("accent2", ""), out["accent"])
    out["text"] = _norm_hex(data.get("text", ""), DEFAULT_THEME["text"])

    hf = str(data.get("heading_font", "")).strip()
    out["heading_font"] = hf if hf in HEADING_FONTS else DEFAULT_THEME["heading_font"]
    bf = str(data.get("body_font", "")).strip()
    out["body_font"] = bf if bf in BODY_FONTS else DEFAULT_THEME["body_font"]

    pat = str(data.get("pattern", "")).strip().lower()
    out["pattern"] = pat if pat in PATTERNS else DEFAULT_THEME["pattern"]

    motifs = data.get("motifs") or []
    motifs = [str(m).strip() for m in motifs if str(m).strip()]
    out["motifs"] = motifs[:6] if motifs else list(DEFAULT_THEME["motifs"])

    desc = str(data.get("description", "")).strip().replace("\n", " ")
    out["description"] = (desc[:120] if desc else DEFAULT_THEME["description"])
    return out


def fallback_theme(title: str) -> dict:
    """Deterministic, decent-looking theme when the AI is unavailable."""
    presets = [
        ("#10231b", "#173026", "#34d399", "#a7f3d0", "#ecfdf5"),  # green
        ("#1a1320", "#241a2e", "#c084fc", "#f5d0fe", "#faf5ff"),  # violet
        ("#1d1410", "#2a1d16", "#fb923c", "#fed7aa", "#fff7ed"),  # amber
        ("#0f1b24", "#152734", "#38bdf8", "#bae6fd", "#f0f9ff"),  # ocean
        ("#231016", "#311620", "#fb7185", "#fecdd3", "#fff1f2"),  # rose
    ]
    idx = int(hashlib.sha256(title.encode("utf-8")).hexdigest(), 16) % len(presets)
    bg, surface, accent, accent2, text = presets[idx]
    theme = dict(DEFAULT_THEME)
    theme.update(bg=bg, surface=surface, accent=accent, accent2=accent2, text=text)
    return theme


def generate_theme(title: str) -> dict:
    """Return a sanitised theme dict for the title. Never raises."""
    if not config.ANTHROPIC_API_KEY:
        return fallback_theme(title)
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        resp = client.with_options(timeout=config.THEME_TIMEOUT_SECONDS).messages.parse(
            model=config.THEME_MODEL,
            max_tokens=1024,
            thinking={"type": "disabled"},
            system=[
                {
                    "type": "text",
                    "text": _system_prompt(),
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[
                {"role": "user", "content": f"Album title: {title!r}\nDesign the theme."}
            ],
            output_format=_ThemeModel,
        )
        parsed: Optional[_ThemeModel] = resp.parsed_output
        if parsed is None:
            return fallback_theme(title)
        return _sanitise(parsed.model_dump())
    except Exception as exc:  # noqa: BLE001 - theming must never break album creation
        import logging

        logging.getLogger("photobook").warning("theme generation failed: %s", exc)
        return fallback_theme(title)
