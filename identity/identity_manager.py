"""Identity manager"""

import os
import json
import stat
from pathlib import Path
from typing import Optional
from .models import AgentIdentity
from .did_generator import DIDGenerator

class IdentityManager:
    """Identity manager"""
    
    def __init__(self):
        self.did_generator = DIDGenerator()
        self.memory_path = self._get_memory_path()
        self.identity_file = self.memory_path / "identity.json"
        
        # Ensure directory exists with restrictive permissions
        self.memory_path.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.memory_path, 0o700)
        except Exception:
            # Best effort; not fatal
            pass

        # If identity file already exists, ensure it is locked (read-only/immutable where possible)
        if self.identity_file.exists():
            self._lock_identity_file()
    
    def _get_memory_path(self) -> Path:
        """Get memory path"""
        memory_path = os.getenv('AGENTMESSAGE_MEMORY_PATH')
        if memory_path:
            return Path(memory_path)
        else:
            # Default path
            return Path.home() / ".agentmessage" / "memory"

    def _lock_identity_file(self) -> None:
        """
        Apply file-system level protections to the identity file (best-effort).
        If you truly need to rotate identity.json:
        - On macOS, clear the immutable flag: sudo chflags nouchg /path/to/identity.json
        - Adjust permissions if necessary: chmod u+w /path/to/identity.json
        - Remove or replace the file, then restart the process to re-apply protections automatically.
        """
        try:
            # Set read-only for owner
            os.chmod(self.identity_file, 0o400)
        except Exception:
            pass
        # Try to set immutable flag on platforms that support it (macOS/BSD)
        try:
            if hasattr(os, "chflags") and hasattr(stat, "UF_IMMUTABLE"):
                os.chflags(self.identity_file, stat.UF_IMMUTABLE)
        except Exception:
            # Not all filesystems or permissions allow this; best-effort only
            pass
    
    def load_identity(self) -> Optional[AgentIdentity]:
        """Load identity information"""
        if not self.identity_file.exists():
            return None
        
        try:
            with open(self.identity_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return AgentIdentity.from_dict(data)
        except Exception as e:
            print(f"Failed to load identity information: {e}")
            return None
    
    def save_identity(self, identity: AgentIdentity) -> bool:
        """Save identity information.
        Create-once semantics: if identity.json already exists, refuse to overwrite.
        On first creation, set read-only permissions and attempt to set immutable flags (best-effort).
        """
        try:
            # Refuse to overwrite if file already exists
            if self.identity_file.exists():
                print("Identity file already exists; refusing to overwrite.")
                return False

            # Ensure parent directory exists with restrictive perms
            self.memory_path.mkdir(parents=True, exist_ok=True)
            try:
                os.chmod(self.memory_path, 0o700)
            except Exception:
                pass

            # Exclusive creation so we don't race and overwrite
            with open(self.identity_file, 'x', encoding='utf-8') as f:
                json.dump(identity.to_dict(), f, indent=2, ensure_ascii=False)

            # Apply file lock protections
            self._lock_identity_file()
            return True
        except FileExistsError:
            print("Identity file already exists; refusing to overwrite.")
            return False
        except Exception as e:
            print(f"Failed to save identity information: {e}")
            return False
    
    def create_identity(self, name: str, description: str, capabilities: list) -> AgentIdentity:
        """Create new identity information"""
        did = self.did_generator.generate_did(name)
        identity = AgentIdentity(
            name=name,
            description=description,
            capabilities=capabilities,
            did=did
        )
        return identity
    
    def has_identity(self) -> bool:
        """Check if identity information already exists"""
        return self.identity_file.exists() and self.load_identity() is not None