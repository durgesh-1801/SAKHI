"""Rule-Based Detectors for SAKHI Safety Signals.

Each detector evaluates processed features / flags for a specific signal.
These rule-based implementations provide immediate, explainable heuristics
and can later be complemented or swapped with ML models (audio classification,
accelerometer gesture recognition, GPS anomaly models) adhering to BaseDetector.
"""

from typing import Optional
from .base import BaseDetector, DetectionResult, DetectorStatus
from ..schemas import SignalsPayload


class ManualSOSDetector(BaseDetector):
    """Detector for explicit user manual SOS trigger."""

    def __init__(self):
        super().__init__(
            signal_name="manual_sos",
            default_reason="Manual SOS triggered",
        )

    def _detect(self, payload: SignalsPayload, weight: float) -> DetectionResult:
        detected = bool(payload.manual_sos)
        return DetectionResult(
            signal_name=self.signal_name,
            detected=detected,
            confidence=1.0 if detected else 0.0,
            weight_contributed=weight if detected else 0.0,
            reason=self.default_reason if detected else None,
            status=DetectorStatus.SUCCESS,
        )


class DistressAudioDetector(BaseDetector):
    """Detector for distress sounds (screams, crying, loud struggle)."""

    def __init__(self, confidence_threshold: float = 0.5):
        super().__init__(
            signal_name="distress_audio",
            default_reason="Distress audio detected",
        )
        self.confidence_threshold = confidence_threshold

    def _detect(self, payload: SignalsPayload, weight: float) -> DetectionResult:
        detected = False
        confidence: Optional[float] = payload.audio_confidence

        if payload.distress_audio:
            detected = True
        elif confidence is not None and confidence >= self.confidence_threshold:
            detected = True

        return DetectionResult(
            signal_name=self.signal_name,
            detected=detected,
            confidence=confidence if confidence is not None else (1.0 if detected else 0.0),
            weight_contributed=weight if detected else 0.0,
            reason=self.default_reason if detected else None,
            status=DetectorStatus.SUCCESS,
        )


class DistressKeywordDetector(BaseDetector):
    """Detector for spoken distress keywords ('help', 'bachao', 'stop')."""

    def __init__(self, confidence_threshold: float = 0.5):
        super().__init__(
            signal_name="distress_keywords",
            default_reason="Distress keywords detected",
        )
        self.confidence_threshold = confidence_threshold

    def _detect(self, payload: SignalsPayload, weight: float) -> DetectionResult:
        detected = False
        confidence: Optional[float] = payload.keyword_confidence

        if payload.distress_keywords:
            detected = True
        elif confidence is not None and confidence >= self.confidence_threshold:
            detected = True

        return DetectionResult(
            signal_name=self.signal_name,
            detected=detected,
            confidence=confidence if confidence is not None else (1.0 if detected else 0.0),
            weight_contributed=weight if detected else 0.0,
            reason=self.default_reason if detected else None,
            status=DetectorStatus.SUCCESS,
        )


class SuddenFallDetector(BaseDetector):
    """Detector for sudden fall / impact motion signatures."""

    def __init__(self, confidence_threshold: float = 0.5):
        super().__init__(
            signal_name="sudden_fall",
            default_reason="Sudden fall detected",
        )
        self.confidence_threshold = confidence_threshold

    def _detect(self, payload: SignalsPayload, weight: float) -> DetectionResult:
        detected = False
        confidence: Optional[float] = payload.fall_confidence

        if payload.sudden_fall:
            detected = True
        elif confidence is not None and confidence >= self.confidence_threshold:
            detected = True

        return DetectionResult(
            signal_name=self.signal_name,
            detected=detected,
            confidence=confidence if confidence is not None else (1.0 if detected else 0.0),
            weight_contributed=weight if detected else 0.0,
            reason=self.default_reason if detected else None,
            status=DetectorStatus.SUCCESS,
        )


class AbnormalMotionDetector(BaseDetector):
    """Detector for erratic motion or struggling dynamics."""

    def __init__(self, score_threshold: float = 0.5):
        super().__init__(
            signal_name="abnormal_motion",
            default_reason="Abnormal motion detected",
        )
        self.score_threshold = score_threshold

    def _detect(self, payload: SignalsPayload, weight: float) -> DetectionResult:
        detected = False
        score: Optional[float] = payload.motion_anomaly_score

        if payload.abnormal_motion:
            detected = True
        elif score is not None and score >= self.score_threshold:
            detected = True

        return DetectionResult(
            signal_name=self.signal_name,
            detected=detected,
            confidence=score if score is not None else (1.0 if detected else 0.0),
            weight_contributed=weight if detected else 0.0,
            reason=self.default_reason if detected else None,
            status=DetectorStatus.SUCCESS,
        )


class SuddenRunningDetector(BaseDetector):
    """Detector for sudden running or fleeing."""

    def __init__(self):
        super().__init__(
            signal_name="sudden_running",
            default_reason="Sudden running detected",
        )

    def _detect(self, payload: SignalsPayload, weight: float) -> DetectionResult:
        detected = bool(payload.sudden_running)
        return DetectionResult(
            signal_name=self.signal_name,
            detected=detected,
            confidence=1.0 if detected else 0.0,
            weight_contributed=weight if detected else 0.0,
            reason=self.default_reason if detected else None,
            status=DetectorStatus.SUCCESS,
        )


class RouteDeviationDetector(BaseDetector):
    """Detector for unexpected deviation from journey path."""

    def __init__(self, score_threshold: float = 0.5):
        super().__init__(
            signal_name="route_deviation",
            default_reason="Route deviation detected",
        )
        self.score_threshold = score_threshold

    def _detect(self, payload: SignalsPayload, weight: float) -> DetectionResult:
        detected = False
        score: Optional[float] = payload.route_deviation_score

        if payload.route_deviation:
            detected = True
        elif score is not None and score >= self.score_threshold:
            detected = True

        return DetectionResult(
            signal_name=self.signal_name,
            detected=detected,
            confidence=score if score is not None else (1.0 if detected else 0.0),
            weight_contributed=weight if detected else 0.0,
            reason=self.default_reason if detected else None,
            status=DetectorStatus.SUCCESS,
        )


class InactivityDetector(BaseDetector):
    """Detector for prolonged unexpected inactivity during journey."""

    def __init__(self):
        super().__init__(
            signal_name="inactivity",
            default_reason="Unusual inactivity detected",
        )

    def _detect(self, payload: SignalsPayload, weight: float) -> DetectionResult:
        detected = bool(payload.inactivity)
        return DetectionResult(
            signal_name=self.signal_name,
            detected=detected,
            confidence=1.0 if detected else 0.0,
            weight_contributed=weight if detected else 0.0,
            reason=self.default_reason if detected else None,
            status=DetectorStatus.SUCCESS,
        )


class SensorAnomalyDetector(BaseDetector):
    """Detector for environmental or device sensor anomalies."""

    def __init__(self):
        super().__init__(
            signal_name="sensor_anomalies",
            default_reason="Sensor anomalies detected",
        )

    def _detect(self, payload: SignalsPayload, weight: float) -> DetectionResult:
        detected = bool(payload.sensor_anomalies)
        return DetectionResult(
            signal_name=self.signal_name,
            detected=detected,
            confidence=1.0 if detected else 0.0,
            weight_contributed=weight if detected else 0.0,
            reason=self.default_reason if detected else None,
            status=DetectorStatus.SUCCESS,
        )


class UserResponseDetector(BaseDetector):
    """Detector for user failing to respond to verification prompt."""

    def __init__(self):
        super().__init__(
            signal_name="no_response",
            default_reason="No user response detected",
        )

    def _detect(self, payload: SignalsPayload, weight: float) -> DetectionResult:
        detected = bool(payload.no_response)
        return DetectionResult(
            signal_name=self.signal_name,
            detected=detected,
            confidence=1.0 if detected else 0.0,
            weight_contributed=weight if detected else 0.0,
            reason=self.default_reason if detected else None,
            status=DetectorStatus.SUCCESS,
        )
