FROM python:3.12-slim AS backend

WORKDIR /app

# Install system deps for scipy/scikit-learn
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --no-cache-dir -e ".[dev]" || pip install --no-cache-dir .

COPY . .

# Run migrations on startup, then start API
EXPOSE 8010
CMD ["sh", "-c", "python -c 'from packages.shared.db.migrate import run_upgrade; run_upgrade()' && uvicorn apps.api.main:app --host 0.0.0.0 --port 8010"]


FROM node:20-slim AS frontend-build

WORKDIR /app/apps/web/frontend
COPY apps/web/frontend/package*.json ./
RUN npm ci
COPY apps/web/frontend/ ./
RUN npm run build


FROM nginx:alpine AS frontend

COPY --from=frontend-build /app/apps/web/frontend/dist /usr/share/nginx/html
COPY ops/docker/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 8510
