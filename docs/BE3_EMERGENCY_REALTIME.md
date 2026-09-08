# ARIA / SAKHI — Backend Engineer 3: Emergency & Realtime Systems

This document covers the implementation, architecture, interfaces, and operational guidelines for **Backend Engineer 3 (BE3)** within Project ARIA (Autonomous Real-Time Intelligence for Assistance) / SAKHI.

---

## 1. Domain Ownership & Boundaries

### BE3 Ownership
- **Emergency / SOS Management**: Manual triggers, AI-initiated incident creation
- **Incident Lifecycle**: `ACTIVE`, `VERIFYING`, `ESCALATING`, `RESOLVED`, `CANCELLED` transitions
- **Verification Engine**: "Are you safe?" prompt, countdown tracking, user verification response handling
- **Policy-Driven Escalation**: Background task execution via Celery, timeout handling, cascade dispatch
- **Notification Abstraction**: Multi-channel delivery (`FCM push`, `in-app`, `Twilio SMS`)
- **Real-Time Location Service**: Live location updates ingestion, history logging, streaming
- **WebSocket Manager**: Secure room-based bidirectional pub/sub per incident for users & guardians

### Integration Boundaries (Consumed via clean contracts, NOT owned by BE3)
- **BE1 (Auth & Users)**:
  - User model identity (`app.models.user.User`)
  - Authentication dependency (`app.auth.dependencies.get_current_user` yielding `UserRead`)
  - AI Risk engine triggers (`POST /emergency/trigger`)
- **BE2 (Contacts, Consent & Policy)**:
  - Trusted contacts contract (`app.services.contact_service`)
  - Consent verification gates (`app.services.consent_service`)
  - User emergency policy configuration (`app.services.policy_service`)

---

## 2. Emergency Incident Lifecycle

```
               ┌──────────────┐
               │  MANUAL_SOS  │
               └──────┬───────┘
                      │ (skips verification)
                      ▼
               ┌──────────────┐
               │    ACTIVE    ├────────────┐
               └──────┬───────┘            │
                      │                    │
                      ▼                    │
             ┌─────────────────┐           │
             │   ESCALATING    │           │
             └────────┬────────┘           │
                      │                    │
      ┌───────────────┴───────────────┐    │
      ▼                               ▼    ▼
┌───────────┐                   ┌─────────────┐
│ RESOLVED  │                   │  CANCELLED  │
└───────────┘                   └─────────────┘
      ▲                               ▲
      │                               │
      │ (USER_REQUESTED_HELP /        │ (USER_CONFIRMED_SAFE)
      │  NO_RESPONSE timeout)         │
      │        ┌──────────────┐       │
      └────────┤  VERIFYING   ├───────┘
               └──────▲───────┘
                      │
               ┌──────┴───────┐
               │ AI_DETECTION │
               └──────────────┘
```

1. **MANUAL_SOS**: Explicit SOS button press. Immediately transitions to `ACTIVE` -> `ESCALATING`. Contacts are notified immediately without waiting for verification.
2. **AI_DETECTION**: Multi-modal risk detection (audio/motion/geofence anomaly). Checks `consent.allow_ai_monitoring`. If granted, creates incident in `VERIFYING` state.
3. **Verification Window**: Prompts the user: *"Are you safe?"* with countdown defined in user's `EmergencyPolicy.verification_timeout_seconds`.
   - `USER_CONFIRMED_SAFE`: Cancels Celery timeout task, transitions incident to `CANCELLED`, records timeline event.
   - `USER_REQUESTED_HELP`: Cancels timeout task, escalates immediately to `ESCALATING`.
   - `NO_RESPONSE`: Celery background task triggers on timeout countdown, transitions to `ESCALATING`, dispatches alerts.
4. **Resolution**: `POST /emergency/incidents/{id}/resolve` marks an active or escalating incident as `RESOLVED`.

---

## 3. HTTP REST API Reference

Base path: `/emergency`

### 3.1 Trigger Manual SOS
- **Endpoint**: `POST /emergency/sos`
- **Auth**: Bearer JWT (`current_user`)
- **Rate Limit**: Configured by `SOS_RATE_LIMIT_PER_MINUTE` (default 5/min)
- **Request Body**:
```json
{
  "latitude": 26.8432,
  "longitude": 75.5651,
  "accuracy": 5.0
}
```
- **Response** (`201 Created`):
```json
{
  "incident_id": "7f7943d0-7a0e-473d-bd88-d227560b457e",
  "status": "ACTIVE",
  "risk_level": "CRITICAL",
  "message": "Emergency incident created. Escalation started."
}
```

### 3.2 AI Trigger (BE1 Integration)
- **Endpoint**: `POST /emergency/trigger`
- **Auth**: Bearer JWT (Target user or BE1 Service Account)
- **Request Body**:
```json
{
  "user_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
  "risk_score": 86.0,
  "risk_level": "CRITICAL",
  "reasons": ["Distress scream detected", "Sudden fall and impact"],
  "trigger_type": "AI_DETECTION",
  "latitude": 26.8432,
  "longitude": 75.5651,
  "accuracy": 10.0
}
```
- **Response** (`201 Created` when consent granted):
```json
{
  "incident_id": "8a8342d0-7a0e-473d-bd88-d227560b457f",
  "status": "VERIFYING",
  "risk_level": "CRITICAL",
  "message": "AI-triggered incident created. Verification request sent. Escalation in 30s if no response."
}
```
- **Response** (`200 OK` when AI monitoring consent denied):
```json
{
  "detail": "AI trigger received but user has not consented to AI monitoring.",
  "user_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
}
```

### 3.3 List Incidents
- **Endpoint**: `GET /emergency/incidents?limit=20&offset=0`
- **Auth**: Bearer JWT
- **Response** (`200 OK`):
```json
[
  {
    "id": "7f7943d0-7a0e-473d-bd88-d227560b457e",
    "user_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    "trigger_type": "MANUAL_SOS",
    "status": "ACTIVE",
    "risk_level": "CRITICAL",
    "risk_score": null,
    "latitude": 26.8432,
    "longitude": 75.5651,
    "location_accuracy": 5.0,
    "location_updated_at": "2026-09-08T12:00:00Z",
    "ai_reasons": null,
    "created_at": "2026-09-08T12:00:00Z",
    "updated_at": "2026-09-08T12:00:00Z",
    "resolved_at": null
  }
]
```

### 3.4 Get Incident with Timeline
- **Endpoint**: `GET /emergency/incidents/{incident_id}/timeline`
- **Auth**: Bearer JWT (Owner or authorized guardian)
- **Response** (`200 OK`):
```json
{
  "id": "7f7943d0-7a0e-473d-bd88-d227560b457e",
  "user_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
  "trigger_type": "MANUAL_SOS",
  "status": "ACTIVE",
  "risk_level": "CRITICAL",
  "created_at": "2026-09-08T12:00:00Z",
  "events": [
    {
      "id": "11111111-1111-1111-1111-111111111111",
      "incident_id": "7f7943d0-7a0e-473d-bd88-d227560b457e",
      "event_type": "INCIDENT_CREATED",
      "description": "Emergency incident created via MANUAL_SOS",
      "metadata": {"trigger": "MANUAL_SOS", "risk_level": "CRITICAL"},
      "created_at": "2026-09-08T12:00:00Z"
    }
  ]
}
```

### 3.5 Verification Response
- **Endpoint**: `POST /emergency/incidents/{incident_id}/verify`
- **Auth**: Bearer JWT (Owner only)
- **Request Body**:
```json
{
  "response": "USER_CONFIRMED_SAFE"
}
```
*(Accepted values: `USER_CONFIRMED_SAFE`, `USER_REQUESTED_HELP`)*
- **Response** (`200 OK`):
```json
{
  "incident_id": "7f7943d0-7a0e-473d-bd88-d227560b457e",
  "status": "CANCELLED",
  "message": "You've confirmed you are safe. Incident cancelled."
}
```

### 3.6 Incident Cancellation & Resolution
- **Cancel**: `POST /emergency/incidents/{incident_id}/cancel` (Owner only; cannot cancel resolved)
- **Resolve**: `POST /emergency/incidents/{incident_id}/resolve` (Owner or authorized contact)

### 3.7 Secure Location Access
- **Endpoint**: `GET /emergency/incidents/{incident_id}/location`
- **Auth**: Bearer JWT (Owner or authorized guardian)
- **Security Check**:
  1. Incident owner -> Access granted
  2. Contact listed in user's trusted contacts with user consent for location sharing -> Access granted
  3. Unrelated user -> `403 Forbidden`
- **Response** (`200 OK`):
```json
{
  "incident_id": "7f7943d0-7a0e-473d-bd88-d227560b457e",
  "latitude": 26.8432,
  "longitude": 75.5651,
  "accuracy": 5.0,
  "updated_at": "2026-09-08T12:00:00Z",
  "status": "ACTIVE"
}
```

---

## 4. Realtime WebSocket API

- **Endpoint**: `WS /ws/emergency/{incident_id}?token={jwt_token}`
- **Security & Authorization**:
  - Validates `token` query param via auth dependency on connection.
  - Rejects with `4001` (Unauthorized) if token invalid.
  - Verifies caller is either the **incident owner** or an **authorized trusted contact (guardian)**.
  - Rejects with `4003` (Forbidden) if user has no role in the incident.
  - Rejects with `4004` (Not Found) if incident ID is invalid or missing.

### 4.1 Client -> Server Events

#### 1. Ping / Keepalive
```json
{
  "event": "ping"
}
```

#### 2. Location Ping (Owner Only)
Guardians attempting to send location updates will receive a `403 FORBIDDEN` error.
```json
{
  "event": "location_update",
  "latitude": 26.84321,
  "longitude": 75.56514,
  "accuracy": 4.5
}
```

### 4.2 Server -> Client Events

#### 1. Connection Welcome
```json
{
  "event": "connected",
  "incident_id": "7f7943d0-7a0e-473d-bd88-d227560b457e",
  "status": "ACTIVE",
  "role": "owner",
  "timestamp": "2026-09-08T12:00:00Z"
}
```

#### 2. Live Location Broadcast
Broadcast to all active connections in the room (owner + guardians).
```json
{
  "event": "location_update",
  "incident_id": "7f7943d0-7a0e-473d-bd88-d227560b457e",
  "latitude": 26.84321,
  "longitude": 75.56514,
  "accuracy": 4.5,
  "timestamp": "2026-09-08T12:00:05Z"
}
```

#### 3. Verification Request
Sent to owner when an AI detection event occurs.
```json
{
  "event": "verification_request",
  "incident_id": "7f7943d0-7a0e-473d-bd88-d227560b457e",
  "message": "Are you safe? Please respond.",
  "expires_at": "2026-09-08T12:00:30Z"
}
```

#### 4. Status Update / Resolution
```json
{
  "event": "incident_resolved",
  "incident_id": "7f7943d0-7a0e-473d-bd88-d227560b457e",
  "status": "RESOLVED",
  "resolved_at": "2026-09-08T12:05:00Z"
}
```

---

## 5. Configuration & Environment Variables

Copy from `.env.example`:

| Variable | Description | Default |
|---|---|---|
| `APP_ENV` | Application environment (`development`, `production`) | `development` |
| `DEBUG` | Enable debug logging & interactive Swagger docs | `false` |
| `SECRET_KEY` | Application secret key | `change-me` |
| `DATABASE_URL` | Async PostgreSQL connection string | `postgresql+asyncpg://aria:aria_password@localhost:5432/aria_db` |
| `REDIS_URL` | Redis URL for caching | `redis://localhost:6379/0` |
| `CELERY_BROKER_URL` | Celery broker URL | `redis://localhost:6379/1` |
| `CELERY_RESULT_BACKEND`| Celery results backend | `redis://localhost:6379/2` |
| `JWT_SECRET_KEY` | JWT signing secret | `change-me-jwt-secret` |
| `JWT_ALGORITHM` | JWT hashing algorithm | `HS256` |
| `FIREBASE_CREDENTIALS_PATH` | Path to Firebase service account JSON | `firebase-credentials.json` |
| `FIREBASE_CREDENTIALS_JSON` | Inline Firebase credentials string | `""` |
| `TWILIO_ACCOUNT_SID` | Twilio Account SID for SMS | `""` |
| `TWILIO_AUTH_TOKEN` | Twilio Auth Token for SMS | `""` |
| `TWILIO_FROM_NUMBER` | Twilio Sender Phone Number | `""` |
| `SMS_NOTIFICATIONS_ENABLED` | Enable outbound SMS | `false` |
| `SOS_RATE_LIMIT_PER_MINUTE` | Rate limit for manual SOS triggers | `5` |
| `DEFAULT_VERIFICATION_TIMEOUT_SECONDS` | Fallback timeout if policy is missing | `30` |

---

## 6. How to Run Locally & Test

### Run Test Suite (pytest)
```bash
python -m pytest tests/ -v
```

### Run Linter & Formatter (ruff)
```bash
python -m ruff check app/ tests/
python -m ruff format app/ tests/
```

### Run Static Type Checker (mypy)
```bash
python -m mypy app/
```

### Run Migrations (Alembic)
```bash
alembic upgrade head
```

### Start Backend Locally (Uvicorn)
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Start Background Celery Worker
```bash
celery -A app.tasks.celery_app.celery_app worker --loglevel=info
```

### Start with Docker Compose
```bash
docker-compose up -d --build
```
This boots:
- `aria-api`: FastAPI backend on `http://localhost:8000`
- `aria-db`: PostgreSQL 16 on `5432`
- `aria-redis`: Redis 7 on `6379`
- `aria-worker`: Celery background worker
