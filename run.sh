#!/bin/sh

set -ex

./manage.py migrate
exec uv run --no-dev --locked python -m gunicorn base.wsgi:application
