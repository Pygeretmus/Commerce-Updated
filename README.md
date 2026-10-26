# Commerce

A timed-auction site: a **Django REST** API with a **React** single-page client and live prices over **WebSockets**. Sellers list lots with photographs, buyers bid, the price moves on every open screen at once, and a scheduler closes each lot on the clock.

It is a ground-up rewrite of an earlier, simpler version, with a real data model, a service layer, concurrency-safe bidding, a consistent API contract, a full test suite and a one-command Docker setup.

## Tech stack

| Layer    | Technology                                                                    |
| -------- | ----------------------------------------------------------------------------- |
| API      | Python 3.13, Django 6, Django REST Framework, SimpleJWT, drf-spectacular      |
| Realtime | Django Channels, Redis channel layer, uvicorn (ASGI)                          |
| Data     | PostgreSQL 17 (full-text search with a GIN index)                             |
| Async    | Celery (worker + beat) with Redis; Redis also backs the cache and rate limits |
| Client   | React 19, TypeScript, Vite (no UI or state libraries)                         |
| Delivery | Docker Compose, nginx reverse proxy                                           |
| Quality  | Django test runner, Ruff, ESLint, GitHub Actions                              |

## Quick start

Requires Docker with Compose.

```bash
cp .env.example .env
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env

docker compose up --build
```

Then open **<http://127.0.0.1>**. The default configuration is set up for exactly that address.

| URL                                       | What                           |
| ----------------------------------------- | ------------------------------ |
| <http://127.0.0.1>                        | The app                        |
| <http://127.0.0.1/api/schema/swagger-ui/> | Interactive API docs (Swagger) |
| <http://127.0.0.1/api/admin/>             | Django admin                   |

A superuser is created on startup from `DJANGO_SUPERUSER_EMAIL` / `DJANGO_SUPERUSER_PASSWORD`. **Change every secret in the `.env` files before exposing the stack anywhere.**

### Services

```mermaid
flowchart LR
    user([Browser]) --> nginx
    nginx -- "/" --> frontend["frontend<br/>static files"]
    nginx -- "/api, /static" --> backend["backend<br/>gunicorn"]

    backend --> postgres[(postgres)]
    backend --> redis[(redis)]
    worker["worker<br/>celery worker"] --> postgres
    worker --> redis
    beat["beat<br/>celery beat"] --> redis

    migrate["migrate<br/>one-off job"] -.->|"schema first"| postgres
```

`backend`, `worker` and `beat` start only after `migrate` has finished. `redis` is the Celery broker and also serves the cache and rate limits.

### Configuration

| Variable                                                 | Purpose                                                    |
| -------------------------------------------------------- | ---------------------------------------------------------- |
| `SECRET_KEY`                                             | Django secret key                                          |
| `DEBUG`                                                  | Defaults to `False`                                        |
| `ALLOWED_HOSTS`                                          | Comma-separated hosts                                      |
| `CSRF_TRUSTED_ORIGINS`, `CORS_ALLOWED_ORIGINS`           | Origins allowed to call the API (add your dev origin here) |
| `DATABASE_URL`                                           | e.g. `postgresql://user:pass@db:5432/postgres`             |
| `REDIS_URL`                                              | Celery broker and cache                                    |
| `DJANGO_SUPERUSER_USERNAME`, `..._EMAIL`, `..._PASSWORD` | Initial admin account                                      |
| `POSTGRES_PASSWORD`                                      | Read by Compose for the database container                 |
| `VITE_API_URL`                                           | API base URL baked into the client at build time           |

## API overview

Base path `/api`. All endpoints except registration and login need `Authorization: Bearer <access token>`. Full schemas are in Swagger.

| Method                 | Path                            | Description                                                  |
| ---------------------- | ------------------------------- | ------------------------------------------------------------ |
| `POST`                 | `/token/`, `/token/refresh/`    | Sign in, refresh the access token                            |
| `POST`                 | `/accounts/`                    | Register                                                     |
| `GET` `PUT` `PATCH`    | `/accounts/me/`                 | Read or update the profile (updates need `current_password`) |
| `PUT`                  | `/accounts/password/`           | Change password                                              |
| `POST`                 | `/accounts/destroy/`            | Delete the account (needs `current_password`)                |
| `GET`                  | `/categories/`                  | Categories                                                   |
| `GET` `POST`           | `/listings/`                    | Catalogue (filters, search, ordering), create draft          |
| `GET` `PATCH` `DELETE` | `/listings/{id}/`               | Lot detail; edit or delete a draft                           |
| `POST`                 | `/listings/{id}/images/`        | Add image to the draft                                       |
| `PUT`                  | `/listings/{id}/images/order/`  | Change images order                                          |
| `DELETE`               | `/listings/{id}/images/{id}/`   | Remove image                                                 |
| `POST`                 | `/listings/{id}/publish/`       | Publish draft                                                |
| `POST`                 | `/listings/{id}/cancel/`        | Cancel active listing                                        |
| `POST`                 | `/listings/{id}/end_now/`       | End active listing now                                       |
| `GET` `POST`           | `/listings/{id}/bids/`          | Bid history (masked); place a bid                            |
| `GET` `POST`           | `/listings/{id}/comments/`      | Ask question, read answer                                    |
| `DELETE`               | `/listings/{id}/comments/{id}/` | Delete comment                                               |
| `PUT` `DELETE`         | `/listings/{id}/watch/`         | Add/remove listing to/from watchlist                         |
| `GET`                  | `/me/bids/`                     | Bids personal dashboard                                      |
| `GET`                  | `/me/listings/`                 | Listings personal dashboard                                  |
| `GET`                  | `/me/summary/`                  | Counters for navigation                                      |

## Development

### Backend

```bash
cd backend
uv sync
# needs PostgreSQL and Redis; point DATABASE_URL and REDIS_URL at them in backend/.env
uv run manage.py migrate
uv run manage.py runserver
```

### Tests

```bash
cd backend
DATABASE_URL=postgres://user:pass@localhost:5432/postgres \
  uv run manage.py test --settings=configuration.settings.test
```

```bash
uv run ruff check . && uv run ruff format --check .   # lint
```

### Frontend

```bash
cd frontend
npm ci
npm run dev        # http://localhost:5173
npm run lint
npm run build
```

When running the dev server, set `VITE_API_URL` to your API and add `http://localhost:5173` to `CORS_ALLOWED_ORIGINS`.

### Continuous integration

GitHub Actions runs the backend tests, a check for missing migrations, a forward → backward → forward migration test, Ruff, and the frontend ESLint and production build.
