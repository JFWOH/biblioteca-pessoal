"""
Voice Profile — Narration role configuration for Phase 13.

Separates the concept of "book narrator" from "assistant voice",
allowing different voices, rates, and expressiveness per role.

ADR-006 compliance: No PyQt6 imports.
"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional


class NarrationRole(Enum):
    """The role for which a voice profile is used."""
    BOOK_NARRATOR = auto()
    ASSISTANT = auto()


@dataclass
class VoiceProfile:
    """Configuration for a specific narration role.

    Attributes:
        role: Whether this is the book narrator or assistant voice.
        preferred_provider: Name of the preferred TTS provider (e.g. 'kokoro').
        voice_id: Specific voice ID within the provider.
        rate: Speech rate multiplier (1.0 = normal).
        volume: Volume level 0.0–1.0.
        style: Narration style hint ('serene', 'technical', 'didactic', 'expressive').
        language: Language code (e.g. 'pt-BR', 'en-US').
    """
    role: NarrationRole
    preferred_provider: str = "kokoro"
    voice_id: Optional[str] = None
    rate: float = 1.0
    volume: float = 1.0
    style: str = "serene"
    language: str = "pt-BR"

    def to_dict(self) -> dict:
        """Serialize to dict for JSON config persistence."""
        return {
            "role": self.role.name.lower(),
            "preferred_provider": self.preferred_provider,
            "voice_id": self.voice_id,
            "rate": self.rate,
            "volume": self.volume,
            "style": self.style,
            "language": self.language,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "VoiceProfile":
        """Deserialize from dict (config.json)."""
        role_str = data.get("role", "book_narrator").upper()
        try:
            role = NarrationRole[role_str]
        except KeyError:
            role = NarrationRole.BOOK_NARRATOR

        return cls(
            role=role,
            preferred_provider=data.get("preferred_provider", "kokoro"),
            voice_id=data.get("voice_id"),
            rate=float(data.get("rate", 1.0)),
            volume=float(data.get("volume", 1.0)),
            style=data.get("style", "serene"),
            language=data.get("language", "pt-BR"),
        )

    @classmethod
    def default_book_narrator(cls) -> "VoiceProfile":
        """Default profile for book narration: serene, comfortable for long reading."""
        return cls(
            role=NarrationRole.BOOK_NARRATOR,
            preferred_provider="kokoro",
            voice_id=None,
            rate=1.0,
            volume=1.0,
            style="serene",
            language="pt-BR",
        )

    @classmethod
    def default_assistant(cls) -> "VoiceProfile":
        """Default profile for assistant voice: didactic, clear, slightly faster."""
        return cls(
            role=NarrationRole.ASSISTANT,
            preferred_provider="kokoro",
            voice_id=None,
            rate=1.05,
            volume=1.0,
            style="didactic",
            language="pt-BR",
        )
