# Stage 1: build frontend + Express bundle
FROM node:20-slim AS builder
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

# Stage 2: production runner — Python 3.12 + Node 20
FROM python:3.12-slim AS runner
WORKDIR /app

# Install Node.js 20 from NodeSource
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY python/requirements.txt ./python/requirements.txt
RUN pip install --no-cache-dir -r python/requirements.txt

# Install Node production dependencies
COPY package.json package-lock.json ./
RUN npm ci --omit=dev

# Copy Express + frontend build artifacts
COPY --from=builder /app/dist ./dist

# Copy Python source (FastAPI app runs from source at runtime)
COPY python/ ./python/

# Copy prod start script
COPY scripts/start-prod.sh ./scripts/start-prod.sh
RUN chmod +x scripts/start-prod.sh

RUN mkdir -p uploads

ENV NODE_ENV=production
ENV PORT=5000
EXPOSE 5000

CMD ["bash", "scripts/start-prod.sh"]
