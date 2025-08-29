#!/bin/bash

set -ex


pytest() {
    uv run --locked python -m pytest "$@"
}


run() {
    exec uv run --no-dev --locked python -m gunicorn base.wsgi:application
}


migrate-and-run() {
    ./manage.py migrate
    run
}


"$@"
