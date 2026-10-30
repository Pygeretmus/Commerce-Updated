# Commerce

A timed-auction site: a **Django REST** API with a **React** single-page client and live prices over **WebSockets**. Sellers list lots with photographs, buyers bid, the price moves on every open screen at once, and a scheduler closes each lot on the clock.

It is a ground-up rewrite of an earlier, simpler version, with a real data model, a service layer, concurrency-safe bidding, a consistent API contract, a full test suite and a one-command Docker setup.

## Features

- **Lots.** Draft → publish → active → closed. Up to several photographs per lot (thumbnails made on upload, reorderable), a category, a starting price and an optional hidden reserve.
- **Bidding.** Tiered minimum increments, proxy-free "highest bid wins", a reserve that is revealed only as "met / not met". Bids are race-safe (see [Concurrency](#concurrency)).
- **Anti-sniping.** A bid in the last two minutes extends the auction by two minutes.
- **Live updates.** Every open lot page gets price, bid count and leader pushed over a WebSocket; a countdown follows the server clock, not the browser's.
- **Closing.** A Celery beat task closes expired lots (idempotent). A seller can _end now_ (only with bids) or _cancel_ (only without bids).
- **Notifications.** Outbid, won, sold, lost, ending soon, new question, lot ended, lot cancelled. Stored in the database, pushed live, with an unread counter and toasts.
- **Q&A.** Public comments on a lot; the seller's answers are marked.
- **Watchlist**, **My bids** (winning / outbid / won / lost), **My lots** (drafts, active, closed).
- **Search and filters.** Full-text search (PostgreSQL), category, status, price range, seller, watched, "my bids" and five orderings.
- **Privacy.** Bidders are shown masked (`a***e`); you see your own name; deleted accounts show nothing.
- **Accounts.** Register, sign in (JWT with refresh), edit profile, change password, delete account (blocked while you lead an auction or have bids on it).
- **Ops-friendly.** Rate limiting, OpenAPI docs, Django admin, CI, a demo-data command and a concurrency experiment.

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

Fill it with a demo catalogue (24 lots, bids, comments, watches, generated photographs; users `alice`, `bob`, ... with password `demo-pass-123`):

```bash
docker compose exec backend python manage.py seed_demo          # add
docker compose exec backend python manage.py seed_demo --reset  # wipe the demo data and rebuild
```

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
    nginx -- "/api, /ws" --> backend["backend<br/>uvicorn (HTTP + WebSocket)"]
    nginx -- "/static, /media" --> files[("static and<br/>media volumes")]

    backend --> postgres[(postgres)]
    backend --> redis[(redis)]
    backend --> files
    worker["worker<br/>celery worker"] --> postgres
    worker --> redis
    worker --> files
    beat["beat<br/>celery beat"] --> redis

    migrate["migrate<br/>one-off job"] -.->|"schema first"| postgres
```

`backend`, `worker` and `beat` start only after `migrate` has finished. `redis` is the Celery broker, the Channels layer (live updates between processes), the cache and the rate-limit store.

### Configuration

| Variable                                                 | Purpose                                                    |
| -------------------------------------------------------- | ---------------------------------------------------------- |
| `SECRET_KEY`                                             | Django secret key                                          |
| `DEBUG`                                                  | Defaults to `False`                                        |
| `ALLOWED_HOSTS`                                          | Comma-separated hosts                                      |
| `CSRF_TRUSTED_ORIGINS`, `CORS_ALLOWED_ORIGINS`           | Origins allowed to call the API (add your dev origin here) |
| `DATABASE_URL`                                           | e.g. `postgresql://user:pass@db:5432/postgres`             |
| `REDIS_URL`                                              | Celery broker, cache, throttling and the Channels layer    |
| `DJANGO_SUPERUSER_USERNAME`, `..._EMAIL`, `..._PASSWORD` | Initial admin account                                      |
| `POSTGRES_PASSWORD`                                      | Read by Compose for the database container                 |
| `VITE_API_URL`                                           | API base URL baked into the client at build time           |

## Architecture

### Data model

A lot is the only mutable thing; everything people did to it is an immutable row or a small per-person row.

```mermaid
erDiagram
    User |o--o{ Listing : "sells"
    Category ||--o{ Listing : "groups"
    Listing ||--o{ ListingImage : "has photos"
    Listing ||--o{ Bid : "receives"
    User |o--o{ Bid : "places"
    Listing }o--o| Bid : "top bid"
    Listing ||--o{ Comment : "has"
    User |o--o{ Comment : "writes"
    User ||--o{ Watch : "keeps"
    Listing ||--o{ Watch : "watched in"
    User ||--o{ Notification : "receives"
    Listing ||--o{ Notification : "is about"

    Listing {
        string status "draft, active, ended or cancelled"
        decimal current_price "denormalised from the top bid"
        int bids_count "denormalised"
        decimal reserve_price "secret, nullable"
        datetime ends_at "moves on a late bid"
        bool sold "null until the lot is closed"
    }
    Bid {
        decimal amount "unique per lot"
        datetime created_at
    }
    ListingImage {
        file image
        file thumbnail "filled in later by a task"
        int position "0 is the cover"
    }
    Comment {
        text body
        datetime deleted_at "null = visible"
    }
    Notification {
        string kind "outbid, won, sold, lost, ending_soon ..."
        json data "amount, author, ..."
        datetime read_at "null = unread"
    }
```

- **`Listing`** carries the live state of an auction (`current_price`, `bids_count`, `top_bid`) so lists can sort and filter by price without a join. These fields change only in `place_bid()`, under a row lock, and database constraints check that they agree with each other.
- **`Bid`** is an accepted bid and is never edited or deleted: the bids are the history, the lot is the summary. Two equal amounts on one lot can never both be stored.
- **Status flow:** a lot starts as a private `draft`, becomes `active` when published and ends as `ended` (the clock ran out, or the seller accepted the top bid) or `cancelled` (only while it has no bids). `sold` says whether somebody won; it is `null` until the lot is closed.
- **`Notification`** is one small row per person, written in the same transaction as the event that caused it, so a rolled-back bid leaves none behind. "Ending soon" is unique per person and lot, even if the task runs twice. The database stays the source of truth; a WebSocket push is only a hint that something new is waiting.
- **`Watch`** is a lot on somebody's watchlist, unique per user and lot.
- **`Comment`** is a flat question or answer; the seller's comments are the answers. Deleting one hides it (`deleted_at`) and keeps the row for moderation.
- **`ListingImage`** stores the original at once and the thumbnail later: a background task makes it, and until then the API serves the original.
  When an account is deleted, its drafts go with it, while finished lots, bids and comments stay in the record with the author shown as "Deleted user" (the links are set to null). Watches and notifications belong to the person and are removed. An account cannot be deleted while it has a live lot or holds the highest bid of a running auction.

## API overview

Base path `/api`. All endpoints except registration and login need `Authorization: Bearer <access token>`. Full schemas are in Swagger.

| Method                 | Path                           | Description                                                  |
| ---------------------- | ------------------------------ | ------------------------------------------------------------ |
| `POST`                 | `/token/`, `/token/refresh/`   | Sign in, refresh the access token                            |
| `POST`                 | `/accounts/`                   | Register                                                     |
| `GET` `PUT` `PATCH`    | `/accounts/me/`                | Read or update the profile (updates need `current_password`) |
| `PUT`                  | `/accounts/password/`          | Change password                                              |
| `POST`                 | `/accounts/destroy/`           | Delete the account (needs `current_password`)                |
| `GET`                  | `/categories/`                 | Categories                                                   |
| `GET` `POST`           | `/listings/`                   | Catalogue (filters, search, ordering), create draft          |
| `GET` `PATCH` `DELETE` | `/listings/{id}/`              | Lot detail; edit or delete a draft                           |
| `POST`                 | `/listings/{id}/images/`       | Add image to the draft                                       |
| `PUT`                  | `/listings/{id}/images/order/` | Change images order                                          |
| `DELETE`               | `/listings/{id}/images/{id}/`  | Remove image                                                 |
| `POST`                 | `/listings/{id}/publish/`      | Publish draft                                                |
| `POST`                 | `/listings/{id}/cancel/`       | Cancel active listing                                        |
| `POST`                 | `/listings/{id}/end_now/`      | End active listing now                                       |
| `GET` `POST`           | `/listings/{id}/bids/`         | Bid history (masked); place a bid                            |
| `GET` `POST`           | `/listings/{id}/comments/`     | Ask question, read answer                                    |
| `DELETE`               | `/comments/{id}/`              | Delete my comment                                            |
| `PUT` `DELETE`         | `/listings/{id}/watch/`        | Add/remove listing to/from watchlist                         |
| `GET`                  | `/me/bids/`                    | Bids personal dashboard                                      |
| `GET`                  | `/me/listings/`                | Listings personal dashboard                                  |
| `GET`                  | `/me/summary/`                 | Counters for navigation                                      |
| `GET`                  | `/notifications/`              | List of all notifications                                    |
| `GET`                  | `/notifications/unread_count/` | Unread notifications counter                                 |
| `POST`                 | `/notifications/read/`         | Mark chosen notifications as read                            |
| `WS`                   | `/ws/listings/{id}/`           | Live price and end events of a lot                           |
| `POST`                 | `/ws/ticket/`                  | One-use ticket for the user notifications WebSocket          |
| `WS`                   | `/ws/me/?ticket=`              | Live perconal notifications                                  |

## Development

### Backend

```bash
cd backend
uv sync
# needs PostgreSQL and Redis; point DATABASE_URL and REDIS_URL at them in backend/.env
uv run manage.py migrate
uv run daphne configuration.asgi:application   # HTTP and WebSocket on :8000 (runserver is WSGI only: no live updates)
uv run celery -A configuration worker -B -l INFO -Q images,commerce,notifications   # worker and scheduler in one
```

### Tests

```bash
cd backend
DATABASE_URL=postgres://user:pass@localhost:5432/postgres \
  uv run manage.py test --settings=configuration.settings.test
```

The suite has 440+ tests, one file per endpoint plus services and the cleanup task, written in an arrange/act/assert style. Test settings disable throttling and use a fast password hasher and an in-memory cache, so no Redis is needed.

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
