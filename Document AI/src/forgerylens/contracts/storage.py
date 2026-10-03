import re
from pathlib import Path

def make_artifact_ref(sha256: str, name: str) -> str:
    """Create an artifact reference ID."""
    if not re.match(r"^[a-fA-F0-9]{64}$", sha256):
        raise ValueError("Invalid sha256")
    if not re.match(r"^[A-Za-z0-9._-]+$", name) or name in (".", ".."):
        raise ValueError("Invalid name")
    return f"artifact:{sha256}/{name}"

def resolve_artifact_ref(ref: str, storage_root: Path) -> Path:
    """Resolve an artifact reference to a Path inside storage_root."""
    if not ref.startswith("artifact:"):
        raise ValueError("Must start with artifact:")
    
    parts = ref[len("artifact:"):].split("/")
    if len(parts) != 2:
        raise ValueError("Invalid reference format")
        
    sha256, name = parts
    
    if not re.match(r"^[a-fA-F0-9]{64}$", sha256):
        raise ValueError("Invalid sha256")
    if not re.match(r"^[A-Za-z0-9._-]+$", name) or name in (".", ".."):
        raise ValueError("Invalid name")
        
    resolved = (storage_root / sha256 / name).resolve()
    storage_root = storage_root.resolve()
    
    try:
        resolved.relative_to(storage_root)
    except ValueError:
        raise ValueError("Path traversal detected")
        
    return resolved
