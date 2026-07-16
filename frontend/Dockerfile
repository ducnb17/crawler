# ===== Frontend Dockerfile — build SPA + serve via nginx =====

# Stage 1: build Vue SPA
FROM node:20-slim AS builder
WORKDIR /app

# Enable pnpm via corepack
RUN corepack enable && corepack prepare pnpm@9.12.0 --activate

# Install deps (cache)
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

# Build with production API base (default: same-origin /)
COPY . .
ARG VITE_API_BASE_URL=/
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
RUN pnpm build

# Stage 2: serve static dist with nginx
FROM nginx:1.27-alpine AS runtime
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]