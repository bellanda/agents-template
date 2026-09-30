#!/usr/bin/env bash
# Local check — herda o TTY (cores + interatividade preservadas), só filtra
# o output extenso do prettier e do vite.
#
# Uso: bash check.sh
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
        run "pytest" uv run pytest --tb=short
        cd "${REPO}/backend/tests"
    else
        # Porta 5433 ocupada por outro projeto (os 5 composes bindam a mesma) ou
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
