# Frontend (Next.js) for Azure Container Apps.
# NEXT_PUBLIC_API_URL is baked in at build time: a new backend URL needs a new image.
FROM node:22-alpine
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
RUN test -n "$NEXT_PUBLIC_API_URL" || (echo "Set --build-arg NEXT_PUBLIC_API_URL" && exit 1)
RUN npm run build

ENV NODE_ENV=production PORT=3000 HOSTNAME=0.0.0.0
RUN chown -R node:node /app
USER node
EXPOSE 3000
CMD ["npx", "next", "start", "-p", "3000", "-H", "0.0.0.0"]
