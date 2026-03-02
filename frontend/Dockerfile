# Multi-stage frontend Dockerfile.
# dev    — hot-reload dev server (used by docker compose)
# builder — production Next.js build
# runner  — minimal standalone production image

ARG NODE_VERSION=22

# ---- base: Node + pnpm ----
FROM node:${NODE_VERSION}-alpine AS base
RUN npm install -g pnpm@9
ENV NEXT_TELEMETRY_DISABLED=1

# ---- deps: install all dependencies ----
FROM base AS deps
WORKDIR /app
COPY package.json ./
RUN pnpm install

# ---- dev: mount source via volume, run next dev ----
FROM base AS dev
WORKDIR /app
# node_modules come from the named volume populated by the deps stage or
# by running `docker compose run --rm frontend pnpm install`
EXPOSE 3000
ENV NODE_ENV=development
# WATCHPACK_POLLING enables file-system polling inside Docker so Next.js
# hot-reload works across the host→container volume boundary.
ENV WATCHPACK_POLLING=true
CMD ["sh", "-c", "pnpm install && pnpm dev"]

# ---- builder: production build ----
FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN pnpm build

# ---- runner: minimal production image ----
FROM node:${NODE_VERSION}-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 nodejs \
    && adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"
CMD ["node", "server.js"]
