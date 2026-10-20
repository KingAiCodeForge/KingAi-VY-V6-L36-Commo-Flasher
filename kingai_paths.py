"""User-owned runtime paths and non-destructive file creation."""
from pathlib import Path
import os


def data_directory() -> Path:
    """Use explicit configuration first, then the platform's user data location."""
    configured = os.environ.get("KINGAI_FLASHER_DATA_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "kingai-flasher"


def write_new_file(path: str | Path, data: bytes) -> None:
    """Create an output exclusively. Existing evidence is never overwritten."""
    with Path(path).open("xb") as stream:
        stream.write(data)
