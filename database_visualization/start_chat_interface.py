#!/usr/bin/env python
"""
Startup script for the Message Interface
"""
# (Removed top-level eventlet import; it will be imported after dependencies are ensured)
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

def check_dependencies():
    """Check if required packages are installed"""
    try:
        import flask  # noqa: F401
        import flask_socketio  # noqa: F401
        import eventlet  # noqa: F401
        print("✅ Dependencies are already installed")
        return True
    except ImportError:
        print("📦 Installing required dependencies...")
        try:
            if not ensure_pip():
                print("⚠️  pip is not available; skipping auto-install. Please install dependencies manually.")
                return False
            req_file = Path(__file__).parent / "requirements.txt"
            with install_lock():
                subprocess.check_call([
                    sys.executable, "-m", "pip", "install", "-r", str(req_file)
                ])
            print("✅ Dependencies installed successfully")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install dependencies: {e}")
            return False

def check_database():
    """Check if database exists"""
    public_env = os.getenv("AGENTMESSAGE_PUBLIC_DATABLOCKS")
    data_dir = Path(public_env) if public_env else (Path(__file__).parent.parent / "data")
    db_path = data_dir / "message_history.db"
    if not db_path.exists():
        print(f"⚠️  Database not found at {db_path}")
        print("The interface will still start, but no data will be displayed until messages are added.")
        return False
    
    print(f"✅ Database found at {db_path}")
    return True

def main():
    print("🚀 Starting Modern Message Interface...")
    print("=" * 50)
    
    # Check dependencies
    if not check_dependencies():
        return

    # Import and monkey patch eventlet only after dependencies are ready
    import eventlet
    eventlet.monkey_patch()
    
    # Check database
    check_database()
    
    print("\n💬 Starting message interface...")
    print("🌐 Open your browser and go to: http://localhost:5002")
    print("💡 Features:")
    print("   • Real-time message interface")
    print("   • Conversation sidebar")
    print("   • Agent status panel")
    print("   • Modern UI design")
    print("⏹️  Press Ctrl+C to stop the server")
    print("=" * 50)
    
    # Start the interface
    try:
        from message_interface import app, socketio
        socketio.run(app, debug=False, host='0.0.0.0', port=5002)
    except KeyboardInterrupt:
        print("\n👋 Shutting down message interface...")
    except Exception as e:
        print(f"❌ Error starting interface: {e}")

if __name__ == "__main__":
    main()