FROM python:3.12-slim-trixie

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ARG PIP_NO_CACHE_DIR=1

# Install Chromium
RUN apt-get -y update
RUN apt-get install -y chromium git --no-install-recommends && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /usr/src/app

# Copy only dependency files first
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-dev

# Copy all other files, including source files
COPY . .
