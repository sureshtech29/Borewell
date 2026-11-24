# Build the web app, then serve the static files with nginx (non-root, port 8080).
#   docker build -t bwf-web --build-arg VITE_TILE_STREET_URL=... frontend/
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
# Reproducible if a lock file is committed (recommended: run `npm install` once and commit package-lock.json).
RUN if [ -f package-lock.json ]; then npm ci --no-audit --no-fund; else npm install --no-audit --no-fund; fi
COPY . .
# Vite bakes these into the bundle at build time (see .env.example for the provider-terms warning).
ARG VITE_API_BASE=/api
ARG VITE_TILE_STREET_URL
ARG VITE_TILE_STREET_ATTRIBUTION
ARG VITE_TILE_SATELLITE_URL
ARG VITE_TILE_SATELLITE_ATTRIBUTION
ENV VITE_API_BASE=$VITE_API_BASE \
    VITE_TILE_STREET_URL=$VITE_TILE_STREET_URL \
    VITE_TILE_STREET_ATTRIBUTION=$VITE_TILE_STREET_ATTRIBUTION \
    VITE_TILE_SATELLITE_URL=$VITE_TILE_SATELLITE_URL \
    VITE_TILE_SATELLITE_ATTRIBUTION=$VITE_TILE_SATELLITE_ATTRIBUTION
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.27-alpine
# The image's entrypoint runs envsubst on /etc/nginx/templates/*.template -> /etc/nginx/conf.d/
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
ENV API_UPSTREAM=api:8000
EXPOSE 8080
