# 🧠 SAKHI AI / Risk Engine Documentation

> **Service Responsibility**: AI / Risk Engine Microservice (Backend Engineer 1)  
> **Boundary Notice**: This service is **strictly an analysis service**. It does **NOT** call emergency numbers (112), send SMS, dispatch notifications, or manage user consent. It evaluates multimodal safety signals and returns risk scores, levels, and explainable reasons to downstream policy services.

---

## 1. Overview & Architecture

The SAKHI AI / Risk Engine processes multiple safety signals, applies configurable weighted scoring, and classifies the severity of potential danger into standardized risk levels.

```
Potential Danger
       ↓
Multiple Safety Signals (Processed Features)
       ↓
[POST /ai/analyze]
       ↓
Signal Validation (Type, Range, Extra-Field Rejection)
       ↓
Modular Detectors (BaseDetector Interface)
       ↓
Risk Engine (Configurable Weights & Thresholds)
       ↓
Score Clamping [0, 100]
       ↓
Risk Classification (SAFE, SUSPICIOUS, HIGH, CRITICAL)
       ↓
Explainable Reason Generation
       ↓
Stable API Response Contract
       ↓
Downstream Consent & Safety Policy Service (Handled by other services)
       ↓
Emergency Action (Handled by other services)
```

---

## 2. Important Engineering Disclaimer: No Fake AI

> [!IMPORTANT]
> The initial risk scoring implementation uses a **configurable, rule-based heuristic scoring system**.
> It is **NOT** a scientifically validated ML model, nor does it claim infallible danger prediction.
> It has been designed with modular detector abstractions (`BaseDetector`) so individual detectors can be seamlessly swapped or augmented with trained ML models (e.g., audio distress classifiers, sensor-based fall networks, route anomaly algorithms) as datasets are acquired.

---

## 3. Signal Definitions & Initial Weights

Weights are positive contributions towards risk severity. All weights are centralized in `src/ai_engine/config.py` and can be dynamically configured.

| Signal | Initial Weight | Description | Feature Representation |
|---|---|---|---|
| `manual_sos` | +50 | User pressed the SOS button explicitly | Boolean flag |
| `distress_audio` | +35 | Scream, struggle, or acoustic distress | Boolean flag / `audio_confidence` (0.0-1.0) |
| `distress_keywords` | +25 | Spoken distress phrases ("help", "bachao") | Boolean flag / `keyword_confidence` (0.0-1.0) |
| `sudden_fall` | +25 | Sudden impact drop detected via accelerometer | Boolean flag / `fall_confidence` (0.0-1.0) |
| `abnormal_motion` | +15 | Erratic motion, struggle dynamics | Boolean flag / `motion_anomaly_score` (0.0-1.0) |
| `sudden_running` | +15 | Transition to sudden high-speed fleeing | Boolean flag |
| `route_deviation` | +15 | Deviation from expected journey path | Boolean flag / `route_deviation_score` (0.0-1.0) |
| `inactivity` | +15 | Prolonged lack of movement during trip | Boolean flag |
| `sensor_anomalies` | +10 | Environmental sensor anomalies | Boolean flag |
| `no_response` | +20 | User failed to respond to verification prompt | Boolean flag |

### Score Calculation:
$$\text{Raw Score} = \sum (\text{Active Signal Weights})$$
$$\text{Risk Score} = \min(\max(\text{Raw Score}, 0.0), 100.0)$$

---

## 4. Risk Classification Thresholds

The clamped risk score is classified into four standard levels:

| Score Range | Risk Level | Meaning | Downstream System Recommendation |
|---|---|---|---|
| **0 – 30** | `SAFE` | Normal conditions; minimal or benign anomalies | No escalation; normal monitoring |
| **31 – 60** | `SUSPICIOUS` | Single strong indicator or low-confidence anomalies | Trigger safety verification check ("Are you safe?") |
| **61 – 80** | `HIGH` | Multiple correlating indicators | Fast-track verification; prepare guardian notification |
| **81 – 100** | `CRITICAL` | Manual SOS or multiple high-severity distress signals | Immediate execution of user's pre-configured emergency policy |

---

## 5. Integration Contract (For Backend Engineers 2 & 3)

### Endpoint
`POST /ai/analyze`  
*(Alias: `POST /api/v1/ai/analyze`)*

### Request Format
```json
{
  "user_id": "usr_98723",
  "signals": {
    "manual_sos": false,
    "distress_audio": true,
    "audio_confidence": 0.88,
    "sudden_fall": true,
    "fall_confidence": 0.92,
    "abnormal_motion": true,
    "route_deviation": false,
    "no_response": true
  },
  "timestamp": "2026-09-08T16:20:00Z"
}
```

### Response Format (Guaranteed Stable Contract)
```json
{
  "risk_score": 95.0,
  "risk_level": "CRITICAL",
  "reasons": [
    "Distress audio detected",
    "Sudden fall detected",
    "Abnormal motion detected",
    "No user response detected"
  ],
  "signals_detected": [
    "distress_audio",
    "sudden_fall",
    "abnormal_motion",
    "no_response"
  ]
}
```

### Error Responses

#### 422 Unprocessable Content (Validation Failure)
Returned when confidence is out-of-range (<0 or >1), types are mismatched, required fields are absent, or unknown keys are passed:
```json
{
  "error": "Validation Error",
  "message": "Incoming signal payload contains invalid types, out-of-range values, or unknown fields.",
  "details": [
    {
      "field": "signals -> audio_confidence",
      "message": "Input should be less than or equal to 1",
      "type": "less_than_equal"
    }
  ]
}
```

---

## 6. Privacy Requirements & Data Minimization

The AI Risk Engine implements **Privacy by Design**:
- **No Raw Audio Storage**: The engine consumes derived features (`distress_audio: bool`, `audio_confidence: float`). Never pass raw `.wav` or stream audio to this service.
- **No Raw Sensor Streams**: Raw high-frequency IMU/gyroscope streams are processed on-device or at the sensor gateway; only derived motion flags/anomaly scores reach the AI engine.
- **No Continuous Location Tracking**: The engine receives journey anomaly indicators (`route_deviation: bool`, `route_deviation_score: float`), not raw GPS coordinates.
- **No PII Logging**: Logging records only `user_id`, computed score, risk level, and detected signal IDs for auditability.

---

## 7. Future ML Extension Architecture

To upgrade any detector to an ML model (e.g., ONNX model, Whisper audio classifier):

1. **Implement `BaseDetector`**:
   ```python
   from ai_engine.detectors.base import BaseDetector, DetectionResult, DetectorStatus

   class MLDressAudioDetector(BaseDetector):
       def __init__(self, model_path: str):
           super().__init__("distress_audio", "Distress audio detected")
           self.model = load_onnx_model(model_path)

       def _detect(self, payload, weight) -> DetectionResult:
           confidence = self.model.predict(payload.audio_features)
           detected = confidence >= 0.75
           return DetectionResult(
               signal_name=self.signal_name,
               detected=detected,
               confidence=confidence,
               weight_contributed=weight if detected else 0.0,
               reason=self.default_reason if detected else None,
               status=DetectorStatus.SUCCESS,
           )
   ```
2. **Register in `RiskEngine`**:
   ```python
   engine.register_detector(MLDressAudioDetector(model_path="models/audio_v1.onnx"))
   ```
3. The rest of the pipeline (clamping, threshold classification, explainability, API contract) continues unchanged.

---

## 8. Speech-to-Text (STT) & Audio Distress Pipeline

The AI Risk Engine features an integrated Speech-to-Text (STT) pipeline using **`faster-whisper`** (v1.2.1) for local, offline transcription and distress keyword recognition.

### Pipeline Flow:
```
Audio Upload (.wav, .mp3, .m4a, .ogg, .flac)
       ↓
Filename & MIME validation (max 10MB ceiling)
       ↓
Backend 2 Consent Check (ai_detection_permitted, audio_analysis_permitted)
       ↓
Byte & Integrity Validation
       ↓
Acoustic Distress Extraction (energy/amplitude scream heuristic: +35.0 weight)
       ↓
Offline Whisper STT Inference (faster-whisper)
       ↓
Multilingual Distress Keyword Detection (English + Hindi/Hinglish: +25.0 weight)
       ↓
Existing Risk Engine Evaluation (clamped 0–100 score)
       ↓
Explainable Risk Assessment
```

### Configuration Concepts:
All Whisper settings are configurable via environment variables:
- `WHISPER_MODEL_SIZE` (default: `"tiny"`): Whisper model variant (`tiny`, `base`, `small`, `medium`, `large-v3`).
- `WHISPER_MODEL_PATH` (default: `None`): Local custom directory or HuggingFace repo path.
- `WHISPER_DEVICE` (default: `"cpu"`): Inference device (`cpu` or `cuda`).
- `WHISPER_COMPUTE_TYPE` (default: `"int8"`): Quantization type (`int8`, `float16`, `float32`).
- `WHISPER_LANGUAGE` (default: `None`/`"auto"`): Spoken language code or automatic detection.

### Privacy & Safety Guarantees:
- **No Raw Audio Persistence**: Audio bytes are held in secure temporary storage only during inference and deterministically unlinked in `try...finally` blocks.
- **No Transcript Storage**: Full transcripts are never saved to any database or external cloud service.
- **No Sensitive Transcript Logging**: Audit logs record speech metadata (duration, detected language, character count, keyword flags), never raw user utterances.
- **Fail-Safe Integrity**: Whisper errors, corrupted audio payloads, or missing models explicitly raise HTTP 422/500 errors and **NEVER** silently default to `SAFE`.

---

## 9. Limitations

1. **Rule-Based Baseline**: Initial weights are heuristic defaults and require tuning as real-world anonymized user feedback and test simulations become available.
2. **Deterministic Inputs**: The engine relies on accurate feature signals from edge devices / upstream sensor processors.
3. **No Autonomous Dispatch**: The engine does not interact with emergency services. Downstream services must handle consent and verification flows.
4. **Local Hardware Constraints**: Offline Whisper CPU inference latency scales with audio length and model size (`tiny` recommended for low-latency local execution).
