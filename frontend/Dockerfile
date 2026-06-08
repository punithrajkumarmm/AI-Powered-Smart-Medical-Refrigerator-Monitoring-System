FROM node:18-alpine AS build

WORKDIR /app

COPY frontend/package*.json ./
RUN npm install

COPY frontend ./

ARG REACT_APP_API_BASE=http://backend:8000
ENV REACT_APP_API_BASE=${REACT_APP_API_BASE}

RUN npm run build

FROM nginx:stable-alpine
COPY --from=build /app/build /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
