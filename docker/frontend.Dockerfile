# ===================================================
# Stage 1: Build React Assets
# ===================================================
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package configurations first to leverage Docker build cache
COPY frontend/package*.json ./

# Install dependencies
RUN npm ci

# Copy the rest of the application files
COPY frontend/ ./

# Build the production bundles
RUN npm run build

# ===================================================
# Stage 2: Serve via Nginx
# ===================================================
FROM nginx:1.25-alpine

# Copy the custom Nginx server configuration
COPY docker/nginx.conf /etc/nginx/nginx.conf

# Copy the static build directory from stage 1
COPY --from=builder /app/dist /usr/share/nginx/html

# Expose HTTP port
EXPOSE 80

# Run Nginx in the foreground
CMD ["nginx", "-g", "daemon off;"]
