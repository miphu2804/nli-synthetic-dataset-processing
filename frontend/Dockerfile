FROM node:20-alpine AS build

WORKDIR /app

# VITE_* vars are baked in at build time (the bundle runs in the browser).
ARG VITE_API_ENDPOINT=http://localhost:8000
ENV VITE_API_ENDPOINT=$VITE_API_ENDPOINT

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM node:20-alpine

WORKDIR /app
COPY --from=build /app/dist ./dist
RUN npm install -g serve

EXPOSE 3000
CMD ["serve", "-s", "dist", "-l", "3000"]
