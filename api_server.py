"""Start TenderBrief's FastAPI application through Uvicorn."""
import os

import uvicorn


if __name__ == "__main__":
    uvicorn.run(
        "bidmaster.api.main:app",
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "4174")),
        log_level=os.environ.get("LOG_LEVEL", "info"),
    )
