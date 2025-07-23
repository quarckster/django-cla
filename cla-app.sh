#!/bin/sh

set -ex


pytest() {
    uv run python -m pytest "$@"
}


manage.py() {
    uv run python manage.py "$@"
}


run() {
    exec uv run --no-dev --locked python -m gunicorn base.wsgi:application
}


migrate-and-run() {
    manage.py migrate
    run
}


"$@"
