# Lumi photo review: the Mastra service, built and run as a bundled Node server.
# Build:  docker build -t lumi-mastra mastra
# Run:    see docker-compose.yml at the repo root. Don't publish port 4111:
#         Mastra also serves its built-in agent API and Studio (docs/team/deploy.md).

# Build stage: install everything (the mastra CLI is a dev dependency) and bundle.
FROM node:22-bookworm-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY tsconfig.json ./
COPY src ./src
# Bundles into .mastra/output with its own node_modules.
RUN npm run build

# Run stage: only the bundle, no dev dependencies or sources.
FROM node:22-bookworm-slim
WORKDIR /app
ENV NODE_ENV=production \
    PORT=4111 \
    MASTRA_HOST=0.0.0.0 \
    MASTRA_TELEMETRY_DISABLED=1
COPY --from=build --chown=node:node /app/.mastra/output ./
USER node
EXPOSE 4111

# Mastra's own GET /health ({"success":true}). It doesn't call Gemini.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:4111/health').then(r => process.exit(r.ok ? 0 : 1), () => process.exit(1))"

CMD ["node", "index.mjs"]
