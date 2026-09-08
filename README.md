<div align="center">

# 🛡️ SAKHI

### AI-Powered Real-Time Women Safety & Emergency Response System

**Detect. Verify. Respond.**

[![Status](https://img.shields.io/badge/status-in%20development-orange)](#)
[![License](https://img.shields.io/badge/license-MIT-blue)](#license)
[![Consent First](https://img.shields.io/badge/design-consent--first-brightgreen)](#-consent-first-design)
[![Made with ❤️](https://img.shields.io/badge/made%20with-%E2%9D%A4%EF%B8%8F-red)](#)

</div>

---

## 📖 Table of Contents

- [What is SAKHI?](#-what-is-sakhi)
- [Core Product Philosophy](#-core-product-philosophy)
  - [Detect](#-detect)
  - [Verify](#-verify)
  - [Respond](#-respond)
- [Consent-First Design](#-consent-first-design)
- [Safe Journey Mode](#-safe-journey-mode)
- [AI Risk Engine](#-ai-risk-engine)
- [Design Principles](#-design-principles)
- [Roadmap](#-roadmap)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🌸 What is SAKHI?

**SAKHI** is an AI-powered, **consent-driven**, real-time safety system designed to help a person seek assistance during potentially unsafe situations — especially in moments where they may not be able to manually press an SOS button, unlock their phone, make a call, or clearly communicate that they are in danger.

Traditional safety apps typically follow a purely reactive flow:

```
User detects danger → User opens app → User presses SOS → Emergency contact notified
```

This model assumes the user is *always* able to act. SAKHI is built for the moments when they can't.

```
Potential danger
      ↓
AI detects unusual/distress signals
      ↓
Risk is assessed
      ↓
User is asked for verification
      ↓
Consent & emergency policy are checked
      ↓
Appropriate action is triggered
      ↓
Trusted contacts receive assistance information
```

> **Core philosophy:** SAKHI does not attempt to replace the user's judgment. It assists the user when they may be unable to act themselves — and it remains **consent-driven and privacy-conscious** at every step.

---

## 🧭 Core Product Philosophy

SAKHI operates in three core stages: **Detect → Verify → Respond**.

### 🔍 Detect

SAKHI identifies potential indicators of an unsafe situation using multiple, complementary signals:

| Category | Signals |
|---|---|
| Manual | Manual SOS trigger |
| Audio | Distress audio, scream/distress detection, voice keywords |
| Motion | Sudden fall, abnormal motion, sudden running, unusual inactivity, phone movement/drop |
| Context | Route deviation, location/context anomalies |
| Future | Wearable / external sensor signals |

⚠️ These signals do **not** claim to definitively prove that an attack is occurring. Instead, they feed into a **Potential Safety Risk Assessment** — a probabilistic signal, not a verdict.

### ✅ Verify

Wherever possible, SAKHI verifies the user's safety **before** escalating automatically.

> *"Are you safe?"*

The user can:
- ✅ Confirm they are safe
- 🆘 Request help
- ⏳ Ignore / respond later
- 🔇 Trigger a silent emergency action

If there's no response within the user's configured verification window, SAKHI falls back to their **pre-configured emergency policy** — never a hardcoded, one-size-fits-all rule.

### 📡 Respond

Once the emergency threshold is reached, SAKHI executes the user's configured response policy, which may include:

- Notifying trusted contacts
- Sharing live location
- Creating an emergency incident
- Sending emergency notifications
- Updating a guardian/trusted-contact dashboard
- Continuing location tracking
- Escalating to secondary contacts
- Generating an incident summary

---

## 🔐 Consent-First Design

Consent isn't a feature bolted onto SAKHI — it's foundational.

**SAKHI is never positioned as a system that continuously spies on its users.** Every capability is opt-in and explicitly configured by the person using it, including:

- 📍 Location monitoring
- 🤖 AI safety detection
- 🎙️ Audio analysis
- 🚨 Automatic emergency escalation
- 🗺️ Emergency location sharing
- 🧾 Evidence collection

SAKHI operates strictly within the permissions and emergency policies configured by the user. Privacy is treated as a **core product requirement**, not an afterthought.

---

## 🗺️ Safe Journey Mode

**Safe Journey** lets a user proactively share and monitor a trip:

```
Origin → Destination → Expected journey
```

While the journey is active, SAKHI monitors relevant safety signals, watching for anomalies such as:

- Significant route deviation
- Unexpected prolonged inactivity
- Unusual movement
- Journey exceeding expected duration
- Other contextual risk signals

If something looks off, SAKHI verifies the user's safety and follows their configured emergency policy — the same Detect → Verify → Respond loop, scoped to the journey.

> The goal is **not** to track the user unnecessarily. Monitoring is limited strictly to the active safety journey and the user's consent — it starts and stops with the journey itself.

---

## 🧠 AI Risk Engine

SAKHI uses a **multimodal risk-assessment approach** rather than relying on any single signal in isolation.

**Naive approach (avoided):**
```
Scream detected → Emergency
```

**SAKHI's approach — combining signals:**
```
Distress audio
      +
Abnormal movement
      +
Unexpected route deviation
      +
No response
      ↓
Higher risk assessment
```

The system produces an **explainable** risk score from **0–100**:

| Score | Level |
|------:|:------|
| 0–30 | 🟢 SAFE |
| 31–60 | 🟡 SUSPICIOUS |
| 61–80 | 🟠 HIGH |
| 81–100 | 🔴 CRITICAL |

Example output:

```json
{
  "risk_score": 86,
  "risk_level": "CRITICAL",
  "reasons": [
    "Distress signal detected",
    "Abnormal movement detected",
    "Unexpected route deviation",
    "User did not respond"
  ]
}
```

> **Guiding principle:** SAKHI provides explainable risk assessment — never a claim of perfect, infallible AI-based danger detection. The exact scoring implementation is expected to evolve over time.

---

## 🧩 Design Principles

- **Human judgment first** — SAKHI assists; it never overrides the user's own decisions.
- **Consent over surveillance** — every capability is opt-in and configurable.
- **Explainability over black-box certainty** — every risk score comes with reasons.
- **Graceful verification** — the system asks before it acts, whenever it safely can.
- **Scoped monitoring** — safety features are active only when and where the user has enabled them.

---

## 🚧 Roadmap

- [ ] Core Detect → Verify → Respond pipeline
- [ ] Consent & permissions management dashboard
- [ ] Safe Journey mode (MVP)
- [ ] Multimodal risk-scoring engine
- [ ] Trusted contacts / guardian dashboard
- [ ] Wearable & external sensor integration
- [ ] Incident summary generation

---

## ⚡ Backend Architecture & Emergency API (BE3)

The emergency management and real-time communication subsystem (Backend Engineer 3) is implemented with FastAPI, async SQLAlchemy, Celery, Redis, and WebSockets.

Comprehensive technical documentation is available in [docs/BE3_EMERGENCY_REALTIME.md](docs/BE3_EMERGENCY_REALTIME.md):
- **Manual SOS & AI Triggers**: `POST /emergency/sos`, `POST /emergency/trigger`
- **Verification Flow**: `POST /emergency/incidents/{id}/verify`
- **Policy-Driven Escalation**: Celery timeout tasks & cascade notifications
- **Realtime WebSocket Channel**: `WS /ws/emergency/{id}` (room-based pub/sub for owner & authorized guardians)
- **Secure Location Streaming**: Authenticated pings & authorized guardian map access
- **Test Suite**: 37 unit and integration tests passing (`python -m pytest tests/ -v`)


---

## 🤝 Contributing

Contributions, ideas, and feedback are welcome. If you'd like to help build SAKHI, feel free to open an issue or submit a pull request.

## 📄 License

This project is licensed under the License.

---

<div align="center">

**SAKHI** — *because safety should be proactive, not just reactive.*

</div>
