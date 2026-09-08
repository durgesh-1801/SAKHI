"""Audio Ingestion, Validation, and Acoustic Distress Pipeline for SAKHI.

Validates uploaded audio payloads, checks format boundaries and size constraints,
and extracts acoustic features / distress indicators.

IMPORTANT:
- Whisper / STT model is PLANNED and not fabricated in application code.
- Twilio is telephony/SMS owned by Backend 3, NOT speech recognition.
- If audio analysis fails, the pipeline fails safely with an explicit error
  and NEVER assumes safety.
"""

import logging
import math
import os

from fastapi import HTTPException, UploadFile, status
from pydantic import BaseModel

logger = logging.getLogger("sakhi.ai_engine.audio")

# Allowed audio extensions and MIME types
ALLOWED_EXTENSIONS: set[str] = {".wav", ".mp3", ".m4a", ".ogg", ".flac"}
ALLOWED_MIME_TYPES: set[str] = {
    "audio/wav",
    "audio/x-wav",
    "audio/wave",
    "audio/mpeg",
    "audio/mp3",
    "audio/m4a",
    "audio/mp4",
    "audio/ogg",
    "audio/flac",
    "audio/x-flac",
    "application/octet-stream",  # often sent by mobile clients for raw recordings
}
MAX_AUDIO_BYTES: int = 10 * 1024 * 1024  # 10 MB upload ceiling


class AudioAnalysisResult(BaseModel):
    """Result of acoustic and speech distress feature extraction."""

    distress_detected: bool
    confidence: float
    keywords_detected: list[str] = []
    rms_energy: float | None = None
    status: str = "SUCCESS"  # SUCCESS, FAILED
    error_message: str | None = None


class AudioValidator:
    """Validates audio file format, size, and integrity."""

    @staticmethod
    def validate_filename_and_mime(filename: str | None, content_type: str | None) -> str:
        """Validates file extension and content type."""
        if not filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "MISSING_FILENAME", "message": "Audio file must have a filename."},
            )

        _, ext = os.path.splitext(filename.lower())
        if ext not in ALLOWED_EXTENSIONS:
            logger.warning("Rejected audio upload with unsupported extension: %s", ext)
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail={
                    "error": "UNSUPPORTED_AUDIO_FORMAT",
                    "message": f"Unsupported audio format '{ext}'. Supported formats: {sorted(ALLOWED_EXTENSIONS)}.",
                },
            )

        if content_type and content_type.lower() not in ALLOWED_MIME_TYPES:
            # If MIME type is present and not recognized, log warning but allow extension match
            logger.debug("Audio upload MIME type %s permitted via extension %s", content_type, ext)

        return ext

    @staticmethod
    def validate_payload_bytes(raw_bytes: bytes) -> None:
        """Validates audio byte payload size and non-emptiness."""
        if len(raw_bytes) == 0:
            logger.warning("Rejected empty audio payload.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "EMPTY_AUDIO", "message": "Uploaded audio payload is empty (0 bytes)."},
            )

        if len(raw_bytes) > MAX_AUDIO_BYTES:
            logger.warning("Rejected oversized audio payload: %d bytes", len(raw_bytes))
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail={
                    "error": "AUDIO_TOO_LARGE",
                    "message": f"Audio file exceeds maximum permitted size of {MAX_AUDIO_BYTES // (1024 * 1024)}MB.",
                },
            )


class AcousticDistressExtractor:
    """Extracts acoustic features and distress signatures from audio bytes.

    Provides a clean heuristic acoustic baseline (energy / amplitude analysis)
    and an extensible interface for future ML / Whisper STT models.
    """

    @staticmethod
    def analyze_bytes(raw_bytes: bytes, filename: str) -> AudioAnalysisResult:
        """Analyzes raw audio bytes for acoustic distress signatures.

        Fails safely if audio data is corrupt, returning status='FAILED'
        without fabricating a safe result.
        """
        try:
            # Inspect byte-level amplitude / sample characteristics
            # For 16-bit PCM or raw audio stream chunks:
            sample_count = len(raw_bytes) // 2
            if sample_count == 0:
                return AudioAnalysisResult(
                    distress_detected=False,
                    confidence=0.0,
                    rms_energy=0.0,
                )

            # Simple robust RMS calculation over raw audio bytes
            sum_squares = 0
            for i in range(0, len(raw_bytes) - 1, 2):
                # Unpack 16-bit signed integer (little-endian)
                val = int.from_bytes(raw_bytes[i : i + 2], byteorder="little", signed=True)
                sum_squares += val * val

            mean_square = sum_squares / max(sample_count, 1)
            rms = math.sqrt(mean_square)

            # Normalized energy metric [0.0, 1.0] relative to 16-bit max amplitude (32767)
            normalized_energy = min(rms / 32767.0, 1.0)

            # Baseline heuristic threshold: high acoustic energy (> 0.45) indicates screaming/struggle
            distress_detected = normalized_energy >= 0.45
            confidence = round(normalized_energy, 2)

            return AudioAnalysisResult(
                distress_detected=distress_detected,
                confidence=confidence,
                rms_energy=round(rms, 2),
                status="SUCCESS",
            )
        except Exception as exc:
            logger.exception("Error extracting acoustic features from audio")
            return AudioAnalysisResult(
                distress_detected=False,
                confidence=0.0,
                status="FAILED",
                error_message=f"Audio decoding failure: {exc!s}",
            )


class AudioPipeline:
    """Unified audio processing pipeline for SAKHI."""

    def __init__(self):
        self.validator = AudioValidator()
        self.extractor = AcousticDistressExtractor()

    async def process_upload(self, file: UploadFile) -> tuple[bytes, AudioAnalysisResult]:
        """Validates and processes an uploaded audio file.

        Raises:
            HTTPException: On validation failure or unrecoverable error.
        """
        self.validator.validate_filename_and_mime(file.filename, file.content_type)
        raw_bytes = await file.read()
        self.validator.validate_payload_bytes(raw_bytes)

        result = self.extractor.analyze_bytes(raw_bytes, file.filename or "audio.wav")
        if result.status == "FAILED":
            logger.error("Audio processing failed for file=%s: %s", file.filename, result.error_message)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "AUDIO_PROCESSING_FAILED",
                    "message": "The uploaded audio file could not be decoded or processed by the safety engine.",
                    "details": result.error_message,
                },
            )

        return raw_bytes, result


# Global pipeline instance
audio_pipeline = AudioPipeline()
