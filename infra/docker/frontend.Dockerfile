# Dcode Frontend production image.
#
# Build context: the repository ROOT, like every other image here. It used to
# be `apps/frontend`, which worked for compose and made this the only image
# whose context differed — awkward on a platform where the service's config
# file path does not follow its root directory.
FROM node:20-alpine AS build

WORKDIR /app

ARG VITE_API_BASE_URL=
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

COPY apps/frontend/package.json apps/frontend/package-lock.json* ./
RUN npm ci --no-audit --no-fund

COPY apps/frontend/ ./
RUN npm run build

FROM nginx:1.27-alpine

# The site config is a template. The nginx image's entrypoint runs envsubst
# over /etc/nginx/templates/*.template into /etc/nginx/conf.d/ at boot.
#
# NGINX_ENVSUBST_FILTER is not optional: without it envsubst would also
# substitute nginx's own $host, $remote_addr, $request_uri and $uri, producing
# a config that is valid, empty in the places that matter, and broken in a way
# that reads like a proxy bug.
COPY apps/frontend/nginx.conf.template /etc/nginx/templates/default.conf.template
ENV NGINX_ENVSUBST_FILTER="^(PORT|API_UPSTREAM|DNS_RESOLVER)$"

# Defaults reproduce the compose behaviour, so the developer stack and
# docker-compose.prod.yml need no change. Railway overrides PORT (it injects
# one), API_UPSTREAM (http://<service>.railway.internal:8000) and DNS_RESOLVER
# (its internal resolver) — see Deploy.md R-4.
ENV PORT=80
ENV API_UPSTREAM=http://api:8000
ENV DNS_RESOLVER=127.0.0.11

COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
