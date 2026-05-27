from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

from sports_analytics.storage.external import DropboxStorage, LocalMirrorStorage, upload_directory


def main() -> int:
    parser = argparse.ArgumentParser(description="Sube artefactos del pipeline a un storage externo.")
    parser.add_argument("--source", type=Path, default=Path("data"), help="Carpeta local a sincronizar.")
    parser.add_argument("--remote-prefix", default="/sports-analytics", help="Prefijo remoto en Dropbox o espejo local.")
    parser.add_argument("--provider", choices=["local", "dropbox"], default="local")
    parser.add_argument("--local-target", type=Path, default=Path("data_external_mirror"))
    args = parser.parse_args()

    if not args.source.exists():
        print(f"No existe la carpeta {args.source}")
        return 1

    if args.provider == "dropbox":
        token = os.getenv("DROPBOX_TOKEN")
        if not token:
            print("Falta configurar DROPBOX_TOKEN.")
            return 1
        storage = DropboxStorage(token)
    else:
        storage = LocalMirrorStorage(args.local_target)

    artifacts = upload_directory(storage, args.source, args.remote_prefix)
    print(f"Artefactos subidos: {len(artifacts)}")
    for artifact in artifacts[:20]:
        print(f"- {artifact.local_path} -> {artifact.remote_path}")
    if len(artifacts) > 20:
        print(f"... {len(artifacts) - 20} artefactos mas")
    return 0


if __name__ == "__main__":
    sys.exit(main())
