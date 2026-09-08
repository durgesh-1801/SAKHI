# SAKHI — Backend 2: Core Backend & Data Layer

**Tagline:** *Detect. Verify. Respond.*  
**Branch:** `feature/core-backend`  
**Role:** Identity, Configuration, Data, Consent & Authorization Layer

---

## 1. Overview & System Architecture

SAKHI is an AI-powered, consent-driven, real-time women safety system. Within the overall tripartite backend architecture:

- **Backend 1 (AI & Risk Engine):** Audio distress detection, motion anomaly detection, route deviation anomaly detection, multimodal risk scoring.
- **Backend 2 (Core Backend & Data - THIS MODULE):** Identity, Authentication, User Accounts, Trusted Contacts, Consent-First Management, Emergency Policies, Safe Journey data lifecycle, authorization & ownership, and shared data contracts.
- **Backend 3 (Emergency & Realtime):** Safety verification countdown execution, WebSocket live feeds, incident timeline, emergency alert dispatch, notification delivery.

```
       [ Client App ]
             │
             ▼
┌──────────────────────────────────────────────────────────┐
│              BACKEND 2 — CORE BACKEND & DATA             │
│  - Authentication & JWT Sessions                         │
│  - User Management                                       │
│  - Trusted Contacts CRUD & Ownership                     │
│  - Consent-First Opt-In Engine                           │
│  - Emergency Response Policies                           │
│  - Safe Journey Lifecycle                                │
└──────────────┬───────────────────────────┬───────────────┘
               │ Context / Consent         │ Policy / Contacts
               ▼                           ▼
┌──────────────────────────────┐  ┌─────────────────────────────────┐
│   BACKEND 1 — AI RISK ENGINE │  │ BACKEND 3 — EMERGENCY & REALTIME│
│  - Distress Audio Analysis   │  │  - Verification Execution       │
│  - Motion / Route Anomaly    │  │  - Alert Escalation Engine      │
│  - Probabilistic Risk Score  │  │  - Realtime WebSockets / Push   │
└──────────────────────────────┘  └─────────────────────────────────┘
```

---

## 2. Database Models & Schema

### `users`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID (String 36) | PRIMARY KEY | Unique user identifier |
| `name` | String(120) | NOT NULL | User's full name |
| `email` | String(255) | UNIQUE, INDEXED, NOT NULL | Account email address |
| `phone` | String(30) | INDEXED, NOT NULL | E.164 phone number |
| `password_hash` | String(255) | NOT NULL | Bcrypt salted hash (never exposed) |
| `is_active` | Boolean | DEFAULT True | Account status |
| `created_at` | DateTime (UTC) | DEFAULT now | Account creation timestamp |
| `updated_at` | DateTime (UTC) | DEFAULT now, onupdate | Last update timestamp |

### `trusted_contacts`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID (String 36) | PRIMARY KEY | Contact identifier |
| `user_id` | UUID (String 36) | FOREIGN KEY (users.id), INDEX | Owning user |
| `name` | String(120) | NOT NULL | Contact name |
| `phone` | String(30) | NOT NULL | Contact phone number |
| `relationship_type`| String(60) | NULLABLE | e.g. Mother, Friend, Partner |
| `priority` | Integer | DEFAULT 1, CHECK(1..10) | Escalation priority (1 = highest) |
| `verified` | Boolean | DEFAULT False | Phone verification state |
| `created_at` | DateTime (UTC) | DEFAULT now | Creation timestamp |
| `updated_at` | DateTime (UTC) | DEFAULT now, onupdate | Last update timestamp |

### `user_consents`
*Consent is opt-in by default for all detection & monitoring.*
| Column | Type | Default | Description |
|---|---|---|---|
| `id` | UUID (String 36) | PRIMARY KEY | Consent record identifier |
| `user_id` | UUID (String 36) | UNIQUE, FOREIGN KEY (users.id) | Owning user |
| `location_monitoring` | Boolean | `False` | Consent to track location during journeys |
| `ai_detection` | Boolean | `False` | Consent to run AI safety signal analysis |
| `audio_analysis` | Boolean | `False` | Consent to analyze mic streams for screams/distress |
| `automatic_escalation` | Boolean | `False` | Consent to alert contacts if verification times out |
| `evidence_collection` | Boolean | `False` | Consent to log sensor/audio snapshots on incident |
| `created_at` | DateTime (UTC) | DEFAULT now | Creation timestamp |
| `updated_at` | DateTime (UTC) | DEFAULT now, onupdate | Audit timestamp |

### `emergency_policies`
| Column | Type | Constraints / Default | Description |
|---|---|---|---|
| `id` | UUID (String 36) | PRIMARY KEY | Policy identifier |
| `user_id` | UUID (String 36) | UNIQUE, FOREIGN KEY (users.id) | Owning user |
| `verification_timeout` | Integer | DEFAULT 30, CHECK(10..300) | Countdown seconds before auto-alerting |
| `auto_alert_enabled` | Boolean | DEFAULT True | Whether to auto-alert if unresponsive |
| `location_sharing_enabled` | Boolean | DEFAULT True | Include live location in alerts |
| `primary_contact_id` | UUID | FOREIGN KEY (trusted_contacts.id) | Primary responder |
| `secondary_contact_id` | UUID | FOREIGN KEY (trusted_contacts.id) | Secondary responder |
| `escalation_level` | Integer | DEFAULT 1, CHECK(1..3) | 1=Primary, 2=All contacts, 3=+Authorities |
| `created_at` | DateTime (UTC) | DEFAULT now | Creation timestamp |
| `updated_at` | DateTime (UTC) | DEFAULT now, onupdate | Policy change timestamp |

### `safe_journeys`
| Column | Type | Constraints / Default | Description |
|---|---|---|---|
| `id` | UUID (String 36) | PRIMARY KEY | Journey identifier |
| `user_id` | UUID (String 36) | FOREIGN KEY (users.id), INDEX | Owning user |
| `origin` | String(255) | NOT NULL | Trip origin |
| `destination` | String(255) | NOT NULL | Trip destination |
| `expected_duration` | Integer | NOT NULL (minutes) | Estimated trip duration |
| `status` | String(20) | PLANNED, ACTIVE, COMPLETED, CANCELLED | Current status |
| `started_at` | DateTime (UTC) | NULLABLE | Trip activation timestamp |
| `ended_at` | DateTime (UTC) | NULLABLE | Trip completion/cancellation timestamp |
| `created_at` | DateTime (UTC) | DEFAULT now | Creation timestamp |
| `updated_at` | DateTime (UTC) | DEFAULT now, onupdate | Update timestamp |

---

## 3. Core API Endpoints

All protected endpoints require `Authorization: Bearer <token>` header.

### Authentication (`/api/v1/auth`)
- `POST /api/v1/auth/register` — Registers user, auto-creates default opt-in consent and emergency policy. Returns `201 Created`.
- `POST /api/v1/auth/login` — Verifies email + password, returns JWT `access_token` and user profile. Returns `200 OK`.
- `GET /api/v1/auth/me` — Returns current authenticated user profile.
- `POST /api/v1/auth/logout` — Logout acknowledgement endpoint.

### User Management (`/api/v1/users`)
- `GET /api/v1/users/me` — Read authenticated profile.
- `PUT /api/v1/users/me` — Update name, phone, or password.

### Trusted Contacts (`/api/v1/contacts`)
- `POST /api/v1/contacts` — Add a new trusted contact (`name`, `phone`, `relationship_type`, `priority`, `verified`).
- `GET /api/v1/contacts` — List all contacts for the authenticated user, sorted by priority.
- `GET /api/v1/contacts/{id}` — Retrieve contact. *Enforces user ownership (403 if foreign contact).*
- `PUT /api/v1/contacts/{id}` — Update contact details. *Enforces ownership.*
- `DELETE /api/v1/contacts/{id}` — Remove contact. Automatically unlinks contact from user's `EmergencyPolicy`.

### Consent Management (`/api/v1/consent`)
- `GET /api/v1/consent` — View current consent configuration.
- `PUT /api/v1/consent` — Granularly update privacy toggles. Automatically updates `updated_at` audit timestamp.

### Emergency Policy (`/api/v1/emergency-policy`)
- `GET /api/v1/emergency-policy` — View user emergency response policy.
- `PUT /api/v1/emergency-policy` — Update policy.
  - Validates `verification_timeout` (10s – 300s).
  - Validates `primary_contact_id` and `secondary_contact_id` strictly belong to the authenticated user.
  - Rejects foreign contacts or setting primary and secondary to the same contact (`400 Bad Request`).

### Safe Journey (`/api/v1/journeys`)
- `POST /api/v1/journeys` — Create a journey (`PLANNED` or immediately `ACTIVE` if `auto_start=True`).
- `GET /api/v1/journeys` — List all user journeys.
- `GET /api/v1/journeys/active` — Return currently `ACTIVE` journey or `null`.
- `GET /api/v1/journeys/{id}` — Get journey details. *Enforces ownership.*
- `PUT /api/v1/journeys/{id}` — Update journey parameters (only allowed on non-concluded journeys).
- `POST /api/v1/journeys/{id}/start` — Transition `PLANNED` → `ACTIVE`. *Rejects with 409 Conflict if another active journey is in progress.*
- `POST /api/v1/journeys/{id}/end` — Transition `ACTIVE` → `COMPLETED`. Sets `ended_at`.
- `POST /api/v1/journeys/{id}/cancel` — Transition `PLANNED`/`ACTIVE` → `CANCELLED`.

---

## 4. Integration Contracts for Backend 1 & Backend 3

### For Backend 1 (AI & Risk Engine):
Backend 1 determines probabilistic risk based on audio, movement, and route context.
Before running inference, Backend 1 calls:

```http
GET /api/v1/context/ai-risk/{user_id}
```

**Response Contract (`AIRiskContext`):**
```json
{
  "user_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "ai_detection_permitted": true,
  "audio_analysis_permitted": false,
  "location_monitoring_permitted": true,
  "active_journey": {
    "id": "c3a10e7b-8419-4f2b-8a5f-972cb7b649a2",
    "origin": "Tech Park",
    "destination": "Home",
    "expected_duration": 30,
    "status": "ACTIVE",
    "started_at": "2026-09-08T16:20:00Z"
  },
  "consent": { ... }
}
```

> **Backend 1 Rule:** If `ai_detection_permitted` is `false`, Backend 1 must NOT run distress detection. If `audio_analysis_permitted` is `false`, microphone audio stream ingestion MUST be skipped.

### For Backend 3 (Emergency & Realtime):
When an emergency incident or safety verification is triggered, Backend 3 queries:

```http
GET /api/v1/context/emergency-dispatch/{user_id}
```

**Response Contract (`EmergencyDispatchContext`):**
```json
{
  "user_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "user_name": "Aarya Sharma",
  "user_phone": "+919876543210",
  "auto_escalation_permitted": true,
  "evidence_collection_permitted": false,
  "verification_timeout": 30,
  "location_sharing_enabled": true,
  "policy": { ... },
  "consent": { ... },
  "active_journey": { ... },
  "recipients": [
    {
      "id": "...",
      "name": "Mother",
      "phone": "+919811122233",
      "priority": 1,
      "verified": true
    },
    {
      "id": "...",
      "name": "Sister",
      "phone": "+919844455566",
      "priority": 2,
      "verified": true
    }
  ]
}
```

> **Backend 3 Rule:** Use `verification_timeout` as the countdown duration before escalating. If `auto_escalation_permitted` is `false`, do not automatically blast emergency alerts when timeout lapses.

---

## 5. Security & Ownership Guarantees

1. **Password Security:** Salted Bcrypt hashing with standard work factor. Password hashes are excluded from all API responses and serialization schemas.
2. **Strict Ownership Isolation:** Contacts, Policies, and Journeys belong to the authenticated identity from the JWT `sub` claim. Accessing or mutating another user's entity yields `403 Forbidden`.
3. **Cross-User Injection Protection:** A user cannot set another user's contact ID as their primary or secondary emergency contact. Doing so returns `400 Bad Request`.
4. **Consent Precedence:** Even if `location_sharing_enabled` is set to `true` in emergency policy, if user consent has `location_monitoring = false`, the effective context returns `location_sharing_enabled: false`.

---

## 6. How to Run Locally & Execute Tests

### Prerequisites
- Python 3.11+
- Virtualenv (recommended)

### Installation
```bash
pip install -r requirements.txt
cp .env.example .env
```

### Run Server
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
- Interactive API Docs (Swagger): `http://localhost:8000/docs`
- Alternative Docs (ReDoc): `http://localhost:8000/redoc`

### Run Test Suite
```bash
python -m pytest
```
Output:
```
============================= 40 passed in 14.97s =============================
```
