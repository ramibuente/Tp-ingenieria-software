from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil


@dataclass(frozen=True)
class UploadedArtifact:
    local_path: Path
    remote_path: str


class LocalMirrorStorage:
    """Storage de respaldo para desarrollo: copia artefactos a otra carpeta local."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def upload_file(self, local_path: Path, remote_path: str) -> UploadedArtifact:
        target = self.root / remote_path.lstrip("/")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(local_path, target)
        return UploadedArtifact(local_path=local_path, remote_path=str(target))


class DropboxStorage:
    """Cliente opcional para Dropbox.

    Requiere instalar `dropbox` y configurar DROPBOX_TOKEN. Se importa de forma
    diferida para que el resto del proyecto funcione aunque no se use Dropbox.
    """

    def __init__(self, access_token: str) -> None:
        try:
            import dropbox
        except ImportError as exc:
            raise RuntimeError("Para usar Dropbox ejecutar: pip install dropbox") from exc
        self.client = dropbox.Dropbox(access_token)

    def upload_file(self, local_path: Path, remote_path: str) -> UploadedArtifact:
        with local_path.open("rb") as file:
            self.client.files_upload(file.read(), remote_path, mode=_dropbox_overwrite_mode())
        return UploadedArtifact(local_path=local_path, remote_path=remote_path)


def upload_directory(storage: LocalMirrorStorage | DropboxStorage, local_dir: Path, remote_prefix: str) -> list[UploadedArtifact]:
    artifacts = []
    for path in sorted(local_dir.rglob("*")):
        if not path.is_file():
            continue
        remote_path = f"{remote_prefix.rstrip('/')}/{path.relative_to(local_dir).as_posix()}"
        artifacts.append(storage.upload_file(path, remote_path))
    return artifacts


def _dropbox_overwrite_mode():
    import dropbox

    return dropbox.files.WriteMode.overwrite
