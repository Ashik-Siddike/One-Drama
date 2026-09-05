"""OneDrama Studio - Master Desktop Launcher & Simultaneous Process Orchestrator.

Simultaneously launches:
1. FastAPI Backend Engine (http://127.0.0.1:8000)
2. Vite React Frontend Studio (http://localhost:5173)
3. Auto-opens System Browser (http://localhost:5173)
4. Monitors health and handles graceful shutdown
"""

import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request
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
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def check_backend_healthy() -> bool:
    try:
        req = urllib.request.Request("http://127.0.0.1:8000/api/health", headers={"User-Agent": "OneDramaLauncher"})
        with urllib.request.urlopen(req, timeout=1.0) as res:
            return res.status == 200
    except Exception:
        return False


def check_frontend_healthy() -> bool:
    try:
        req = urllib.request.Request("http://localhost:5173", headers={"User-Agent": "OneDramaLauncher"})
        with urllib.request.urlopen(req, timeout=1.0) as res:
            return res.status in (200, 304)
    except Exception:
        return False


def main():
    print(BANNER)
    spawned_procs = []

    # ----------------------------------------------------------------------- #
    # 1. Start / Check FastAPI Backend Engine (Port 8000)
    # ----------------------------------------------------------------------- #
    print(" [1/3] Initializing Backend Engine (FastAPI)...")
    if is_port_in_use(8000):
        print("       -> Backend is already active on http://127.0.0.1:8000")
    else:
        print("       -> Starting Python FastAPI server (server.py)...")
        b_flags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
        b_proc = subprocess.Popen(
            [VENV_PYTHON, "server.py"],
            cwd=ENGINE_DIR,
            creationflags=b_flags,
        )
        spawned_procs.append(("FastAPI Backend", b_proc))

    # ----------------------------------------------------------------------- #
    # 2. Start / Check Vite React Frontend (Port 5173)
    # ----------------------------------------------------------------------- #
    print(" [2/3] Initializing Frontend Studio (Vite React)...")
    if is_port_in_use(5173):
        print("       -> Frontend Studio is already active on http://localhost:5173")
    else:
        print("       -> Starting Vite dev server (npm run dev)...")
        npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
        f_flags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
        f_proc = subprocess.Popen(
            [npm_cmd, "run", "dev"],
            cwd=WEB_DIR,
            shell=True if sys.platform == "win32" else False,
            creationflags=f_flags,
        )
        spawned_procs.append(("Vite Frontend", f_proc))

    # ----------------------------------------------------------------------- #
    # 3. Concurrently Wait for Both Ports to Respond
    # ----------------------------------------------------------------------- #
    print(" [3/3] Synchronizing services on localhost...")
    max_wait = 20.0
    start_time = time.time()
    backend_ready = is_port_in_use(8000)
    frontend_ready = is_port_in_use(5173)

    while (not backend_ready or not frontend_ready) and (time.time() - start_time < max_wait):
        if not backend_ready:
            backend_ready = is_port_in_use(8000)
        if not frontend_ready:
            frontend_ready = is_port_in_use(5173)
        time.sleep(0.4)

    if backend_ready:
        print("       ✓ Backend Engine Online  -> http://127.0.0.1:8000")
    else:
        print("       ! Backend still starting up in background...")

    if frontend_ready:
        print("       ✓ Frontend Studio Online -> http://localhost:5173")
    else:
        print("       ! Frontend still starting up in background...")

    # ----------------------------------------------------------------------- #
    # 4. Auto-Launch Default Browser
    # ----------------------------------------------------------------------- #
    studio_url = "http://localhost:5173"
    print(f"\n [🚀] Launching OneDrama Studio in your browser: {studio_url}\n")
    time.sleep(0.5)
    webbrowser.open(studio_url)

    print("========================================================================")
    print("       🌟 ONEDRAMA AI STUDIO IS LIVE ON LOCALHOST 🌟")
    print("========================================================================")
    print("   • Frontend UI   : http://localhost:5173")
    print("   • Backend API   : http://127.0.0.1:8000")
    print("   • API Swagger   : http://127.0.0.1:8000/docs")
    print("========================================================================")
    print("   Keep this window open while using OneDrama.")
    print("   Press Ctrl + C in this window anytime to stop all services.\n")

    try:
        while True:
            time.sleep(1)
            # Check health of spawned processes
            for name, proc in spawned_procs:
                if proc.poll() is not None:
                    print(f" [!] {name} terminated with code {proc.returncode}")
    except KeyboardInterrupt:
        print("\n [x] Shutting down OneDrama Studio services cleanly...")
        for name, proc in spawned_procs:
            try:
                print(f"     Stopping {name}...")
                proc.terminate()
                proc.wait(timeout=2.0)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        print(" [✓] All local services stopped. Goodbye!\n")


if __name__ == "__main__":
    main()
