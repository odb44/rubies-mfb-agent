"""Run the Rubies MFB agent API."""

import os
import sys

import uvicorn


def configure_console_encoding() -> None:
    """Configure UTF-8 output for agent callbacks and console logging."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(
                encoding="utf-8",
                errors="backslashreplace",
            )


def main() -> None:
    """Start the application using its factory."""
    configure_console_encoding()

    host = os.getenv("AGENT_HOST", "127.0.0.1")
    port = int(os.getenv("AGENT_PORT", "8001"))

    uvicorn.run(
        "rubies_agent.app:create_app",
        factory=True,
        host=host,
        port=port,
        env_file=".env",
    )


if __name__ == "__main__":
    main()
