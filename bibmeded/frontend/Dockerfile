# ---- deps: install dependencies once, reused by the build stage and (in
#      dev, via docker-compose.override.yml) mounted straight into a
#      `next dev` container -----------------------------------------------
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# ---- builder: production build ---------------------------------------
FROM node:20-alpine AS builder
WORKDIR /app
# Copy source first, then overlay the clean `deps` node_modules on top. This
# ordering is deliberate: it guarantees the image never ships a
# host-copied node_modules (e.g. macOS/Windows native binaries picked up by
# a stray local `npm install`) even if one happens to be sitting in the
# build context, without needing a .dockerignore entry.
COPY . .
COPY --from=deps /app/node_modules ./node_modules
RUN npm run build

# ---- runner: production runtime ----------------------------------------
# next.config.ts does not opt into `output: "standalone"`, so this runs the
# ordinary `next start` server rather than the standalone server.js.
FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
RUN addgroup --system --gid 1001 nodejs \
    && adduser --system --uid 1001 nextjs
COPY --from=deps /app/node_modules ./node_modules
COPY --from=builder /app/package.json /app/package-lock.json ./
COPY --from=builder /app/next.config.ts ./next.config.ts
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next ./.next
RUN chown -R nextjs:nodejs /app

USER nextjs
EXPOSE 3000
ENV PORT=3000
CMD ["npm", "run", "start"]
