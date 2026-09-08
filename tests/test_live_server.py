"""End-to-End Live HTTP server tests.

Spins up a lightweight uvicorn server in a separate thread and issues real network
requests using httpx to guarantee live wire-level compliance.
"""

import threading
import time
import httpx
import uvicorn
from src.ai_engine.api import app


class LiveServerThread(threading.Thread):
    def __init__(self, host="127.0.0.1", port=8765):
        super().__init__(daemon=True)
        self.host = host
        self.port = port
        self.config = uvicorn.Config(app, host=self.host, port=self.port, log_level="error")
        self.server = uvicorn.Server(self.config)

    def run(self):
        self.server.run()

    def stop(self):
        self.server.should_exit = True


def test_live_server_end_to_end():
    server = LiveServerThread()
    server.start()

    # Wait for server to start
    base_url = f"http://{server.host}:{server.port}"
    for _ in range(50):
        try:
            r = httpx.get(f"{base_url}/health", timeout=1.0)
            if r.status_code == 200:
                break
        except Exception:
            time.sleep(0.1)

    try:
        with httpx.Client(base_url=base_url, timeout=5.0) as client:
            # 1. Health check over wire
            health_res = client.get("/health")
            assert health_res.status_code == 200
            assert health_res.json()["status"] == "healthy"

            # 2. Config check over wire
            config_res = client.get("/ai/config")
            assert config_res.status_code == 200
            assert config_res.json()["weights"]["manual_sos"] == 50.0

            # 3. Post analysis request over wire
            payload = {
                "user_id": "live_wire_user_1",
                "signals": {
                    "manual_sos": False,
                    "distress_audio": True,
                    "audio_confidence": 0.89,
                    "sudden_fall": True,
                    "fall_confidence": 0.94,
                    "abnormal_motion": True,
                    "no_response": True,
                },
            }
            analyze_res = client.post("/ai/analyze", json=payload)
            assert analyze_res.status_code == 200
            data = analyze_res.json()

            # 35 + 25 + 15 + 20 = 95 -> CRITICAL
            assert data["risk_score"] == 95.0
            assert data["risk_level"] == "CRITICAL"
            assert "distress_audio" in data["signals_detected"]
            assert "sudden_fall" in data["signals_detected"]
            assert "abnormal_motion" in data["signals_detected"]
            assert "no_response" in data["signals_detected"]
            assert len(data["reasons"]) == 4

            # 4. Post invalid request over wire -> HTTP 422
            bad_payload = {
                "user_id": "live_wire_user_1",
                "signals": {
                    "audio_confidence": 99.0,
                },
            }
            bad_res = client.post("/ai/analyze", json=bad_payload)
            assert bad_res.status_code == 422
            assert bad_res.json()["error"] == "Validation Error"

    finally:
        server.stop()
