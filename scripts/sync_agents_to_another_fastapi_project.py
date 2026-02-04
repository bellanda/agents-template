import argparse
import pathlib
import shutil
import sys

from config import paths

"""
uv run scripts/sync_agents_to_another_fastapi_project.py \
--api-path /path/to/api \
--backend-path /path/to/backend
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Substitui pastas agents do template no projeto de destino (Minimalist Version)."
    )
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
        help="Caminho da pasta backend de destino (receberá agents/ e config/).",
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


def copy_merge(src: pathlib.Path, dest: pathlib.Path) -> None:
    """Merge source directory into destination without deleting existing files."""
    if not src.is_dir():
        raise FileNotFoundError(f"Fonte ausente: {src}")
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dest, dirs_exist_ok=True)


def main() -> None:
    args = parse_args()

    try:
        api_path = ensure_dir(args.api_path, "api de destino")
        backend_path = ensure_dir(args.backend_path, "backend de destino")
    except (FileNotFoundError, NotADirectoryError) as err:
        print(err, file=sys.stderr)
        sys.exit(1)

    try:
        # 1. Copy Agents (Merge individual agent folders)
        for dir in (paths.BASE_DIR / "agents").iterdir():
            if dir.is_dir():
                copy_merge(dir, backend_path / "agents" / dir.name)
                print(f"✓ Sincronizado agente: {dir.name}")

        # 2. Copy API Routes (Merge files)
        copy_merge(paths.BASE_DIR / "api" / "routes" / "agents", api_path / "routes" / "agents")
        print("✓ Sincronizado routes/agents")

        # 3. Copy API Services (Merge files)
        copy_merge(paths.BASE_DIR / "api" / "services" / "agents", api_path / "services" / "agents")
        print("✓ Sincronizado services/agents")

        # 4. Copy Config Files
        env_dest = backend_path / "config"
        env_dest.mkdir(exist_ok=True)

        for config_file in ["api_keys.py", "agents.py"]:
            src_file = paths.BASE_DIR / "config" / config_file
            if src_file.exists():
                shutil.copy(src_file, env_dest / config_file)
                print(f"✓ Copiado config/{config_file}")

        # 5. Copy Scripts
        (backend_path / "scripts").mkdir(exist_ok=True, parents=True)
        shutil.copy(
            paths.BASE_DIR / "scripts" / "uv_upgrade_pyproject_dependencies.py",
            backend_path / "scripts" / "uv_upgrade_pyproject_dependencies.py",
        )
        print("✓ Copiado scripts/uv_upgrade_pyproject_dependencies.py")

        # 6. Copy Cursor Rules
        rules_dest = backend_path.parent / ".cursor" / "rules"
        rules_dest.mkdir(exist_ok=True, parents=True)
        rule_file = "backend-ai-fastapi-langchain.mdc"
        src_rule = paths.BASE_DIR / ".cursor" / "rules" / rule_file
        if src_rule.exists():
            shutil.copy(src_rule, rules_dest / rule_file)
            print(f"✓ Copiado .cursor/rules/{rule_file}")

        print("\n✅ Sincronização concluída com sucesso!")
        print("Lembre-se de instalar as dependências no projeto de destino: markitdown, etc.")

    except FileNotFoundError as err:
        print(f"❌ Erro: fonte não encontrada. {err}", file=sys.stderr)
        sys.exit(1)
    except Exception as err:  # pragma: no cover - unexpected failure
        print(f"❌ Falha ao copiar: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
