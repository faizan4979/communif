"""
Startup runner script for DDSS - Dawood Data Science Society.
Launches both the FastAPI backend (port 8000) and the Streamlit frontend (port 8501)
concurrently and manages their lifecycle cleanly.
"""

import os
import sys
import time
import subprocess
import signal

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Resolve appropriate Python interpreter
VENV_PYTHON = os.path.join(BASE_DIR, ".venv_new", "Scripts", "python.exe")
PYTHON_EXE = VENV_PYTHON if os.path.exists(VENV_PYTHON) else sys.executable


def main():
    print("=" * 75)
    print("  DDSS - Dawood Data Science Society Members & Volunteer Registration")
    print("  Department of Data Science, Dawood University of Engg & Tech (DUET)")
    print("=" * 75)
    print(f"[*] Base Directory: {BASE_DIR}")
    print(f"[*] Python Interpreter: {PYTHON_EXE}")

    # Set up environment with project root in PYTHONPATH
    env = os.environ.copy()
    env["PYTHONPATH"] = BASE_DIR

    processes = []

    try:
        # 1. Start FastAPI Backend on Port 8000
        print("\n[+] Starting FastAPI backend on http://127.0.0.1:8000 ...")
        backend_cmd = [
            PYTHON_EXE,
            "-m",
            "uvicorn",
            "backend.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000"
        ]
        backend_proc = subprocess.Popen(backend_cmd, cwd=BASE_DIR, env=env)
        processes.append(backend_proc)

        # Brief delay to allow FastAPI to bind port
        time.sleep(2)

        # 2. Start Streamlit Frontend on Port 8501
        print("[+] Starting Streamlit frontend on http://127.0.0.1:8501 ...")
        frontend_cmd = [
            PYTHON_EXE,
            "-m",
            "streamlit",
            "run",
            os.path.join(BASE_DIR, "frontend", "app.py"),
            "--server.port",
            "8501",
            "--server.address",
            "127.0.0.1",
            "--server.headless",
            "true"
        ]
        frontend_proc = subprocess.Popen(frontend_cmd, cwd=BASE_DIR, env=env)
        processes.append(frontend_proc)

        print("\n" + "=" * 75)
        print("  SYSTEM RUNNING SUCCESSFULLY")
        print("=" * 75)
        print("  🌐 Public Portal / Frontend:  http://127.0.0.1:8501")
        print("  ⚙️  FastAPI Backend REST API:  http://127.0.0.1:8000")
        print("  📖 Interactive Swagger Docs:  http://127.0.0.1:8000/docs")
        print("=" * 75)
        print("=" * 75)
        print("  Press Ctrl+C in this console to shut down both services.\n")

        # Keep alive while monitoring child processes
        while True:
            time.sleep(1)
            for p in processes:
                if p.poll() is not None:
                    print(f"[!] Process {p.pid} terminated unexpectedly.")
                    return

    except KeyboardInterrupt:
        print("\n[*] Shutting down DDSS services gracefully...")
    finally:
        for p in processes:
            if p.poll() is None:
                p.terminate()
                try:
                    p.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    p.kill()
        print("[*] All processes stopped. Goodbye!")


if __name__ == "__main__":
    main()
