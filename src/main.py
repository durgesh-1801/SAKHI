"""Main entry point for running the SAKHI AI / Risk Engine service."""

import uvicorn

from ai_engine.api import app

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=False,
    )
