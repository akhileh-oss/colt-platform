# Built from the repository root (Milestone 26): `docker build -f apps/web/Dockerfile .` —
# pnpm workspace dependencies (`@colt/api-client`, `@colt/ui`) need the whole workspace in the
# build context, not `apps/web/` alone.

FROM node:22-slim AS base
RUN corepack enable

FROM base AS builder
WORKDIR /workspace

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/package.json
COPY packages/typescript/ packages/typescript/
RUN pnpm install --frozen-lockfile

COPY apps/web/ apps/web/
RUN pnpm --filter @colt/web build

FROM node:22-slim AS runtime
WORKDIR /app

RUN useradd --create-home --uid 1000 colt
# next.config.ts's `output: "standalone"` means only these three paths are needed at runtime —
# never the full pnpm workspace `node_modules`, whose symlinks don't survive a Docker `COPY`.
COPY --from=builder --chown=colt:colt /workspace/apps/web/.next/standalone ./
COPY --from=builder --chown=colt:colt /workspace/apps/web/.next/static ./apps/web/.next/static
COPY --from=builder --chown=colt:colt /workspace/apps/web/public ./apps/web/public
USER colt

EXPOSE 3000
CMD ["node", "apps/web/server.js"]
