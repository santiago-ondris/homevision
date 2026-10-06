FROM node:24-slim AS build
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
COPY samples/ /samples/
ARG VITE_API_URL=http://localhost:8080
ENV VITE_API_URL=${VITE_API_URL}
RUN npm run build

FROM nginx:alpine
COPY web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /web/dist /usr/share/nginx/html
EXPOSE 80
