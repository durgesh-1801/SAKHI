"""Speech-to-Text (STT) Service for SAKHI AI / Risk Engine.

Provides local, offline Whisper inference to transcribe uploaded audio files,
extract acoustic/speech distress keywords, and feed structured signals into
the existing SAKHI Risk Engine.

PRIVACY & SAFETY:
- Audio files are processed in-memory or in temporary files with guaranteed deletion.
- Transcripts and raw audio are NEVER persisted to database or third-party storage.
- Full sensitive transcripts are NOT logged.
- STT failure does NOT default to SAFE.
"""

import io
import logging
import math
import os
import re
import tempfile
import threading
import wave
from typing import Any

from pydantic import BaseModel, Field

from .config import WhisperSettings
from .config import settings as global_settings

logger = logging.getLogger("sakhi.ai_engine.stt")

# Multilingual safety distress keywords (English + Hindi/Hinglish)
DEFAULT_DISTRESS_KEYWORDS: list[str] = [
    # English distress terms
    "help",
    "please help",
    "help me",
    "emergency",
    "someone help",
    "save me",
    "stop",
    "leave me alone",
    "don't touch me",
    "dont touch me",
    "call police",
    "call the police",
    "following me",
    "stalking me",
    "attack",
    "get away",
    "let me go",
    "danger",
    "kill me",
    "hurting me",
    # Hindi / Hinglish distress terms
    "bachao",
    "madad",
    "madad karo",
    "mujhe bachao",
    "chodo",
    "chhoro",
    "chhod mujhe",
    "ruk",
    "police bulao",
    "mar jayenge",
    "koi hai",
    "mera picha kar raha hai",
    "dur raho",
]


class TranscriptionResult(BaseModel):
    """Structured transcription output from Whisper STT inference."""

    text: str = Field(description="Transcribed spoken speech text.")
    language: str = Field(description="Detected or configured language code.")
    confidence: float | None = Field(
        default=None,
        description="Reliable transcription confidence (derived from model token logprobs), or None.",
    )
    duration: float = Field(
        default=0.0,
        description="Audio duration in seconds as reported by the STT model.",
    )
    keywords_detected: list[str] = Field(
        default_factory=list,
        description="Matched distress keywords found in transcript.",
    )
    distress_detected: bool = Field(
        default=False,
        description="Whether distress keywords were detected in the transcript.",
    )
    keyword_confidence: float | None = Field(
        default=None,
        description="Confidence score for detected distress keywords (0.0 to 1.0).",
    )


class STTProcessingError(Exception):
    """Raised when speech-to-text processing or decoding fails."""

    def __init__(self, message: str, details: str | None = None):
        super().__init__(message)
        self.message = message
        self.details = details


class SpeechToTextService:
    """Offline Speech-to-Text service powered by pretrained Whisper.

    Implements lazy model loading, thread-safe initialization, temporary
    storage management with deterministic cleanup, and distress keyword detection.
    """

    def __init__(self, config: WhisperSettings | None = None):
        self.config = config or global_settings.whisper
        self._model: Any = None
        self._lock = threading.Lock()

    def _get_model(self) -> Any:
        """Lazily initialize and return the Whisper model instance (thread-safe)."""
        if self._model is not None:
            return self._model

        with self._lock:
            if self._model is not None:
                return self._model

            logger.info(
                "Initializing Whisper STT model: size=%s, device=%s, compute_type=%s",
                self.config.model_size,
                self.config.device,
                self.config.compute_type,
            )
            try:
                from faster_whisper import WhisperModel

                model_source = self.config.model_path or self.config.model_size
                self._model = WhisperModel(
                    model_size_or_path=model_source,
                    device=self.config.device,
                    compute_type=self.config.compute_type,
                )
                logger.info("Whisper STT model loaded successfully.")
                return self._model
            except Exception as exc:
                logger.exception("Failed to load Whisper STT model")
                raise STTProcessingError(
                    message="Whisper STT model is unavailable or failed to initialize.",
                    details=str(exc),
                ) from exc

    @staticmethod
    def detect_distress_keywords(
        transcript: str,
        keywords: list[str] | None = None,
    ) -> tuple[bool, float, list[str]]:
        """Scans transcribed text for spoken distress keywords.

        Returns:
            Tuple of (distress_detected, confidence, list_of_matched_keywords).
        """
        if not transcript or not transcript.strip():
            return False, 0.0, []

        target_keywords = keywords or DEFAULT_DISTRESS_KEYWORDS
        # Normalize: lowercase and replace punctuation with spaces
        normalized = " " + re.sub(r"[^\w\s]", " ", transcript.lower()) + " "
        normalized = re.sub(r"\s+", " ", normalized)

        matched: list[str] = []
        for kw in target_keywords:
            kw_norm = kw.lower().strip()
            # Match whole word / phrase boundaries
            pattern = r"(?:\b|_)" + re.escape(kw_norm) + r"(?:\b|_)"
            if re.search(pattern, normalized):
                matched.append(kw)

        if matched:
            # Deterministic confidence based on keyword detection presence [0.75 - 0.95]
            confidence = min(0.75 + 0.05 * len(matched), 0.95)
            return True, round(confidence, 2), sorted(set(matched))

        return False, 0.0, []

    @staticmethod
    def _ensure_valid_audio_container(raw_bytes: bytes, ext: str) -> bytes:
        """If a .wav upload contains raw PCM samples without RIFF/WAV header, wrap it in a standard WAV container."""
        if ext == ".wav" and not raw_bytes.startswith(b"RIFF"):
            try:
                # Ensure even sample length for 16-bit PCM
                even_bytes = raw_bytes if len(raw_bytes) % 2 == 0 else raw_bytes[:-1]
                if len(even_bytes) >= 2:
                    buf = io.BytesIO()
                    with wave.open(buf, "wb") as wav_file:
                        wav_file.setnchannels(1)
                        wav_file.setsampwidth(2)
                        wav_file.setframerate(16000)
                        wav_file.writeframes(even_bytes)
                    return buf.getvalue()
            except (wave.Error, ValueError, OSError) as exc:
                logger.debug("Failed to wrap raw PCM samples to WAV container: %s", exc)
        return raw_bytes

    def transcribe(
        self,
        raw_bytes: bytes,
        filename: str = "audio.wav",
    ) -> TranscriptionResult:
        """Transcribes audio bytes using Whisper and checks for distress keywords.

        Ensures raw audio is kept only in temporary storage and cleaned up
        strictly in a finally block.

        Raises:
            STTProcessingError: If audio is corrupted or transcription fails.
        """
        if not raw_bytes or len(raw_bytes) == 0:
            raise STTProcessingError("Cannot transcribe empty audio payload (0 bytes).")

        _, ext = os.path.splitext(filename.lower())
        if not ext:
            ext = ".wav"

        # Check if STT is disabled in config
        if not self.config.enabled:
            logger.info("Whisper STT is disabled in configuration. Skipping transcription.")
            return TranscriptionResult(
                text="",
                language="unknown",
                confidence=None,
                duration=0.0,
                keywords_detected=[],
                distress_detected=False,
                keyword_confidence=0.0,
            )

        model = self._get_model()

        # Wrap raw PCM if necessary
        processed_bytes = self._ensure_valid_audio_container(raw_bytes, ext)

        # Write to secure temporary file with guaranteed cleanup
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as temp_file:
            temp_path = temp_file.name
            temp_file.write(processed_bytes)
            temp_file.flush()
        try:

            # Configure language: None or 'auto' means automatic language detection
            lang = self.config.language
            if lang in (None, "", "auto"):
                lang = None

            segments_gen, info = model.transcribe(
                temp_path,
                language=lang,
                beam_size=1,
            )

            # Consume segments generator
            text_segments: list[str] = []
            logprobs: list[float] = []
            for segment in segments_gen:
                text_segments.append(segment.text)
                if hasattr(segment, "avg_logprob") and segment.avg_logprob is not None:
                    logprobs.append(segment.avg_logprob)

            full_text = " ".join(text_segments).strip()

            # Compute reliable confidence if log probabilities are present
            confidence: float | None = None
            if logprobs:
                mean_logprob = sum(logprobs) / len(logprobs)
                # exp(mean_logprob) approximates token probability in [0, 1]
                prob = math.exp(mean_logprob)
                if math.isfinite(prob):
                    confidence = round(min(max(prob, 0.0), 1.0), 2)

            duration = round(float(info.duration), 2) if hasattr(info, "duration") else 0.0
            detected_lang = getattr(info, "language", lang or "unknown")

            # Privacy note: log only metadata, never the full sensitive transcript
            logger.info(
                "Whisper transcription completed: duration=%.2fs, lang=%s, char_len=%d",
                duration,
                detected_lang,
                len(full_text),
            )

            # Keyword distress detection
            has_keywords, kw_conf, matched_kws = self.detect_distress_keywords(full_text)
            if has_keywords:
                logger.warning(
                    "Distress keywords identified in speech audio: count=%d (keywords=%s)",
                    len(matched_kws),
                    matched_kws,
                )

            return TranscriptionResult(
                text=full_text,
                language=detected_lang,
                confidence=confidence,
                duration=duration,
                keywords_detected=matched_kws,
                distress_detected=has_keywords,
                keyword_confidence=kw_conf if has_keywords else None,
            )

        except STTProcessingError:
            raise
        except Exception as exc:
            logger.exception("Whisper audio transcription failure")
            raise STTProcessingError(
                message="Audio decoding or Whisper STT transcription failed.",
                details=str(exc),
            ) from exc
        finally:
            # Deterministic cleanup of temporary audio file for privacy
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError as err:
                    logger.debug("Could not remove temp audio file %s: %s", temp_path, err)


# Global STT service instance
stt_service = SpeechToTextService()
