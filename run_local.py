"""Start the Rubies MFB application stack for local development."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import TextIO

ROOT = Path(__file__).resolve().parent

BANKING_URL = "http://127.0.0.1:8000"
MCP_URL = "http://127.0.0.1:8002/mcp"
AGENT_URL = "http://127.0.0.1:8001"
FRONTEND_URL = "http://127.0.0.1:5173"

STARTUP_TIMEOUT = 45
SHUTDOWN_TIMEOUT = 8

processes: dict[str, subprocess.Popen[str]] = {}
stop_event = threading.Event()


def log(service: str, message: str) -> None:
    print(f"[{service}] {message}", flush=True)


def load_env_file() -> dict[str, str]:
    """Read simple KEY=VALUE entries from the root .env file."""
    env = os.environ.copy()
    env_file = ROOT / ".env"

    if not env_file.exists():
        log("launcher", "No root .env file found; using existing environment.")
        return env

    for raw_line in env_file.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        if not key:
            continue

        # Do not overwrite variables already explicitly set in this shell.
        if key not in os.environ:
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            env[key] = value

    return env


def port_is_available(host: str, port: int) -> bool:
    """Check whether a local port can be bound without taking it over."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((host, port))
            return True
        except OSError:
            return False


def stream_output(name: str, stream: TextIO | None) -> None:
    """Print a child process's output with its service name."""
    if stream is None:
        return

    try:
        for line in iter(stream.readline, ""):
            if not line:
                break
            print(f"[{name}] {line.rstrip()}", flush=True)
    finally:
        stream.close()


def start_service(
    name: str,
    command: list[str],
    cwd: Path,
    env: dict[str, str],
) -> subprocess.Popen[str]:
    """Start one service and stream its stdout/stderr."""
    log(name, f"Starting: {' '.join(command)}")

    process = subprocess.Popen(
        command,
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    processes[name] = process

    threading.Thread(
        target=stream_output,
        args=(name, process.stdout),
        daemon=True,
    ).start()

    return process


def endpoint_ready(url: str, expected_json_status: str | None = None) -> bool:
    """Return True when an endpoint responds as expected."""
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json"},
    )

    try:
        with urllib.request.urlopen(request, timeout=2) as response:
            if not 200 <= response.status < 300:
                return False

            if expected_json_status is None:
                return True

            import json

            payload = json.loads(response.read().decode("utf-8"))
            return payload.get("status") == expected_json_status

    except urllib.error.HTTPError as exc:
        # The MCP endpoint may reject a plain GET because it expects MCP
        # protocol traffic. A non-server-error response still proves that
        # an HTTP server is listening at that endpoint.
        return (
            expected_json_status is None
            and 400 <= exc.code < 500
        )
    except (
        urllib.error.URLError,
        TimeoutError,
        OSError,
        ValueError,
    ):
        return False


def wait_until_ready(
    name: str,
    url: str,
    process: subprocess.Popen[str],
    expected_json_status: str | None = None,
) -> None:
    """Wait for a service to become ready or fail with useful context."""
    log(name, f"Waiting for readiness at {url}")

    deadline = time.monotonic() + STARTUP_TIMEOUT

    while time.monotonic() < deadline:
        if stop_event.is_set():
            raise RuntimeError("Startup interrupted.")

        exit_code = process.poll()
        if exit_code is not None:
            raise RuntimeError(
                f"{name} exited during startup with code {exit_code}."
            )

        if endpoint_ready(url, expected_json_status):
            log(name, "Ready.")
            return

        time.sleep(0.5)

    raise RuntimeError(
        f"{name} did not become ready within {STARTUP_TIMEOUT} seconds. "
        f"Check the [{name}] log above."
    )


def stop_services() -> None:
    """Stop only child processes started by this launcher."""
    stop_event.set()

    if not processes:
        return

    log("launcher", "Stopping services...")

    # Stop in reverse startup order.
    for name, process in reversed(list(processes.items())):
        if process.poll() is None:
            log(name, "Sending termination signal.")
            process.terminate()

    for name, process in reversed(list(processes.items())):
        if process.poll() is None:
            try:
                process.wait(timeout=SHUTDOWN_TIMEOUT)
            except subprocess.TimeoutExpired:
                log(name, "Did not stop in time; forcing this child to exit.")
                process.kill()
                process.wait()

        log(name, "Stopped.")

    processes.clear()


def ensure_required_environment(env: dict[str, str]) -> None:
    """Check required MCP authentication configuration without printing it."""
    required = ("JWT_SECRET_KEY", "JWT_ISSUER", "JWT_AUDIENCE")
    missing = [key for key in required if not env.get(key, "").strip()]

    if missing:
        raise RuntimeError(
            "Missing required .env/environment variables: "
            + ", ".join(missing)
        )


def main() -> int:
    env = load_env_file()

    try:
        ensure_required_environment(env)

        # Do not silently attach to another process already using our ports.
        expected_ports = (
            ("Banking API", 8000),
            ("MCP server", 8002),
            ("Agent API", 8001),
            ("Frontend", 5173),
        )

        occupied = [
            f"{name} (127.0.0.1:{port})"
            for name, port in expected_ports
            if not port_is_available("127.0.0.1", port)
        ]

        if occupied:
            raise RuntimeError(
                "These required ports are already occupied:\n  - "
                + "\n  - ".join(occupied)
                + "\nStop the relevant service yourself, then run this launcher again. "
                "The launcher will not kill unrelated processes."
            )

        python = sys.executable

        banking = start_service(
            "banking",
            [
                python,
                "-m",
                "uvicorn",
                "rubies_banking_api.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
            ],
            ROOT,
            env,
        )
        wait_until_ready(
            "banking",
            f"{BANKING_URL}/health",
            banking,
            expected_json_status="ok",
        )

        mcp = start_service(
            "mcp",
            [python, "-m", "rubies_mcp_server.server"],
            ROOT,
            env,
        )
        wait_until_ready("mcp", MCP_URL, mcp)

        agent = start_service(
            "agent",
            [python, "-m", "rubies_agent"],
            ROOT,
            env,
        )
        wait_until_ready(
            "agent",
            f"{AGENT_URL}/health",
            agent,
            expected_json_status="ok",
        )

        frontend = start_service(
    "frontend",
    [
        "cmd.exe",
        "/d",
        "/s",
        "/c",
        "npm run dev -- --host 127.0.0.1 --port 5173 --strictPort",
    ],
    ROOT / "frontend",
    env,
)
        
        wait_until_ready("frontend", FRONTEND_URL, frontend)

        print()
        log("launcher", "All four services are ready.")
        log("launcher", f"Frontend:   {FRONTEND_URL}")
        log("launcher", f"Banking:    {BANKING_URL}")
        log("launcher", f"MCP:        {MCP_URL}")
        log("launcher", f"Agent API:  {AGENT_URL}")
        log("launcher", "Press Ctrl+C to stop the services.")

        while True:
            for name, process in list(processes.items()):
                exit_code = process.poll()
                if exit_code is not None:
                    raise RuntimeError(
                        f"{name} exited unexpectedly with code {exit_code}."
                    )
            time.sleep(0.5)

    except KeyboardInterrupt:
        log("launcher", "Shutdown requested.")
        return 0
    except Exception as exc:
        log("launcher", f"FAILED: {exc}")
        return 1
    finally:
        stop_services()


if __name__ == "__main__":
    raise SystemExit(main())