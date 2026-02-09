import argparse
import filecmp
import pathlib
import shutil
import sys

from config import paths

"""
uv run scripts/sync_agents_to_another_fastapi_project.py \
--api-path /path/to/api \
--backend-path /path/to/backend \
[--frontend-path /path/to/frontend]
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sincroniza agents, API routes/services e config do template para projeto de destino."
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
    parser.add_argument(
        "--frontend-path",
        type=pathlib.Path,
        help="Caminho da pasta frontend de destino (opcional, receberá routes/, components/, etc.).",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Substituir arquivos idênticos automaticamente sem perguntar.",
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


def files_are_identical(file1: pathlib.Path, file2: pathlib.Path) -> bool:
    """Check if two files are identical."""
    if not file1.exists() or not file2.exists():
        return False
    if not file1.is_file() or not file2.is_file():
        return False
    return filecmp.cmp(str(file1), str(file2), shallow=False)


def copy_file_with_confirmation(src: pathlib.Path, dest: pathlib.Path, auto_yes: bool = False) -> bool:
    """Copy file, asking for confirmation if destination exists and files are identical."""
    if not src.exists() or not src.is_file():
        return False

    if not dest.exists():
        # File doesn't exist, copy it
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        return True

    if files_are_identical(src, dest):
        # Files are identical, ask if should replace
        if not auto_yes:
            response = input(f"  Arquivo idêntico já existe: {dest}\n  Substituir? [s/N]: ").strip().lower()
            if response not in ("s", "sim", "y", "yes"):
                return False
        # User confirmed or auto_yes is True
        shutil.copy2(src, dest)
        return True
    else:
        # Files are different, always copy (merge behavior)
        shutil.copy2(src, dest)
        return True


def copy_merge(src: pathlib.Path, dest: pathlib.Path, auto_yes: bool = False) -> None:
    """Merge source directory into destination, asking for confirmation on identical files."""
    if not src.is_dir():
        raise FileNotFoundError(f"Fonte ausente: {src}")
    dest.mkdir(parents=True, exist_ok=True)

    for item in src.rglob("*"):
        if item.is_file():
            rel_path = item.relative_to(src)
            dest_file = dest / rel_path
            copy_file_with_confirmation(item, dest_file, auto_yes)


def main() -> None:
    args = parse_args()

    try:
        api_path = ensure_dir(args.api_path, "api de destino")
        backend_path = ensure_dir(args.backend_path, "backend de destino")
        frontend_path = args.frontend_path
        if frontend_path:
            frontend_path = ensure_dir(frontend_path, "frontend de destino")
    except (FileNotFoundError, NotADirectoryError) as err:
        print(err, file=sys.stderr)
        sys.exit(1)

    auto_yes = args.yes

    try:
        print("🔄 Iniciando sincronização do template...\n")

        # 1. Copy Agents (Merge individual agent folders)
        agents_src = paths.BASE_DIR / "agents"
        if agents_src.exists():
            for agent_dir in agents_src.iterdir():
                if agent_dir.is_dir():
                    print(f"📦 Sincronizando agente: {agent_dir.name}")
                    copy_merge(agent_dir, backend_path / "agents" / agent_dir.name, auto_yes)
                    print(f"  ✓ Agente sincronizado: {agent_dir.name}")

        # 2. Copy API Routes (Merge files)
        routes_src = paths.BASE_DIR / "src/api" / "routes" / "agents"
        if routes_src.exists():
            print("\n📁 Sincronizando routes/agents")
            copy_merge(routes_src, api_path / "routes" / "agents", auto_yes)
            print("  ✓ routes/agents sincronizado")

        # 3. Copy API Services (Merge files)
        services_src = paths.BASE_DIR / "src/api" / "services" / "agents"
        if services_src.exists():
            print("\n📁 Sincronizando services/agents")
            copy_merge(services_src, api_path / "services" / "agents", auto_yes)
            print("  ✓ services/agents sincronizado")

        # 4. Copy Config Files
        config_dest = backend_path / "config"
        config_dest.mkdir(exist_ok=True, parents=True)

        config_files = ["api_keys.py", "agents.py", "checkpointer.py", "paths.py", "prompt_cache.py"]
        print("\n⚙️  Sincronizando arquivos de configuração")
        for config_file in config_files:
            src_file = paths.BASE_DIR / "config" / config_file
            if src_file.exists():
                if copy_file_with_confirmation(src_file, config_dest / config_file, auto_yes):
                    print(f"  ✓ config/{config_file}")

        # 5. Copy Scripts
        scripts_dest = backend_path / "scripts"
        scripts_dest.mkdir(exist_ok=True, parents=True)
        script_files = ["uv_upgrade_pyproject_dependencies.py", "sync_agents_to_another_fastapi_project.py"]
        print("\n📜 Sincronizando scripts")
        for script_file in script_files:
            src_script = paths.BASE_DIR / "scripts" / script_file
            if src_script.exists():
                if copy_file_with_confirmation(src_script, scripts_dest / script_file, auto_yes):
                    print(f"  ✓ scripts/{script_file}")

        # 6. Copy Cursor Rules (all agents-template rules)
        rules_dest = backend_path.parent / ".cursor" / "rules"
        rules_dest.mkdir(exist_ok=True, parents=True)
        rule_files = [
            "agents-template-backend-agents-api.mdc",
            "agents-template-frontend-chat-dashboard.mdc",
            "agents-template-overview.mdc",
        ]
        print("\n📋 Sincronizando regras do Cursor")
        for rule_file in rule_files:
            src_rule = paths.BASE_DIR / ".cursor" / "rules" / rule_file
            if src_rule.exists():
                if copy_file_with_confirmation(src_rule, rules_dest / rule_file, auto_yes):
                    print(f"  ✓ .cursor/rules/{rule_file}")

        # 7. Copy Frontend Files (if frontend-path provided)
        if frontend_path:
            # Try to find frontend directory (could be at project root or backend parent)
            frontend_base = None
            possible_paths = [
                paths.BASE_DIR.parent / "frontend",  # frontend/ at project root
                paths.BASE_DIR / ".." / "frontend",  # Alternative path
            ]
            for possible_path in possible_paths:
                resolved = possible_path.resolve()
                if resolved.exists() and resolved.is_dir():
                    frontend_base = resolved
                    break
            
            if not frontend_base:
                print("\n⚠️  Diretório frontend não encontrado no template. Pulando sincronização do frontend.")
                print(f"   Procurou em: {[str(p.resolve()) for p in possible_paths]}")
            elif frontend_base.exists():
                print("\n🎨 Sincronizando arquivos do frontend")

                # 7.1 Copy Routes
                routes_src = frontend_base / "src" / "routes"
                if routes_src.exists():
                    print("  📁 Sincronizando routes/")
                    # Copy main route files
                    route_files = ["__root.tsx", "index.tsx"]
                    for route_file in route_files:
                        src_file = routes_src / route_file
                        if src_file.exists():
                            dest_file = frontend_path / "src" / "routes" / route_file
                            if copy_file_with_confirmation(src_file, dest_file, auto_yes):
                                print(f"    ✓ routes/{route_file}")
                    
                    # Copy chat and agent route directories
                    for route_dir in ["chat", "agent"]:
                        src_dir = routes_src / route_dir
                        if src_dir.exists() and src_dir.is_dir():
                            copy_merge(src_dir, frontend_path / "src" / "routes" / route_dir, auto_yes)
                            print(f"    ✓ routes/{route_dir}/")

                # 7.2 Copy Components
                components_src = frontend_base / "src" / "components"
                if components_src.exists():
                    print("  🧩 Sincronizando components/")
                    # Copy main component files
                    component_files = ["ChatView.tsx"]
                    for comp_file in component_files:
                        src_file = components_src / comp_file
                        if src_file.exists():
                            dest_file = frontend_path / "src" / "components" / comp_file
                            if copy_file_with_confirmation(src_file, dest_file, auto_yes):
                                print(f"    ✓ components/{comp_file}")
                    
                    # Copy component directories
                    for comp_dir in ["layouts", "sidebar"]:
                        src_dir = components_src / comp_dir
                        if src_dir.exists() and src_dir.is_dir():
                            copy_merge(src_dir, frontend_path / "src" / "components" / comp_dir, auto_yes)
                            print(f"    ✓ components/{comp_dir}/")

                # 7.3 Copy Hooks
                hooks_src = frontend_base / "src" / "hooks"
                if hooks_src.exists():
                    print("  🪝 Sincronizando hooks/")
                    hook_files = ["useUserId.ts", "use-mobile.ts"]
                    for hook_file in hook_files:
                        src_file = hooks_src / hook_file
                        if src_file.exists():
                            dest_file = frontend_path / "src" / "hooks" / hook_file
                            if copy_file_with_confirmation(src_file, dest_file, auto_yes):
                                print(f"    ✓ hooks/{hook_file}")

                # 7.4 Copy Lib
                lib_src = frontend_base / "src" / "lib"
                if lib_src.exists():
                    print("  📚 Sincronizando lib/")
                    lib_files = ["api.ts", "utils.ts"]
                    for lib_file in lib_files:
                        src_file = lib_src / lib_file
                        if src_file.exists():
                            dest_file = frontend_path / "src" / "lib" / lib_file
                            if copy_file_with_confirmation(src_file, dest_file, auto_yes):
                                print(f"    ✓ lib/{lib_file}")

                # 7.5 Copy Styles
                styles_src = frontend_base / "src" / "styles.css"
                if styles_src.exists():
                    print("  🎨 Sincronizando styles.css")
                    dest_file = frontend_path / "src" / "styles.css"
                    if copy_file_with_confirmation(styles_src, dest_file, auto_yes):
                        print("    ✓ src/styles.css")

                # 7.6 Copy Config Files
                config_files = {
                    "vite.config.ts": frontend_base / "vite.config.ts",
                    "tsconfig.json": frontend_base / "tsconfig.json",
                }
                print("  ⚙️  Sincronizando arquivos de configuração do frontend")
                for config_name, src_file in config_files.items():
                    if src_file.exists():
                        dest_file = frontend_path / config_name
                        if copy_file_with_confirmation(src_file, dest_file, auto_yes):
                            print(f"    ✓ {config_name}")

        print("\n✅ Sincronização concluída com sucesso!")
        print("\n📝 Próximos passos:")
        print("  Backend:")
        print("    1. Instale as dependências:")
        print("       - markitdown (para processamento de arquivos)")
        print("       - langgraph, langchain, etc. (conforme necessário)")
        print("    2. Configure as variáveis de ambiente (API keys)")
        print("    3. Adapte o checkpointer para produção (substitua SQLite se necessário)")
        print("    4. Configure o main.py do FastAPI com o lifespan correto")
        if frontend_path:
            print("  Frontend:")
            print("    1. Instale as dependências: bun install")
            print("    2. Instale AI Elements: bunx ai-elements@latest add message conversation reasoning")
            print("    3. Adapte o useUserId hook para seu sistema de autenticação")
            print("    4. Configure o vite.config.ts proxy se necessário")
            print("    5. Verifique o tsconfig.json para path aliases (@/ → src/)")

    except FileNotFoundError as err:
        print(f"❌ Erro: fonte não encontrada. {err}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Sincronização cancelada pelo usuário.", file=sys.stderr)
        sys.exit(1)
    except Exception as err:  # pragma: no cover - unexpected failure
        print(f"❌ Falha ao copiar: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
