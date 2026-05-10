# Stage 1: Build the Excalidraw draw app (Vite + React)
FROM node:20-alpine AS draw-builder
WORKDIR /app
COPY draw-app/package.json draw-app/package-lock.json ./
RUN npm ci
COPY draw-app/ ./
RUN npm run build

# Stage 2: Serve everything with nginx
FROM nginx:1.27-alpine

# Copy all frontend files into the image at build time.
# This eliminates the hostPath bind-mount and the stale-inode 403 bug that
# came with it. After this, deploys are: build → import → rollout restart.
COPY . /usr/share/nginx/html

# Overwrite /draw with the Vite build output (replaces the source files)
COPY --from=draw-builder /draw/ /usr/share/nginx/html/draw/

# Remove draw-app source from the final image (only the built output is needed)
RUN rm -rf /usr/share/nginx/html/draw-app

EXPOSE 80
