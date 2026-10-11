"""Small file-based model registry. Load only artifacts created by your trusted training code."""
from pathlib import Path
import json
import shutil


def registry_root():
    return Path(__file__).resolve().parents[2] / "models"


def model_dir(version: str, root: Path | None = None) -> Path:
    if not version or not all(c.isalnum() or c in "-_" for c in version):
        raise ValueError("Invalid model version")
    return (root or registry_root()) / version


def register(version: str, files: dict[str, str | Path], metadata: dict, root: Path | None = None):
    destination = model_dir(version, root)
    if destination.exists():
        raise FileExistsError(f"Model version {version} already exists")
    destination.mkdir(parents=True)
    try:
        for name, source in files.items():
            if Path(name).name != name:
                raise ValueError("Artifact name must be a filename")
            shutil.copy2(source, destination / name)
        (destination / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    except Exception:
        shutil.rmtree(destination)
        raise
    return destination


def activate(version: str, root: Path | None = None):
    root = root or registry_root()
    target = model_dir(version, root)
    if not (target / "metadata.json").exists():
        raise FileNotFoundError(f"Unknown version: {version}")
    pointer = root / "active.json"
    pending = root / "active.tmp"
    pending.write_text(json.dumps({"version": version}), encoding="utf-8")
    pending.replace(pointer)


def active_version(root: Path | None = None):
    return json.loads(((root or registry_root()) / "active.json").read_text(encoding="utf-8"))["version"]


def list_versions(root: Path | None = None):
    return sorted(p.name for p in (root or registry_root()).glob("*/metadata.json") for p in [p.parent])
