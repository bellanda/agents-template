#!/usr/bin/env bash
# Local check — herda o TTY (cores + interatividade preservadas), só filtra
# o output extenso do prettier e do vite.
#
# Uso: bash check.sh [--serial]
#   --serial (ou PYTEST_WORKERS=0): pytest sem xdist. Default = pytest-xdist com
#   PYTEST_WORKERS workers (default min(nproc, 8)); cada worker clona o template do banco
#   de teste (ver backend/tests/conftest.py). TEST_DB_PORT exportado vai ao compose + conftest.
#
# Script CANÔNICO — padronizado entre os projetos.
# - PROJECT vem do nome da pasta → isola o compose de teste por projeto.
# - Passos opcionais são auto-detectados pela presença do arquivo/testes.
# - DB de teste é efêmero: `down -v` recria o cluster a cada run e evita o erro
#   "template database template1 has a collation version" após troca de glibc/imagem.
# - Roda TODOS os passos mesmo com falha (um run mostra o estrago inteiro), mas
#   acumula os que falharam e sai != 0 no fim. Sem isso o exit code era só o do
#   ÚLTIMO passo e um pytest vermelho saía como verde.

set -uo pipefail

REPO="$(cd "$(dirname "$0")" && pwd)"
PROJECT="$(basename "${REPO}")"

FAILED=()

if [ "${1:-}" = "--serial" ]; then
    PYTEST_WORKERS=0
    shift
fi
# xdist: 8 foi o ponto doce medido no kailos (14 vCPU: `-n auto` perdeu para 8 por contenção
# de Postgres/IO). O Postgres é um só; cada worker tem o seu banco clonado.
DEFAULT_WORKERS="$(nproc 2>/dev/null || echo 4)"
[ "${DEFAULT_WORKERS}" -gt 8 ] && DEFAULT_WORKERS=8
PYTEST_WORKERS="${PYTEST_WORKERS:-${DEFAULT_WORKERS}}"
PYTEST_ARGS=(--tb=short)
if [ "${PYTEST_WORKERS}" != "0" ]; then
    PYTEST_ARGS+=(-n "${PYTEST_WORKERS}")
fi

# Vite build: keep everything except `dist/...` chunk lines under 500 kB.
build_filter() {
    awk '
        /^dist\// {
            for (i = 1; i <= NF; i++) {
                if ($i ~ /^[0-9]+(\.[0-9]+)?$/ && $(i+1) == "kB") {
                    if ($i + 0 >= 500) print
                    next
                }
            }
            next
        }
        { print }
    '
}

step() { printf '\n\033[1;36m── %s ──\033[0m\n' "$*"; }

# Roda um passo, registra a falha e segue. O nome vira a linha do resumo final.
run() {
    local name="$1"; shift
    step "${name}"
    "$@" || FAILED+=("${name}")
}

summary() {
    if [ "${#FAILED[@]}" -eq 0 ]; then
        printf '\n\033[1;32m✓ todos os passos passaram\033[0m\n'
        return 0
    fi
    printf '\n\033[1;31m✗ %d passo(s) falharam:\033[0m\n' "${#FAILED[@]}"
    printf '  \033[31m•\033[0m %s\n' "${FAILED[@]}"
    return 1
}

# ---- backend
cd "${REPO}/backend"
run "ruff format"           uv run ruff format
run "ruff check --fix"      uv run ruff check --fix

# ---- tests (DB efêmero: down -v garante cluster novo, sem drift de collation)
# O template não traz testes (regra do projeto: só quando pedidos). Sem nenhum test_*.py o pytest
# sai com 5 ("no tests collected") e o check ficaria vermelho à toa — pula o DB inteiro então.
if [ -n "$(find "${REPO}/backend/tests" -name 'test_*.py' -print -quit)" ]; then
    cd "${REPO}/backend/tests"
    step "docker compose up (fresh)"
    docker compose -p "${PROJECT}-tests" -f compose.yml down -v --remove-orphans
    if docker compose -p "${PROJECT}-tests" -f compose.yml up -d --wait; then
        cd "${REPO}/backend"
        run "pytest" uv run pytest "${PYTEST_ARGS[@]}"
        cd "${REPO}/backend/tests"
    else
        # Porta de teste ocupada por outro projeto (TEST_DB_PORT) ou
        # healthcheck estourado. Rodar pytest agora o apontaria para o banco de
        # OUTRO projeto e a suíte passaria medindo a coisa errada.
        FAILED+=("docker compose up (DB de teste)")
        printf '\033[1;31m✗ DB de teste não subiu — pytest PULADO (rodaria contra outro banco)\033[0m\n'
    fi

    step "docker compose down"
    docker compose -p "${PROJECT}-tests" -f compose.yml down -v --remove-orphans
else
    step "pytest (nenhum test_*.py — pulado)"
fi

# ---- frontend
cd "${REPO}/frontend"
run "prettier" bunx prettier . --write --log-level warn
run "vitest"   bun run test

step "tsc + vite build"
bun run build 2>&1 | build_filter
[ "${PIPESTATUS[0]}" -eq 0 ] || FAILED+=("tsc + vite build")

summary
