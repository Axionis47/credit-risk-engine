"""Start the scoring API server."""

import uvicorn

from credit_scoring.config.settings import load_settings


def main():
    settings = load_settings()
    uvicorn.run(
        "credit_scoring.serving.api:create_app",
        factory=True,
        host=settings.serving.host,
        port=settings.serving.port,
        workers=1,  # Single worker for development; use settings.serving.workers in prod
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
