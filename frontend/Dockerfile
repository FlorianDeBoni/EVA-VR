# ---------- 1️⃣ Build stage ----------
FROM node:20 AS build

WORKDIR /app

# Loading environment variables
ARG VITE_FRONTEND_PORT
ARG VITE_BACKEND_PORT
ARG VITE_BACKEND_URL
ARG VITE_BASE_URL

ENV VITE_FRONTEND_PORT=$VITE_FRONTEND_PORT
ENV VITE_BACKEND_PORT=$VITE_BACKEND_PORT
ENV VITE_BACKEND_URL=$VITE_BACKEND_URL
ENV VITE_BASE_URL=$VITE_BASE_URL

# Copy and install dependencies
COPY package*.json ./
RUN npm ci

# Copy all source files
COPY . .

# Build the static files
RUN npm run build

# ---------- 2️⃣ Runtime stage ----------
FROM nginx:alpine AS production

# Copy the built app to nginx html folder
COPY --from=build /app/dist /usr/share/nginx/html

# Replace default Nginx config (optional, to tweak ports etc.)
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

# Expose port (default 80)
EXPOSE 80

# Start Nginx
CMD ["nginx", "-g", "daemon off;"]
