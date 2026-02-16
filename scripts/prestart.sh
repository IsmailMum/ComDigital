#! /usr/bin/env bash

set -ex

alembic upgrade head

python -m app.initial_data

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
