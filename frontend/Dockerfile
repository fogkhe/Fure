# syntax=docker/dockerfile:1
FROM node:26-bookworm-slim AS build

WORKDIR /app

COPY package.json package-lock.json ./
# Nuxt prepares generated files during build, after sources are copied.
RUN --mount=type=cache,target=/root/.npm npm ci --ignore-scripts

COPY . .
ENV NUXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:26-bookworm-slim AS runtime

WORKDIR /app

ENV NODE_ENV=production
ENV HOST=0.0.0.0
ENV PORT=3000

COPY --from=build --chown=node:node /app/.output ./.output

USER node

EXPOSE 3000
CMD ["node", ".output/server/index.mjs"]
