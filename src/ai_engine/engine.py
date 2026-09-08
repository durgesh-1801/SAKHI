"""SAKHI AI / Risk Engine Core.

Coordinates signal validation, detector evaluation, weighted score aggregation,
score clamping [0, 100], risk level classification, and explainable reason generation.
"""

import logging

from .config import RiskEngineSettings, RiskThresholds
from .config import settings as default_settings
from .detectors.base import BaseDetector, DetectorStatus
from .detectors.rule_based import (
    AbnormalMotionDetector,
    DistressAudioDetector,
    DistressKeywordDetector,
    InactivityDetector,
    ManualSOSDetector,
    RouteDeviationDetector,
    SensorAnomalyDetector,
    SuddenFallDetector,
    SuddenRunningDetector,
    UserResponseDetector,
)
from .schemas import (
    AIAnalyzeResponse,
    RiskLevel,
    SignalDetail,
    SignalsPayload,
)

logger = logging.getLogger("sakhi.ai_engine.engine")


class RiskEngine:
    """Core AI Risk Engine for SAKHI.

    Processes multimodal safety signals, calculates explainable risk scores,
    and classifies danger levels without initiating emergency actions.
    """

    def __init__(self, config: RiskEngineSettings | None = None):
        self.config = config or default_settings
        self.detectors: dict[str, BaseDetector] = {}
        self._register_default_detectors()

    def _register_default_detectors(self) -> None:
        """Register the standard initial suite of signal detectors."""
        detectors = [
            ManualSOSDetector(),
            DistressAudioDetector(),
            DistressKeywordDetector(),
            SuddenFallDetector(),
            AbnormalMotionDetector(),
            SuddenRunningDetector(),
            RouteDeviationDetector(),
            InactivityDetector(),
            SensorAnomalyDetector(),
            UserResponseDetector(),
        ]
        for detector in detectors:
            self.register_detector(detector)

    def register_detector(self, detector: BaseDetector) -> None:
        """Register a new or replacement detector (e.g. future ML model)."""
        self.detectors[detector.signal_name] = detector
        logger.debug("Registered detector for signal: %s", detector.signal_name)

    def update_weights(self, new_weights: dict[str, float]) -> None:
        """Dynamically update signal weights in runtime configuration."""
        current_dict = self.config.weights.to_dict()
        current_dict.update(new_weights)
        self.config.weights = self.config.weights.__class__(**current_dict)

    def update_thresholds(
        self,
        safe_max: float | None = None,
        suspicious_max: float | None = None,
        high_max: float | None = None,
        critical_min: float | None = None,
    ) -> None:
        """Dynamically update classification thresholds with strict validation."""
        current_data = self.config.thresholds.model_dump()
        if safe_max is not None:
            current_data["safe_max"] = safe_max
        if suspicious_max is not None:
            current_data["suspicious_max"] = suspicious_max
        if high_max is not None:
            current_data["high_max"] = high_max
        if critical_min is not None:
            current_data["critical_min"] = critical_min
        self.config.thresholds = RiskThresholds(**current_data)

    def classify_risk(self, score: float) -> RiskLevel:
        """Classify a clamped risk score into a standard categorical RiskLevel.

        Classification thresholds:
        - score <= safe_max (default 30)         -> SAFE
        - score <= suspicious_max (default 60)   -> SUSPICIOUS
        - score <= high_max (default 80)         -> HIGH
        - score > high_max (default 81-100)      -> CRITICAL
        """
        thresholds = self.config.thresholds
        if score <= thresholds.safe_max:
            return RiskLevel.SAFE
        elif score <= thresholds.suspicious_max:
            return RiskLevel.SUSPICIOUS
        elif score <= thresholds.high_max:
            return RiskLevel.HIGH
        else:
            return RiskLevel.CRITICAL

    def analyze(self, signals: SignalsPayload) -> AIAnalyzeResponse:
        """Analyze incoming safety signals and return explainable risk assessment.

        Args:
            signals: Validated SignalsPayload object.

        Returns:
            AIAnalyzeResponse containing risk_score, risk_level, reasons,
            and signals_detected.
        """
        raw_score = 0.0
        reasons: list[str] = []
        signals_detected: list[str] = []
        details: dict[str, SignalDetail] = {}

        weights = self.config.weights.to_dict()

        for signal_name, detector in self.detectors.items():
            weight = weights.get(signal_name, 0.0)
            result = detector.evaluate(signals, weight)

            details[signal_name] = SignalDetail(
                signal_name=signal_name,
                detected=result.detected,
                weight_contributed=result.weight_contributed,
                confidence=result.confidence,
                reason=result.reason,
                status=result.status.value,
            )

            if result.status == DetectorStatus.SUCCESS and result.detected:
                raw_score += result.weight_contributed
                signals_detected.append(signal_name)
                if result.reason:
                    reasons.append(result.reason)
            elif result.status == DetectorStatus.FAILED:
                logger.warning(
                    "Detector '%s' reported failure during analysis: %s",
                    signal_name,
                    result.error_message,
                )

        # Clamping score strictly between min_score (0.0) and max_score (100.0)
        clamped_score = min(
            max(raw_score, self.config.min_score),
            self.config.max_score,
        )

        risk_level = self.classify_risk(clamped_score)

        return AIAnalyzeResponse(
            risk_score=round(clamped_score, 2),
            risk_level=risk_level,
            reasons=reasons,
            signals_detected=signals_detected,
            details=details,
        )
