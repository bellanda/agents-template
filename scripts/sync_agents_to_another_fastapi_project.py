import argparse
import pathlib
import shutil
import sys

from environment import paths

"""
uv run scripts/sync_agents_to_another_fastapi_project.py \
--api-path /path/to/api \
--backend-path /path/to/backend
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Substitui pastas agents do template no projeto de destino.")
    parser.add_argument(
        "--api-path",
        required=True,
        type=pathlib.Path,
        help="Caminho da pasta api de destino (contendo routes/ e services/).",
    )
    parser.add_argument(
        "--backend-path",
        required=True,
        type=pathlib.Path,
        help="Caminho da pasta backend de destino (receberá agents/ e environment/ai_keys.py).",
    )
    return parser.parse_args()


def ensure_dir(path: pathlib.Path, label: str) -> pathlib.Path:
    """Resolve and validate a directory path."""
    resolved = path.expanduser().resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"{label} não encontrado: {resolved}")
    if not resolved.is_dir():
        raise NotADirectoryError(f"{label} precisa ser um diretório: {resolved}")
    return resolved


def replace_tree(src: pathlib.Path, dest: pathlib.Path) -> None:
    """Replace destination directory with a copy of source."""
    if not src.is_dir():
        raise FileNotFoundError(f"Fonte ausente: {src}")
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dest)


def main() -> None:
    args = parse_args()

    try:
        api_path = ensure_dir(args.api_path, "api de destino")
        backend_path = ensure_dir(args.backend_path, "backend de destino")
    except (FileNotFoundError, NotADirectoryError) as err:
        print(err, file=sys.stderr)
        sys.exit(1)

    try:
        for dir in (paths.BASE_DIR / "agents").iterdir():
            if dir.is_dir():
                replace_tree(dir, backend_path / "agents" / dir.name)
                print(f"Copiado {dir.name} -> {backend_path / 'agents' / dir.name}")

        replace_tree(paths.BASE_DIR / "api" / "routes" / "agents", api_path / "routes" / "agents")
        print(f"Copiado routes/agents -> {api_path / 'routes' / 'agents'}")

        replace_tree(paths.BASE_DIR / "api" / "services" / "agents", api_path / "services" / "agents")
        print(f"Copiado services/agents -> {api_path / 'services' / 'agents'}")

        shutil.copy(paths.BASE_DIR / "environment" / "api_keys.py", backend_path / "environment" / "api_keys.py")
        print(f"Copiado environment/api_keys.py -> {backend_path / 'environment' / 'api_keys.py'}")

    except FileNotFoundError as err:
        print(f"Erro: fonte não encontrada. {err}", file=sys.stderr)
        sys.exit(1)
    except Exception as err:  # pragma: no cover - unexpected failure
        print(f"Falha ao copiar: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
