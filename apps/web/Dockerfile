FROM node:20-alpine

WORKDIR /app

# Pin pnpm to the version that generated pnpm-lock.yaml. `pnpm@latest` now
# resolves to pnpm 11, which needs a newer Node than this image ships and
# crashes with ERR_UNKNOWN_BUILTIN_MODULE.
ARG PNPM_VERSION=9.15.9
RUN corepack enable && corepack prepare pnpm@${PNPM_VERSION} --activate

# Copy package files
COPY package.json pnpm-lock.yaml ./

# Install dependencies
RUN pnpm install --frozen-lockfile

# Copy application code
COPY . .

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:3000 || exit 1

# Development mode with hot reload
CMD ["pnpm", "dev"]
