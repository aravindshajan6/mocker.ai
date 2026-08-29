# node_modules is installed on the host (npm ci) and vendored into the image: on this
# machine npm cannot reach the registry reliably from inside Docker builds. node:20-slim
# (glibc) matches the host's native binaries (@next/swc, lightningcss, tailwind oxide).
FROM node:20-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
COPY node_modules ./node_modules
COPY . .
# Rewrites are resolved at build time, so the backend URL must be known here.
ARG BACKEND_URL=http://backend:8000
ENV NEXT_TELEMETRY_DISABLED=1 BACKEND_URL=$BACKEND_URL
RUN npm run build

FROM node:20-slim AS run
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
COPY --from=build /app/public ./public
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
EXPOSE 3000
CMD ["node", "server.js"]
