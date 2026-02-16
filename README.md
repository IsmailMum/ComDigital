# ComDigital

A RESTful API built with **FastAPI**, **SQLModel**, **PostgreSQL**, and **Redis**, featuring JWT authentication, role-based access control, caching, and structured logging with database persistence.

---

## Table of Contents

- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Environment Variables](#environment-variables)
  - [Run with Docker Compose](#run-with-docker-compose)
  - [Run Locally (without Docker)](#run-locally-without-docker)
- [API Documentation](#api-documentation)
- [Running Tests](#running-tests)
- [Logging](#logging)
- [Database Migrations](#database-migrations)

---

## Tech Stack

| Component       | Technology                          |
|-----------------|-------------------------------------|
| Framework       | FastAPI 0.129                       |
| ORM             | SQLModel 0.33 / SQLAlchemy 2.0      |
| Database        | PostgreSQL 17                       |
| Cache           | Redis 7                             |
| Auth            | JWT (PyJWT) + OAuth2 password flow  |
| Migrations      | Alembic                             |
| Password Hashing| pwdlib (bcrypt)                     |
| Runtime         | Python 3.14, Uvicorn                |

---

## Project Structure

```
ComDigital/
├── app/
│   ├── alembic/               # Alembic migration environment & versions
│   ├── api/
│   │   ├── dependencies.py    # FastAPI dependency injection (DB session, auth)
│   │   ├── main.py            # API router aggregation
│   │   └── routes/
│   │       ├── items.py       # Item CRUD endpoints
│   │       └── users.py       # User registration, login, profile endpoints
│   ├── core/
│   │   ├── cache.py           # Redis cache helpers
│   │   ├── config.py          # Pydantic settings (env-based configuration)
│   │   ├── db.py              # Async SQLAlchemy engine & session factory
│   │   ├── exception_handlers.py  # Global exception handlers
│   │   ├── exceptions.py      # Custom application exceptions
│   │   ├── logging.py         # Centralised logging setup & DB handler
│   │   ├── middleware.py       # Request/response logging middleware
│   │   └── security.py        # Password hashing & JWT token creation
│   ├── crud.py                # Database CRUD operations
│   ├── initial_data.py        # Superuser bootstrap script
│   ├── main.py                # FastAPI application entry point
│   ├── models.py              # SQLModel table & schema definitions
│   └── utils.py               # Utility functions (e.g. category density)
├── tests/
│   ├── conftest.py            # Shared test fixtures
│   ├── unit/                  # Unit tests (mocked DB)
│   └── integration/           # Integration tests (in-memory SQLite)
├── scripts/
│   └── prestart.sh            # Runs migrations + seeds before starting the server
├── compose.yml                # Docker Compose services (PostgreSQL, Redis, backend)
├── Dockerfile                 # Multi-stage Docker build
├── alembic.ini                # Alembic configuration
└── requirements.txt           # Python dependencies
```

---

## Getting Started

### Prerequisites

- **Docker & Docker Compose** (recommended), or
- **Python 3.14+**, a running **PostgreSQL 17** instance, and a running **Redis 7** instance

### Environment Variables

Create a `.env` file in the project root. All variables below are **required** unless a default is noted:

```env
# ── Application ──────────────────────────────────────
PROJECT_NAME=ComDigital                    # default: ComDigital
SECRET_KEY=your-secret-key-here            # default: random token
ACCESS_TOKEN_EXPIRE_MINUTES=60             # default: 60

# ── First superuser (created on startup) ─────────────
FIRST_SUPERUSER=admin@example.com
FIRST_SUPERUSER_PASSWORD=changethis

# ── PostgreSQL ───────────────────────────────────────
POSTGRES_SERVER=localhost
POSTGRES_PORT=5432
POSTGRES_USER=comdigital
POSTGRES_PASSWORD=changethis
POSTGRES_DB=comdigital

# ── Redis ────────────────────────────────────────────
REDIS_HOST=localhost                       # default: localhost
REDIS_PORT=6379                            # default: 6379
REDIS_PASSWORD=                            # default: empty
REDIS_CACHE_TTL=300                        # default: 300 (seconds)

# ── Logging ──────────────────────────────────────────
LOG_LEVEL=INFO                             # default: INFO  (DEBUG, INFO, WARNING, ERROR, CRITICAL)
LOG_FORMAT=console                         # default: console  ("console" for dev, "json" for production)
```

### Run with Docker Compose

This is the easiest way — it starts PostgreSQL, Redis, and the backend in one command:

```bash
# 1. Clone the repository and cd into it
git clone <repo-url> && cd ComDigital

# 2. Create your .env file (see section above)
cp .env.example .env   # or create manually

# 3. Build and start all services
docker compose up --build -d

# The API is available at http://localhost:8000
```

To stop the services:

```bash
docker compose down
```

### Run Locally (without Docker)

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Linux / macOS
# .venv\Scripts\activate         # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Make sure PostgreSQL and Redis are running, then create your .env file

# 4. Run database migrations
alembic upgrade head

# 5. Seed the initial superuser
python -m app.initial_data

# 6. Start the development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## API Documentation

Once the server is running, interactive API docs are available at:

| Format   | URL                                                  |
|----------|------------------------------------------------------|
| Swagger  | [http://localhost:8000/api/v1/openapi.json](http://localhost:8000/api/v1/openapi.json) (OpenAPI spec) |
| Swagger UI | [http://localhost:8000/docs](http://localhost:8000/docs)  |
| ReDoc    | [http://localhost:8000/redoc](http://localhost:8000/redoc) |

### Key Endpoints

| Method   | Path                                  | Description                   | Auth Required |
|----------|---------------------------------------|-------------------------------|:------------:|
| `POST`   | `/api/v1/users/register`              | Register a new user           | No           |
| `POST`   | `/api/v1/users/login`                 | Log in (get JWT token)        | No           |
| `GET`    | `/api/v1/users/profile`               | Get current user profile      | Yes          |
| `PATCH`  | `/api/v1/users/profile`               | Update current user profile   | Yes          |
| `POST`   | `/api/v1/items/`                      | Create an item                | Yes          |
| `GET`    | `/api/v1/items/`                      | List items (with filters)     | Yes          |
| `GET`    | `/api/v1/items/{id}`                  | Get item by ID                | Yes          |
| `PUT`    | `/api/v1/items/{id}`                  | Update an item                | Yes          |
| `DELETE` | `/api/v1/items/{id}`                  | Delete an item                | Yes          |
| `GET`    | `/api/v1/items/analytics/category-density` | Category density analytics | Yes          |

---

## Running Tests

The test suite is split into **unit tests** (fully mocked, no external services) and **integration tests** (in-memory SQLite).

```bash
# Activate the virtual environment first
source .venv/bin/activate

# Run all tests
pytest

# Run only unit tests
pytest tests/unit/

# Run only integration tests
pytest tests/integration/

# Run with verbose output
pytest -v

# Run with coverage report
pytest --cov=app --cov-report=term-missing

# Run with HTML coverage report
pytest --cov=app --cov-report=html
# Open htmlcov/index.html in your browser
```

> **Note:** Tests do not require PostgreSQL or Redis — unit tests use mocks, and integration tests use an in-memory SQLite database.

---

## Logging

The application uses a centralised logging system configured via environment variables:

- **`LOG_LEVEL`** — Controls verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` (default: `INFO`)
- **`LOG_FORMAT`** — Output format: `console` (coloured, human-readable) or `json` (structured, for log aggregation tools) (default: `console`)

### What Gets Logged

| Layer           | Events                                                               |
|-----------------|----------------------------------------------------------------------|
| **Middleware**   | Every HTTP request/response with method, path, status code, duration |
| **Auth**         | Token validation failures, inactive user access attempts             |
| **Routes**       | User registration, login attempts (success/failure), CRUD operations |
| **CRUD**         | Database reads, writes, updates, and deletes                         |
| **Cache**        | Redis connection lifecycle, cache hits/misses, errors                |
| **Exceptions**   | Unhandled exceptions (with full tracebacks)                          |

### Database Persistence

All log entries are also persisted to the `log_entry` table in PostgreSQL via an async background handler. This includes request metadata (method, path, status code, duration, client IP, request ID) when available.

### Request Tracing

Every response includes an `X-Request-ID` header for correlating logs with specific requests.

---

## Database Migrations

Migrations are managed by [Alembic](https://alembic.sqlalchemy.org/):

```bash
# Apply all pending migrations
alembic upgrade head

# Create a new migration after model changes
alembic revision --autogenerate -m "description of changes"

# Downgrade one revision
alembic downgrade -1
```

When running via Docker Compose, migrations are automatically applied on container startup via `scripts/prestart.sh`.
