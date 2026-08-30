# City Hospital frontend — Next.js standalone.
#
# Build from the repository root:
#   docker build -f docker/frontend.Dockerfile -t cityhospital-web .
#
# NEXT_PUBLIC_* values are inlined into the client bundle at BUILD time, so the
# default below (`NEXT_PUBLIC_API_BASE=""`) bakes in "call my own origin". One
# image then works in every environment, provided the ingress routes /api and
# /ws to the backend on the same hostname. Override the build arg only when the
# API lives on a different hostname — that produces an environment-specific
# image, which is what you are trying to avoid.
#
# The server side is different: INTERNAL_API_BASE is a plain variable read at
# RUN time, so Server Components reach the backend over cluster DNS without a
# rebuild. See frontend/src/lib/config.ts.

# --------------------------------------------------------------------------- #
# Stage 1 — dependencies
# --------------------------------------------------------------------------- #
FROM node:22-alpine AS deps
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
# `npm ci` installs exactly the lockfile, and fails rather than silently
# resolving something newer — the property you want in a build.
RUN npm ci

# --------------------------------------------------------------------------- #
# Stage 2 — build
# --------------------------------------------------------------------------- #
FROM node:22-alpine AS builder
WORKDIR /app

ARG NEXT_PUBLIC_API_BASE=""
ARG NEXT_PUBLIC_WS_BASE=""
ENV NEXT_PUBLIC_API_BASE=$NEXT_PUBLIC_API_BASE \
    NEXT_PUBLIC_WS_BASE=$NEXT_PUBLIC_WS_BASE \
    NEXT_TELEMETRY_DISABLED=1

COPY --from=deps /app/node_modules ./node_modules
COPY frontend/ ./
RUN npm run build

# --------------------------------------------------------------------------- #
# Stage 3 — runtime
# --------------------------------------------------------------------------- #
FROM node:22-alpine AS runtime
WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

RUN addgroup --system --gid 10001 nodejs \
 && adduser --system --uid 10001 nextjs

# `output: "standalone"` produces server.js plus only the node_modules actually
# imported, so none of the build toolchain ships.
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/public ./public

USER nextjs
EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
    CMD node -e "fetch('http://127.0.0.1:3000/').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

CMD ["node", "server.js"]
