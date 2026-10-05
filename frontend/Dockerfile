# ============================================================
# STAGE 1: Build - Compilação da aplicação React
# ============================================================
FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

# ============================================================
# STAGE 2: Production - Servindo com Nginx
# ============================================================
FROM nginx:stable-alpine AS production

RUN addgroup -g 1001 appuser && \
    adduser -S -u 1001 -G appuser appuser

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

RUN chown -R appuser:appuser /usr/share/nginx/html && \
    chown -R appuser:appuser /var/cache/nginx && \
    chown -R appuser:appuser /etc/nginx/conf.d && \
    touch /var/run/nginx.pid && \
    chown -R appuser:appuser /var/run/nginx.pid

USER appuser

EXPOSE 5173

CMD ["nginx", "-g", "daemon off;"]
