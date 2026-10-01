# Build the static dashboard, then serve it with nginx.
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
# The API URL is baked in at build time (it is public; never put secrets in VITE_ variables).
ARG VITE_API_BASE_URL=http://localhost:8000/api/v1
ARG VITE_POLL_INTERVAL_MS=5000
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL VITE_POLL_INTERVAL_MS=$VITE_POLL_INTERVAL_MS
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
