FROM nginx:1.27-alpine

# Copy all frontend files into the image at build time.
# This eliminates the hostPath bind-mount and the stale-inode 403 bug that
# came with it. After this, deploys are: build → import → rollout restart.
COPY . /usr/share/nginx/html

EXPOSE 80
