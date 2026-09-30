# =============================================================================
# STAGE 1 — Vite bundle via Bun
# =============================================================================
FROM oven/bun:1.3.14-slim AS builder

WORKDIR /app

COPY package.json bun.lock ./
RUN bun install --frozen-lockfile

COPY . .

# VITE_* are build-time: the image build cannot read config/app/*.yaml, so compose passes them
# as build args (config/docker/compose.<env>.yaml > nginx.build.args) mirroring the yaml
# `vite:` block. Vite exposes process-env VITE_* to `import.meta.env` natively.
ARG VITE_BACKEND_URL
ARG VITE_FRONTEND_URL

ENV VITE_BACKEND_URL=${VITE_BACKEND_URL} \
    VITE_FRONTEND_URL=${VITE_FRONTEND_URL}

RUN bun run build

# =============================================================================
# STAGE 2 — nginx serving the bundle + reverse proxy to the backend
# =============================================================================
FROM nginx:1.29.8-trixie AS nginx-runtime

COPY --from=builder /app/dist /usr/share/nginx/html

CMD ["nginx", "-g", "daemon off;"]
