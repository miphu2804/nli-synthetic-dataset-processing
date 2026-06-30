from pathlib import Path


def project_root() -> Path:
    """Return the runtime project root for local repo and Docker layouts."""
    backend_or_root = Path(__file__).resolve().parents[2]
    if backend_or_root.name == "backend":
        return backend_or_root.parent
    return backend_or_root


def data_root() -> Path:
    return project_root() / "data"


def pipeline_root() -> Path:
    return project_root() / ".pipeline"


def resolve_runtime_path(path: str | Path) -> Path:
    resolved = Path(path).expanduser()
    if resolved.is_absolute():
        return resolved.resolve()
    if resolved.parts and resolved.parts[0] in {"data", ".pipeline"}:
        return (project_root() / resolved).resolve()
    return resolved.resolve()


def resolve_data_path(*parts: str) -> Path:
    return data_root().joinpath(*parts).resolve()
