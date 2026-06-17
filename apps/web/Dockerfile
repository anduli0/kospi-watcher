# syntax=docker/dockerfile:1
# KOSPI-WATCHER Next.js frontend. Build context is apps/web:
#   docker build -f apps/web/Dockerfile -t kospi-watcher-web apps/web
# NOTE: image builds are NOT verified in this phase (no Docker available locally).
FROM node:22-slim AS deps
WORKDIR /app
COPY package.json ./
RUN npm install --no-audit --no-fund

FROM node:22-slim AS build
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:22-slim AS run
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/.next ./.next
COPY --from=build /app/public ./public
COPY --from=build /app/package.json ./package.json
COPY --from=build /app/next.config.mjs ./next.config.mjs
RUN useradd --create-home --uid 10001 webuser && chown -R webuser /app
USER webuser
EXPOSE 3000
CMD ["npm", "run", "start"]
