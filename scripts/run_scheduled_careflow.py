import argparse
import fcntl
import getpass
import json
import os
import signal
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = Path.home() / ".config/careflow/scheduler-config.json"
STATE = Path.home() / ".config/careflow"
LOGS = Path.home() / "Library/Logs/CareFlow"

PYTHON = ROOT / ".venv/bin/python"
INGESTION = ROOT / "scripts/run_ingestion.py"

TIMEOUT_SECONDS = 1200


def read_keychain(service):
    result = subprocess.run(
        [
            "/usr/bin/security",
            "find-generic-password",
            "-a", getpass.getuser(),
            "-s", service,
            "-w",
        ],
        capture_output=True,
        timeout=30,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Unable to retrieve Keychain item: {service}"
        )

    return result.stdout.decode("utf-8").rstrip("\r\n")


def build_environment(enable_email):
    if not CONFIG.is_file():
        raise RuntimeError("Scheduler configuration is missing")

    with CONFIG.open() as file:
        settings = json.load(file)

    required = [
        "AZURE_STORAGE_ACCOUNT",
        "CAREFLOW_SMTP_HOST",
        "CAREFLOW_SMTP_PORT",
        "CAREFLOW_SMTP_USER",
        "CAREFLOW_ALERT_FROM",
        "CAREFLOW_ALERT_TO",
    ]

    missing = [
        name for name in required
        if not settings.get(name)
    ]

    if missing:
        raise RuntimeError(
            "Missing scheduler settings: " + ", ".join(missing)
        )

    # Build a clean environment instead of inheriting
    # secrets or variables from the active Terminal.
    env = {
        "HOME": str(Path.home()),
        "USER": getpass.getuser(),
        "PATH": (
            "/opt/homebrew/bin:/usr/local/bin:"
            "/usr/bin:/bin:/usr/sbin:/sbin"
        ),
        "LANG": "en_US.UTF-8",
        "TMPDIR": os.environ.get("TMPDIR", "/tmp"),
    }

    env.update({name: settings[name] for name in required})

    env["CAREFLOW_AUDIT_KEY_PASSPHRASE"] = read_keychain(
        "careflow-audit-passphrase"
    )

    env["CAREFLOW_SMTP_PASSWORD"] = read_keychain(
        "careflow-smtp-password"
    )

    env["CAREFLOW_EMAIL_DELIVERY_ENABLED"] = (
        "1" if enable_email else "0"
    )

    return env


def run(enable_email):
    os.umask(0o077)

    STATE.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)

    lock_path = STATE / "scheduled-ingestion.lock"

    with lock_path.open("a+") as lock:
        try:
            fcntl.flock(
                lock.fileno(),
                fcntl.LOCK_EX | fcntl.LOCK_NB,
            )
        except BlockingIOError:
            print("CareFlow already has a scheduled run active.")
            print("Overlapping execution prevented.")
            return 75

        if not PYTHON.is_file() or not INGESTION.is_file():
            raise RuntimeError("CareFlow ingestion executable missing")

        env = build_environment(enable_email)

        timestamp = datetime.now(timezone.utc).strftime(
            "%Y%m%dT%H%M%S_%fZ"
        )

        log_path = LOGS / f"ingestion-{timestamp}.log"

        print("=== CAREFLOW SCHEDULED RUNNER ===", flush=True)
        print("Credentials: Loaded from Keychain", flush=True)
        print(
            "Email delivery:",
            "ENABLED" if enable_email else "DISABLED",
            flush=True,
        )
        print("Execution log:", log_path, flush=True)

        with log_path.open("x") as log:
            log.write(
                f"CareFlow scheduled execution: {timestamp}\n"
            )
            log.flush()

            process = subprocess.Popen(
                [str(PYTHON), str(INGESTION)],
                cwd=ROOT,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )

            try:
                exit_code = process.wait(
                    timeout=TIMEOUT_SECONDS
                )

            except subprocess.TimeoutExpired:
                log.write(
                    "\nScheduled execution exceeded time limit.\n"
                )
                log.flush()

                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass

                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.wait()

                exit_code = 124

            log.write(
                f"\nScheduled runner exit code: {exit_code}\n"
            )

        print("Pipeline exit code:", exit_code, flush=True)
        print("Execution log:", log_path, flush=True)

        return exit_code


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--enable-email",
        action="store_true",
        help="Enable real email delivery for this execution",
    )

    args = parser.parse_args()

    try:
        sys.exit(run(args.enable_email))
    except Exception as error:
        print(
            f"Scheduled runner failed: "
            f"{type(error).__name__}: {error}",
            file=sys.stderr,
        )
        sys.exit(1)
