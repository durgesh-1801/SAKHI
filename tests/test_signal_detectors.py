"""Unit tests for individual signal detectors.

Verifies detection rules, feature-based thresholds, and isolated failure behavior
for every supported safety signal detector in SAKHI.
"""

import pytest
from src.ai_engine.schemas import SignalsPayload
from src.ai_engine.detectors.base import BaseDetector, DetectionResult, DetectorStatus
from src.ai_engine.detectors.rule_based import (
    ManualSOSDetector,
    DistressAudioDetector,
    DistressKeywordDetector,
    SuddenFallDetector,
    AbnormalMotionDetector,
    SuddenRunningDetector,
    RouteDeviationDetector,
    InactivityDetector,
    SensorAnomalyDetector,
    UserResponseDetector,
)


def test_manual_sos_detector():
    detector = ManualSOSDetector()

    # Inactive
    res_false = detector.evaluate(SignalsPayload(manual_sos=False), weight=50.0)
    assert not res_false.detected
    assert res_false.weight_contributed == 0.0
    assert res_false.reason is None
    assert res_false.status == DetectorStatus.SUCCESS

    # Active
    res_true = detector.evaluate(SignalsPayload(manual_sos=True), weight=50.0)
    assert res_true.detected
    assert res_true.weight_contributed == 50.0
    assert res_true.reason == "Manual SOS triggered"
    assert res_true.status == DetectorStatus.SUCCESS


@pytest.mark.parametrize(
    "flag, confidence, expected_detected",
    [
        (False, None, False),
        (True, None, True),
        (False, 0.49, False),
        (False, 0.50, True),
        (False, 0.95, True),
        (True, 0.20, True),  # Flag takes precedence even if confidence is low
    ],
)
def test_distress_audio_detector(flag, confidence, expected_detected):
    detector = DistressAudioDetector(confidence_threshold=0.5)
    payload = SignalsPayload(distress_audio=flag, audio_confidence=confidence)
    res = detector.evaluate(payload, weight=35.0)

    assert res.detected == expected_detected
    if expected_detected:
        assert res.weight_contributed == 35.0
        assert res.reason == "Distress audio detected"
    else:
        assert res.weight_contributed == 0.0
        assert res.reason is None


@pytest.mark.parametrize(
    "flag, confidence, expected_detected",
    [
        (False, None, False),
        (True, None, True),
        (False, 0.49, False),
        (False, 0.50, True),
        (False, 0.88, True),
        (True, 0.10, True),
    ],
)
def test_distress_keyword_detector(flag, confidence, expected_detected):
    detector = DistressKeywordDetector(confidence_threshold=0.5)
    payload = SignalsPayload(distress_keywords=flag, keyword_confidence=confidence)
    res = detector.evaluate(payload, weight=25.0)

    assert res.detected == expected_detected
    if expected_detected:
        assert res.weight_contributed == 25.0
        assert res.reason == "Distress keywords detected"
    else:
        assert res.weight_contributed == 0.0


@pytest.mark.parametrize(
    "flag, confidence, expected_detected",
    [
        (False, None, False),
        (True, None, True),
        (False, 0.49, False),
        (False, 0.50, True),
        (False, 0.92, True),
    ],
)
def test_sudden_fall_detector(flag, confidence, expected_detected):
    detector = SuddenFallDetector(confidence_threshold=0.5)
    payload = SignalsPayload(sudden_fall=flag, fall_confidence=confidence)
    res = detector.evaluate(payload, weight=25.0)

    assert res.detected == expected_detected
    if expected_detected:
        assert res.weight_contributed == 25.0
        assert res.reason == "Sudden fall detected"


@pytest.mark.parametrize(
    "flag, score, expected_detected",
    [
        (False, None, False),
        (True, None, True),
        (False, 0.49, False),
        (False, 0.50, True),
        (False, 0.85, True),
    ],
)
def test_abnormal_motion_detector(flag, score, expected_detected):
    detector = AbnormalMotionDetector(score_threshold=0.5)
    payload = SignalsPayload(abnormal_motion=flag, motion_anomaly_score=score)
    res = detector.evaluate(payload, weight=15.0)

    assert res.detected == expected_detected
    if expected_detected:
        assert res.weight_contributed == 15.0
        assert res.reason == "Abnormal motion detected"


def test_sudden_running_detector():
    detector = SuddenRunningDetector()

    res_false = detector.evaluate(SignalsPayload(sudden_running=False), weight=15.0)
    assert not res_false.detected
    assert res_false.weight_contributed == 0.0

    res_true = detector.evaluate(SignalsPayload(sudden_running=True), weight=15.0)
    assert res_true.detected
    assert res_true.weight_contributed == 15.0
    assert res_true.reason == "Sudden running detected"


@pytest.mark.parametrize(
    "flag, score, expected_detected",
    [
        (False, None, False),
        (True, None, True),
        (False, 0.49, False),
        (False, 0.50, True),
        (False, 0.77, True),
    ],
)
def test_route_deviation_detector(flag, score, expected_detected):
    detector = RouteDeviationDetector(score_threshold=0.5)
    payload = SignalsPayload(route_deviation=flag, route_deviation_score=score)
    res = detector.evaluate(payload, weight=15.0)

    assert res.detected == expected_detected
    if expected_detected:
        assert res.weight_contributed == 15.0
        assert res.reason == "Route deviation detected"


def test_inactivity_detector():
    detector = InactivityDetector()

    res_false = detector.evaluate(SignalsPayload(inactivity=False), weight=15.0)
    assert not res_false.detected

    res_true = detector.evaluate(SignalsPayload(inactivity=True), weight=15.0)
    assert res_true.detected
    assert res_true.weight_contributed == 15.0
    assert res_true.reason == "Unusual inactivity detected"


def test_sensor_anomaly_detector():
    detector = SensorAnomalyDetector()

    res_false = detector.evaluate(SignalsPayload(sensor_anomalies=False), weight=10.0)
    assert not res_false.detected

    res_true = detector.evaluate(SignalsPayload(sensor_anomalies=True), weight=10.0)
    assert res_true.detected
    assert res_true.weight_contributed == 10.0
    assert res_true.reason == "Sensor anomalies detected"


def test_user_response_detector():
    detector = UserResponseDetector()

    res_false = detector.evaluate(SignalsPayload(no_response=False), weight=20.0)
    assert not res_false.detected

    res_true = detector.evaluate(SignalsPayload(no_response=True), weight=20.0)
    assert res_true.detected
    assert res_true.weight_contributed == 20.0
    assert res_true.reason == "No user response detected"


class ExceptionThrowingDetector(BaseDetector):
    def __init__(self, exc_to_raise: Exception):
        super().__init__("error_detector", "Error reason")
        self.exc_to_raise = exc_to_raise

    def _detect(self, payload: SignalsPayload, weight: float) -> DetectionResult:
        raise self.exc_to_raise


@pytest.mark.parametrize(
    "exception_instance",
    [
        ZeroDivisionError("division by zero"),
        ValueError("corrupt feature shape"),
        TypeError("unsupported operand type"),
        KeyError("missing embedded model key"),
    ],
)
def test_detector_safe_failure_on_various_exceptions(exception_instance):
    detector = ExceptionThrowingDetector(exception_instance)
    result = detector.evaluate(SignalsPayload(), weight=50.0)

    assert result.status == DetectorStatus.FAILED
    assert not result.detected
    assert result.weight_contributed == 0.0
    assert result.reason is None
    assert "Detector error:" in result.error_message
