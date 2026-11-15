# Foundation infrastructure

The root `docker-compose.yml` owns the four local development services. PostgreSQL and Redis use named persistent volumes; Redis enables AOF and no-eviction. Host ports bind only to loopback. Nginx in the frontend image serves the compiled SPA and forwards `/api/*` to the backend, so browsers use one origin. Nginx is an ancillary static server/proxy, not an additional application framework.

This is local infrastructure, without TLS, Redis authentication or high availability. Do not expose it publicly. Workers, Prometheus and Grafana belong to later phases. Do not use `docker compose down -v` unless intentionally destroying local data.
