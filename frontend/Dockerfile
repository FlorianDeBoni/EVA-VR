# Production image: build the static app, serve it with nginx on port 80.
# Build context: frontend/. Public path and API URL are baked in at build time.
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ARG VITE_BASE_PATH=/eva-vr/
ARG VITE_API_URL=/eva-vr/api
ARG VITE_HEALTH_POLL_MS=5000
ARG VITE_STT_MIN_MS=500
ARG VITE_STT_MIN_LEVEL=0.01
ENV VITE_BASE_PATH=$VITE_BASE_PATH VITE_API_URL=$VITE_API_URL \
    VITE_HEALTH_POLL_MS=$VITE_HEALTH_POLL_MS VITE_STT_MIN_MS=$VITE_STT_MIN_MS \
    VITE_STT_MIN_LEVEL=$VITE_STT_MIN_LEVEL
# FRONTEND_PORT is only read by the dev server but vite.config.js needs it defined.
RUN FRONTEND_PORT=80 npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
