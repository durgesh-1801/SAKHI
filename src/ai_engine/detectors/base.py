"""Base Detector Interface for SAKHI AI / Risk Engine.

Provides an extensible contract for all signal detectors (rule-based or future ML models).
Includes built-in safe failure handling so individual detector faults never crash the engine.
"""

from abc import ABC, abstractmethod
from enum import Enum
import logging
from typing import Optional
from pydantic import BaseModel
from ..schemas import SignalsPayload

logger = logging.getLogger("sakhi.ai_engine.detectors")


class DetectorStatus(str, Enum):
    """Execution status of an individual detector."""

    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class DetectionResult(BaseModel):
    """Standardized output produced by any signal detector."""

    signal_name: str
    detected: bool = False
    confidence: Optional[float] = None
    weight_contributed: float = 0.0
    reason: Optional[str] = None
    status: DetectorStatus = DetectorStatus.SUCCESS
    error_message: Optional[str] = None


class BaseDetector(ABC):
    """Abstract Base Class for all signal detectors.

    To replace a rule-based detector with an ML model in the future:
    1. Subclass BaseDetector.
    2. Implement _detect(payload, weight).
    3. Register the new detector class in the RiskEngine.
    """

    def __init__(self, signal_name: str, default_reason: str):
        self.signal_name = signal_name
        self.default_reason = default_reason

    def evaluate(self, payload: SignalsPayload, weight: float) -> DetectionResult:
        """Safely evaluates the detector on the incoming payload.

        Catches any unexpected internal exceptions, logs the diagnostic error safely,
        and returns a graceful FAILED result without raising an unhandled exception.
        A failed detector contributes 0 risk score and is NOT assumed to be in danger.
        """
        try:
            return self._detect(payload, weight)
        except Exception as exc:
            logger.error(
                "Detector %s failed during evaluation: %s",
                self.signal_name,
                str(exc),
                exc_info=True,
            )
            return DetectionResult(
                signal_name=self.signal_name,
                detected=False,
                confidence=None,
                weight_contributed=0.0,
                reason=None,
                status=DetectorStatus.FAILED,
                error_message=f"Detector error: {str(exc)}",
            )

    @abstractmethod
    def _detect(self, payload: SignalsPayload, weight: float) -> DetectionResult:
        """Internal detector logic implemented by concrete detector subclasses."""
        raise NotImplementedError
