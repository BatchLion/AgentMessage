#!/usr/bin/env python
"""
Startup script for the Message History Visualizer
"""
import subprocess
import sys
import os
from pathlib import Path
import time
import tempfile
import fcntl
from contextlib import contextmanager

def ensure_pip():
    """Ensure pip is available (bootstrap with ensurepip if necessary)."""
    try:
        import pip  # noqa: F401
        return True
    except ImportError:
        try:
            import ensurepip
            ensurepip.bootstrap()
            import pip  # noqa: F401
            return True
        except Exception as e:
            print(f"❌ Unable to bootstrap pip in this environment: {e}")
            return False

@contextmanager
def install_lock(timeout: int = 60):
    """Serialize pip installs to avoid concurrent uninstall/upgrade races."""
    lock_path = Path(tempfile.gettempdir()) / "agentmessage_deps.lock"
    with open(lock_path, "w") as f:
        start = time.time()
        while True:
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.time() - start > timeout:
                    print("⚠️ Dependency install lock timed out; proceeding without exclusive lock.")
                    break
                time.sleep(0.5)
        try:
            yield
        finally:
            try:
                fcntl.flock(f, fcntl.LOCK_UN)
            except Exception:
                pass

def install_requirements():
    """Install required packages"""
    try:
        # Quick pre-check: if imports succeed, skip install
        try:
            import flask  # noqa: F401
            import flask_socketio  # noqa: F401
            print("✅ Dependencies are already installed")
            return True
        except ImportError:
            pass

        if not ensure_pip():
            print("⚠️  pip is not available; skipping auto-install. Please install dependencies manually.")
            return False

        req_file = Path(__file__).parent / "requirements.txt"
        with install_lock():
            subprocess.check_call([
                sys.executable, "-m", "pip", "install", "-r", str(req_file)
            ])
        print("✅ Dependencies installed successfully")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        return False
    return True

def check_database():
    """Check if database exists"""
    public_env = os.getenv("AGENTMESSAGE_PUBLIC_DATABLOCKS")
    data_dir = Path(public_env) if public_env else (Path(__file__).parent.parent / "data")
    db_path = data_dir / "message_history.db"
    if not db_path.exists():
        print(f"⚠️  Database not found at {db_path}")
        print("The visualizer will still start, but no data will be displayed until messages are added.")
        return False
    
    print(f"✅ Database found at {db_path}")
    return True

def main():
    print("🚀 Starting Message History Visualizer...")
    print("=" * 50)
    
    # Install dependencies
    if not install_requirements():
        return
    
    # Check database
    check_database()
    
    print("\n📊 Starting web server...")
    print("🌐 Open your browser and go to: http://localhost:5001")
    print("🔄 The interface will update in real-time as new messages are added")
    print("⏹️  Press Ctrl+C to stop the server")
    print("=" * 50)
    
    # Start the visualizer
    try:
        from message_visualizer import app, socketio, monitor
        monitor.start_monitoring()
        socketio.run(app, debug=False, host='0.0.0.0', port=5001)
    except KeyboardInterrupt:
        print("\n👋 Shutting down visualizer...")
    except Exception as e:
        print(f"❌ Error starting visualizer: {e}")

if __name__ == "__main__":
    main()