#! /usr/bin/env bash

set -ex

python -m app.pre_start

alembic upgrade head

python -m app.initial_data
