FROM python:3.12-slim-trixie

ENV DEBIAN_FRONTEND=noninteractive PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    RUSTUP_HOME=/opt/rustup CARGO_HOME=/opt/cargo \
    PATH=/opt/cargo/bin:/usr/local/go/bin:$PATH

RUN apt-get update \
 && apt-get install -y --no-install-recommends gcc libc6-dev openjdk-21-jdk-headless curl ca-certificates xz-utils \
 && curl -fsSL https://nodejs.org/dist/v22.12.0/node-v22.12.0-linux-x64.tar.xz | tar -xJ -C /usr/local --strip-components=1 \
 && curl -fsSL https://go.dev/dl/go1.24.4.linux-amd64.tar.gz | tar -xz -C /usr/local \
 && curl -fsSL https://sh.rustup.rs | sh -s -- -y --profile minimal --default-toolchain stable --no-modify-path \
 && chmod -R a+rX /opt/rustup /opt/cargo \
 && apt-get purge -y curl xz-utils && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.txt backend/
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend backend
COPY samples samples

RUN useradd -m runner && mkdir backend/.cache && chown runner backend/.cache
USER runner
WORKDIR /app/backend
RUN python -c "from app import runner; runner.warm(); bad = [l for l, ok in runner.TOOLCHAINS.items() if not ok]; assert not bad, runner.REASONS"

ENV PORT=8000
EXPOSE 8000
CMD uvicorn app.main:app --host 0.0.0.0 --port $PORT
