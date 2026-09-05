"""OneDrama Studio - Master Desktop Launcher & Process Manager.

Orchestrates:
1. FastAPI Backend Engine (Port 8000)
2. Vite React Frontend Studio (Port 5173)
3. Auto-launching the system default browser
4. Graceful shutdown on exit
"""

import os
import signal
import socket
import subprocess
import sys
import time
import webbrowser

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
ENGINE_DIR = os.path.join(ROOT_DIR, "one_drama_engine")
WEB_DIR = os.path.join(ROOT_DIR, "web")
VENV_PYTHON = os.path.join(ENGINE_DIR, ".venv", "Scripts", "python.exe")
if not os.path.isfile(VENV_PYTHON):
    VENV_PYTHON = sys.executable

BANNER = r"""
========================================================================
   ____               ____                                   ___    ____
  / __ \____  ___    / __ \_________ _____ ___  ____ _      /   |  /  _/
 / / / / __ \/ _ \  / / / / ___/ __ `/ __ `__ \/ __ `/     / /| |  / /  
/ /_/ / / / /  __/ / /_/ / /  / /_/ / / / / / / /_/ /     / ___ |_/ /   
\____/_/ /_/\___/ /_____/_/   \__,_/_/ /_/ /_/\__,_/     /_/  |_/___/   
                   3D Manhua & Drama AI Studio v1.0
========================================================================
"""

def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.6)
        return s.connect_ex(("127.0.0.1", port)) == 0


def wait_for_port(port: int, timeout: float = 15.0) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        if is_port_in_use(port):
            return True
        time.sleep(0.5)
    return False


def main():
    print(BANNER)
    procs = []

    # 1. Check / Start Backend
    if is_port_in_use(8000):
        print(" [✓] FastAPI Backend Engine is already running on http://127.0.0.1:8000")
    else:
        print(" [>] Starting FastAPI Engine (one_drama_engine/server.py)...")
        backend_proc = subprocess.Popen(
            [VENV_PYTHON, "server.py"],
            cwd=ENGINE_DIR,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
        )
        procs.append(("Backend", backend_proc))
        if wait_for_port(8000, 15.0):
            print(" [✓] FastAPI Backend Engine online at http://127.0.0.1:8000")
        else:
            print(" [!] Warning: Backend is taking longer than usual to bind port 8000.")

    # 2. Check / Start Frontend
    if is_port_in_use(5173):
        print(" [✓] Vite Frontend Studio is already running on http://localhost:5173")
    else:
        print(" [>] Starting Vite Dev Studio (web/)...")
        # Use npm.cmd on Windows
        npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
        frontend_proc = subprocess.Popen(
            [npm_cmd, "run", "dev"],
            cwd=WEB_DIR,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
        )
        procs.append(("Frontend", frontend_proc))
        if wait_for_port(5173, 15.0):
            print(" [✓] Vite Frontend Studio online at http://localhost:5173")
        else:
            print(" [!] Warning: Frontend is taking longer than usual to bind port 5173.")

    # 3. Open Browser
    studio_url = "http://localhost:5173"
    print(f"\n [🚀] Opening OneDrama Studio in your browser: {studio_url}\n")
    time.sleep(1.0)
    webbrowser.open(studio_url)

    print("------------------------------------------------------------------------")
    print(" Studio is active and ready for production!")
    print(" Keep this terminal open while using OneDrama.")
    print(" Press Ctrl + C in this terminal anytime to exit.")
    print("------------------------------------------------------------------------\n")

    try:
        while True:
            time.sleep(1)
            # Monitor spawned processes
            for name, p in procs:
                if p.poll() is not None:
                    print(f" [!] {name} stopped unexpectedly with code {p.returncode}")
    except KeyboardInterrupt:
        print("\n [x] Shutting down OneDrama Studio services...")
        for name, p in procs:
            try:
                print(f"     Stopping {name}...")
                p.terminate()
                p.wait(timeout=3)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass
        print(" [✓] All services stopped. Goodbye!")


if __name__ == "__main__":
    main()
