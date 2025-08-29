#!/bin/sh

set -ex

uv run --locked python -m pytest "$@"
