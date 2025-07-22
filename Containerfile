FROM docker.io/library/debian:12-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends wget ca-certificates && \
    apt-get clean all

RUN useradd -m cla

WORKDIR /home/cla

USER cla

RUN wget -nv https://github.com/astral-sh/uv/releases/download/0.8.0/uv-x86_64-unknown-linux-gnu.tar.gz && \
    mkdir -p .local/bin/ && \
    tar -xzvf uv-x86_64-unknown-linux-gnu.tar.gz -C .local/bin/ --strip-components=1 && \
    rm uv-x86_64-unknown-linux-gnu.tar.gz .wget-hsts

ENV PATH="$PATH:/home/cla/.local/bin"

COPY base/ ./base/
COPY cla/ ./cla/
COPY pyproject.toml uv.lock manage.py ./

RUN uv sync --locked --no-dev

CMD ["uv", "run", "--no-dev", "--locked", "python", "-m", "gunicorn", "--workers=2", "--bind", "0.0.0.0:8080", "base.wsgi:application"]
