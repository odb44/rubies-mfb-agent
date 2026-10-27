"""Run the Rubies MFB agent API."""

import os

import uvicorn


def main() -> None:
    """Start the application using its factory."""
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