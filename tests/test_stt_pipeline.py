"""Comprehensive Test Suite for Whisper Speech-to-Text (STT) Pipeline in SAKHI Backend 1.

Covers:
1. Whisper model lazy initialization.
2. Valid audio produces transcription and keyword detection.
3. Empty audio handled correctly (rejected prior to STT).
4. Invalid/corrupt audio handled correctly (HTTP 422, never silently SAFE).
5. audio_analysis_permitted=False prevents Whisper execution.
6. ai_detection_permitted=False prevents analysis (HTTP 403).
7. Whisper transcription feeds existing DistressKeywordDetector.
8. Distress keywords affect existing risk engine scoring and explainability.
9. Whisper failure does not silently return SAFE.
10. No raw audio is persisted (temporary files cleaned up).
11. Privacy: No sensitive transcripts leaked to standard logs.
12. Existing RiskAssessment schema contract remains fully compatible.
"""

import io
import logging
import wave
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.schemas.consent import ConsentUpdate
from app.services.consent_service import consent_service
from src.ai_engine.config import WhisperSettings
from src.ai_engine.schemas import AIAnalyzeResponse, RiskLevel
from src.ai_engine.stt_service import (
    SpeechToTextService,
    STTProcessingError,
    TranscriptionResult,
)


def make_synthetic_wav(duration_seconds: float = 0.5, sample_rate: int = 16000) -> bytes:
    """Generates a valid minimal WAV file with silence."""
    num_samples = int(duration_seconds * sample_rate)
    pcm_bytes = b"\x00\x00" * num_samples
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()


# --------------------------------------------------------------------------
# 1. Whisper Model Initialization & Configuration
# --------------------------------------------------------------------------


def test_whisper_lazy_initialization():
    """STT service must NOT initialize the heavy model at instantiation time."""
    custom_settings = WhisperSettings(model_size="tiny", device="cpu", compute_type="int8")
    service = SpeechToTextService(config=custom_settings)
    # Model should be uninitialized until accessed
    assert service._model is None


def test_whisper_configuration_override():
    """STT configuration respects custom settings."""
    custom_settings = WhisperSettings(
        model_size="base",
        device="cpu",
        compute_type="int8",
        language="hi",
        enabled=False,
    )
    service = SpeechToTextService(config=custom_settings)
    assert service.config.model_size == "base"
    assert service.config.language == "hi"
    assert service.config.enabled is False


# --------------------------------------------------------------------------
# 2. Keyword Detection & Transcription Logic
# --------------------------------------------------------------------------


def test_distress_keyword_detector_lexicon():
    """Detects spoken English and Hindi distress keywords correctly."""
    # English matches
    detected, conf, keywords = SpeechToTextService.detect_distress_keywords("Please help me someone is following me")
    assert detected is True
    assert conf >= 0.75
    assert any(k in ["help", "help me", "please help", "following me"] for k in keywords)

    # Hindi / Hinglish matches
    detected_hi, conf_hi, keywords_hi = SpeechToTextService.detect_distress_keywords("mujhe bachao please police bulao")
    assert detected_hi is True
    assert conf_hi >= 0.75
    assert any(k in ["bachao", "mujhe bachao", "police bulao"] for k in keywords_hi)

    # Neutral speech
    neutral_detected, neutral_conf, neutral_kws = SpeechToTextService.detect_distress_keywords("the weather is pleasant today")
    assert neutral_detected is False
    assert neutral_conf == 0.0
    assert neutral_kws == []


def test_transcription_result_structure():
    """TranscriptionResult contains required structured metadata."""
    res = TranscriptionResult(
        text="Help me please",
        language="en",
        confidence=0.92,
        duration=2.4,
        keywords_detected=["help", "help me"],
        distress_detected=True,
        keyword_confidence=0.85,
    )
    assert res.text == "Help me please"
    assert res.language == "en"
    assert res.confidence == 0.92
    assert res.duration == 2.4
    assert res.distress_detected is True
    assert res.keywords_detected == ["help", "help me"]


# --------------------------------------------------------------------------
# 3. Empty Audio Handling
# --------------------------------------------------------------------------


def test_empty_audio_rejected_before_stt(client: TestClient, user_a, db_session):
    """Empty audio file (0 bytes) is rejected with HTTP 400 before STT inference."""
    consent_service.update_consent(
        db_session,
        user_a.id,
        ConsentUpdate(ai_detection=True, audio_analysis=True),
    )
    empty_file = io.BytesIO(b"")
    response = client.post(
        "/api/v1/ai/analyze-audio",
        data={"user_id": user_a.id},
        files={"file": ("empty.wav", empty_file, "audio/wav")},
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["error"] == "EMPTY_AUDIO"


def test_stt_service_rejects_empty_bytes():
    """SpeechToTextService.transcribe explicitly raises STTProcessingError on empty bytes."""
    service = SpeechToTextService()
    with pytest.raises(STTProcessingError) as exc_info:
        service.transcribe(b"", "empty.wav")
    assert "empty audio payload" in str(exc_info.value).lower()


# --------------------------------------------------------------------------
# 4. Corrupt / Invalid Audio Handling (Never silently SAFE)
# --------------------------------------------------------------------------


def test_corrupt_audio_raises_422(client: TestClient, user_a, db_session):
    """Corrupted audio payload raises HTTP 422 and does NOT return a fabricated SAFE assessment."""
    consent_service.update_consent(
        db_session,
        user_a.id,
        ConsentUpdate(ai_detection=True, audio_analysis=True),
    )
    corrupt_bytes = b"CORRUPTED_NON_AUDIO_BYTES_PAYLOAD" * 50
    corrupt_file = io.BytesIO(corrupt_bytes)

    response = client.post(
        "/api/v1/ai/analyze-audio",
        data={"user_id": user_a.id},
        files={"file": ("bad_file.mp3", corrupt_file, "audio/mp3")},
    )
    assert response.status_code == 422
    data = response.json()
    assert "error" in data["detail"]
    # Never return 200 with risk_score = 0
    assert response.status_code != 200


# --------------------------------------------------------------------------
# 5. Consent Enforcement for Audio Analysis & AI Detection
# --------------------------------------------------------------------------


def test_audio_analysis_forbidden_stops_stt(client: TestClient, user_a, db_session):
    """If audio_analysis_permitted=False, STT pipeline is NEVER called and returns 403."""
    consent_service.update_consent(
        db_session,
        user_a.id,
        ConsentUpdate(ai_detection=True, audio_analysis=False),
    )

    wav_bytes = make_synthetic_wav(0.2)
    with patch("src.ai_engine.stt_service.SpeechToTextService.transcribe") as mock_transcribe:
        response = client.post(
            "/api/v1/ai/analyze-audio",
            data={"user_id": user_a.id},
            files={"file": ("test.wav", io.BytesIO(wav_bytes), "audio/wav")},
        )
        assert response.status_code == 403
        assert "AUDIO_ANALYSIS_NOT_PERMITTED" in response.json()["detail"]["error"]
        # STT must NOT have been called
        mock_transcribe.assert_not_called()


def test_ai_detection_forbidden_aborts_audio_endpoint(client: TestClient, user_a, db_session):
    """If ai_detection_permitted=False, audio endpoint aborts with 403 before processing."""
    consent_service.update_consent(
        db_session,
        user_a.id,
        ConsentUpdate(ai_detection=False, audio_analysis=True),
    )

    wav_bytes = make_synthetic_wav(0.2)
    with patch("src.ai_engine.stt_service.SpeechToTextService.transcribe") as mock_transcribe:
        response = client.post(
            "/api/v1/ai/analyze-audio",
            data={"user_id": user_a.id},
            files={"file": ("test.wav", io.BytesIO(wav_bytes), "audio/wav")},
        )
        assert response.status_code == 403
        assert "AI_CONSENT_REVOKED" in response.json()["detail"]["error"]
        mock_transcribe.assert_not_called()


# --------------------------------------------------------------------------
# 6. Whisper Transcription Feeds Existing Keyword Detector & Risk Engine
# --------------------------------------------------------------------------


def test_whisper_transcription_feeds_keyword_detector_and_elevates_risk(
    client: TestClient, user_a, db_session
):
    """Spoken distress keywords detected by Whisper feed DistressKeywordDetector and elevate risk score."""
    consent_service.update_consent(
        db_session,
        user_a.id,
        ConsentUpdate(ai_detection=True, audio_analysis=True),
    )
    wav_bytes = make_synthetic_wav(0.5)

    mock_stt_result = TranscriptionResult(
        text="Please help me someone is following me",
        language="en",
        confidence=0.91,
        duration=0.5,
        keywords_detected=["help", "following me"],
        distress_detected=True,
        keyword_confidence=0.85,
    )

    with patch("src.ai_engine.audio_pipeline.stt_service.transcribe", return_value=mock_stt_result):
        response = client.post(
            "/api/v1/ai/analyze-audio",
            data={"user_id": user_a.id, "sudden_fall": False},
            files={"file": ("safety_recording.wav", io.BytesIO(wav_bytes), "audio/wav")},
        )
        assert response.status_code == 200
        data = response.json()

        # Distress keywords weight is 25.0
        assert data["risk_score"] == 25.0
        assert data["risk_level"] == "SAFE"  # 0-30 is SAFE
        assert "distress_keywords" in data["signals_detected"]
        assert "Distress keywords detected" in data["reasons"]


def test_acoustic_plus_distress_keywords_elevates_to_suspicious(
    client: TestClient, user_a, db_session
):
    """Acoustic distress (35.0) + Spoken distress keywords (25.0) = 60.0 (SUSPICIOUS)."""
    consent_service.update_consent(
        db_session,
        user_a.id,
        ConsentUpdate(ai_detection=True, audio_analysis=True),
    )
    wav_bytes = make_synthetic_wav(0.5)

    mock_stt_result = TranscriptionResult(
        text="Bachao mujhe bachao",
        language="hi",
        confidence=0.89,
        duration=0.5,
        keywords_detected=["bachao", "mujhe bachao"],
        distress_detected=True,
        keyword_confidence=0.85,
    )

    with (
        patch("src.ai_engine.audio_pipeline.stt_service.transcribe", return_value=mock_stt_result),
        patch(
            "src.ai_engine.audio_pipeline.AcousticDistressExtractor.analyze_bytes",
            return_value=MagicMock(
                distress_detected=True,
                confidence=0.80,
                rms_energy=500.0,
                status="SUCCESS",
            ),
        ),
    ):
        response = client.post(
            "/api/v1/ai/analyze-audio",
            data={"user_id": user_a.id},
            files={"file": ("audio.wav", io.BytesIO(wav_bytes), "audio/wav")},
        )
        assert response.status_code == 200
        data = response.json()

        # Acoustic distress (35) + Distress keywords (25) = 60.0 -> SUSPICIOUS
        assert data["risk_score"] == 60.0
        assert data["risk_level"] == "SUSPICIOUS"
        assert "distress_audio" in data["signals_detected"]
        assert "distress_keywords" in data["signals_detected"]
        assert "Distress audio detected" in data["reasons"]
        assert "Distress keywords detected" in data["reasons"]


def test_acoustic_plus_keywords_plus_fall_elevates_to_critical(
    client: TestClient, user_a, db_session
):
    """Acoustic distress (35) + Keywords (25) + Sudden Fall (25) = 85.0 (CRITICAL)."""
    consent_service.update_consent(
        db_session,
        user_a.id,
        ConsentUpdate(ai_detection=True, audio_analysis=True),
    )
    wav_bytes = make_synthetic_wav(0.5)

    mock_stt_result = TranscriptionResult(
        text="Help me",
        language="en",
        confidence=0.95,
        duration=0.5,
        keywords_detected=["help", "help me"],
        distress_detected=True,
        keyword_confidence=0.90,
    )

    with (
        patch("src.ai_engine.audio_pipeline.stt_service.transcribe", return_value=mock_stt_result),
        patch(
            "src.ai_engine.audio_pipeline.AcousticDistressExtractor.analyze_bytes",
            return_value=MagicMock(
                distress_detected=True,
                confidence=0.85,
                rms_energy=600.0,
                status="SUCCESS",
            ),
        ),
    ):
        response = client.post(
            "/api/v1/ai/analyze-audio",
            data={"user_id": user_a.id, "sudden_fall": True},
            files={"file": ("audio.wav", io.BytesIO(wav_bytes), "audio/wav")},
        )
        assert response.status_code == 200
        data = response.json()

        # 35 + 25 + 25 = 85.0 -> CRITICAL
        assert data["risk_score"] == 85.0
        assert data["risk_level"] == "CRITICAL"
        assert set(data["signals_detected"]) == {"distress_audio", "distress_keywords", "sudden_fall"}


# --------------------------------------------------------------------------
# 7. STT Failure Handling (Never silently returns SAFE)
# --------------------------------------------------------------------------


def test_stt_failure_does_not_silently_return_safe(client: TestClient, user_a, db_session):
    """When Whisper STT crashes or raises STTProcessingError, endpoint returns HTTP 422."""
    consent_service.update_consent(
        db_session,
        user_a.id,
        ConsentUpdate(ai_detection=True, audio_analysis=True),
    )
    wav_bytes = make_synthetic_wav(0.2)

    with patch(
        "src.ai_engine.audio_pipeline.stt_service.transcribe",
        side_effect=STTProcessingError("Model failed during audio token decoding"),
    ):
        response = client.post(
            "/api/v1/ai/analyze-audio",
            data={"user_id": user_a.id},
            files={"file": ("audio.wav", io.BytesIO(wav_bytes), "audio/wav")},
        )
        # Must return explicit error, NEVER 200 SAFE
        assert response.status_code == 422
        detail = response.json()["detail"]
        assert detail["error"] == "STT_TRANSCRIPTION_FAILED"


# --------------------------------------------------------------------------
# 8. Privacy: No Raw Audio Persisted, Temp Files Deleted
# --------------------------------------------------------------------------


def test_temp_file_guaranteed_cleanup():
    """Temporary audio file is strictly unlinked after STT inference, even on error."""
    import os

    service = SpeechToTextService()
    # Mock _get_model to simulate transcription error
    mock_model = MagicMock()
    mock_model.transcribe.side_effect = RuntimeError("Simulated internal error")

    created_paths = []
    real_named_temp = __import__("tempfile").NamedTemporaryFile

    def tracking_temp_file(*args, **kwargs):
        tf = real_named_temp(*args, **kwargs)
        created_paths.append(tf.name)
        return tf

    wav_bytes = make_synthetic_wav(0.1)
    with (
        patch.object(service, "_get_model", return_value=mock_model),
        patch("tempfile.NamedTemporaryFile", side_effect=tracking_temp_file),
        pytest.raises(STTProcessingError),
    ):
        service.transcribe(wav_bytes, "test.wav")

    # Verify temp file was cleaned up
    assert len(created_paths) == 1
    assert not os.path.exists(created_paths[0]), f"Temp file was leaked: {created_paths[0]}"


# --------------------------------------------------------------------------
# 9. Privacy: No Full Sensitive Transcripts in Standard Logs
# --------------------------------------------------------------------------


def test_no_sensitive_transcript_logged(caplog):
    """Standard STT log messages record metadata (duration, lang, length) but not full raw text."""
    service = SpeechToTextService()
    sensitive_speech = "My secret PIN is 1234 and I am hiding at 5th avenue"

    mock_segment = MagicMock()
    mock_segment.text = sensitive_speech
    mock_segment.avg_logprob = -0.15

    mock_info = MagicMock()
    mock_info.language = "en"
    mock_info.duration = 2.5

    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([mock_segment], mock_info)

    with (
        patch.object(service, "_get_model", return_value=mock_model),
        caplog.at_level(logging.INFO, logger="sakhi.ai_engine.stt"),
    ):
        wav_bytes = make_synthetic_wav(0.2)
        service.transcribe(wav_bytes, "test.wav")

        # The full sensitive text must NOT appear in the log output
        for record in caplog.records:
            assert sensitive_speech not in record.message


# --------------------------------------------------------------------------
# 10. Schema Stability Contract for Backend 2 / 3
# --------------------------------------------------------------------------


def test_risk_assessment_schema_remains_compatible(client: TestClient, user_a, db_session):
    """Response adheres strictly to AIAnalyzeResponse schema contract."""
    consent_service.update_consent(
        db_session,
        user_a.id,
        ConsentUpdate(ai_detection=True, audio_analysis=True),
    )
    wav_bytes = make_synthetic_wav(0.2)
    mock_stt_result = TranscriptionResult(
        text="",
        language="en",
        confidence=None,
        duration=0.2,
        keywords_detected=[],
        distress_detected=False,
        keyword_confidence=None,
    )

    with patch("src.ai_engine.audio_pipeline.stt_service.transcribe", return_value=mock_stt_result):
        response = client.post(
            "/api/v1/ai/analyze-audio",
            data={"user_id": user_a.id},
            files={"file": ("test.wav", io.BytesIO(wav_bytes), "audio/wav")},
        )
        assert response.status_code == 200
        # Parse against pydantic schema to verify validation succeeds
        parsed = AIAnalyzeResponse(**response.json())
        assert isinstance(parsed.risk_score, float)
        assert isinstance(parsed.risk_level, RiskLevel)
        assert isinstance(parsed.reasons, list)
        assert isinstance(parsed.signals_detected, list)
