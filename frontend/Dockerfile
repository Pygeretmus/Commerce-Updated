FROM node:24-slim AS builder

WORKDIR /app

COPY package.json package-lock.json ./

RUN npm ci --include=optional

COPY . .

RUN npm run build

FROM nginx:1.28-alpine

COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80
