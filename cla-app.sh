#!/bin/bash

set -ex


pytest() {
    uv run --no-dev --locked python -m pytest "$@"
}


manage.py() {
    uv run --no-dev --locked python manage.py "$@"
}


run() {
    exec uv run --no-dev --locked python -m gunicorn base.wsgi:application
}


migrate-and-run() {
    manage.py migrate
    run
}


"$@"
