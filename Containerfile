FROM docker.io/library/debian:12-slim as base

RUN apt-get update && \
    apt-get install -y --no-install-recommends wget ca-certificates python3-dev default-libmysqlclient-dev build-essential pkg-config

RUN useradd -m cla

WORKDIR /home/cla

USER cla

RUN wget -nv https://github.com/astral-sh/uv/releases/download/0.8.0/uv-x86_64-unknown-linux-gnu.tar.gz && \
    mkdir -p .local/bin/ && \
    tar -xzvf uv-x86_64-unknown-linux-gnu.tar.gz -C .local/bin/ --strip-components=1

COPY pyproject.toml uv.lock ./

ENV PATH="$PATH:/home/cla/.local/bin"

RUN uv sync --locked --no-dev

FROM docker.io/library/debian:12-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates python3 libmariadb3 && \
    apt-get clean

RUN useradd -m cla

WORKDIR /home/cla

USER cla

COPY --from=base /home/cla/.local/ ./.local/
COPY --from=base /home/cla/.venv/ ./.venv/
COPY base/ ./base/
COPY cla/ ./cla/
COPY pyproject.toml uv.lock manage.py cla-app.sh ./

ENV PATH="$PATH:/home/cla/.local/bin"

ENV DJANGO_DEBUG="false" \
    GUNICORN_CMD_ARGS="--bind=0.0.0.0:8080 --workers=2"

CMD ["./cla-app.sh", "migrate-and-run"]
