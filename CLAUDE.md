# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is Flathunter

A Python bot that crawls German real estate portals (ImmoScout24, Kleinanzeigen, Immowelt) for rental listings and sends notifications via Telegram, Slack, or Mattermost. Runs as either a CLI loop (`flathunt.py`) or a Flask web server (`main.py`).

## Commands

```sh
# Install dependencies
uv sync                      # dev (includes ruff, etc.)
uv sync --frozen --no-dev    # production only

# Run tests
pytest                       # all tests
pytest test/test_hunter.py   # single file
pytest test/test_hunter.py::TestHunter::test_hunt_flats -v  # single test

# Coverage
coverage run                 # runs pytest via .coveragerc config
coverage report

# Lint (ruff with ALL rules enabled, target py313)
ruff check .
ruff check --fix .           # auto-fix
ruff format .                # format

# Type checking
pyright

# Run the bot (CLI mode)
python flathunt.py --config config.yaml

# Run the web server
python main.py               # Flask on localhost:8080

# Docker
docker compose up --build
```

## Architecture

**Processing pipeline** -- the core flow in `Hunter.hunt_flats()`:

```
Config.target_urls() + Config.searchers()
  -> Crawler.crawl(url)           # yields raw expose dicts
  -> ProcessorChain.process()     # reduce over a list of Processors
       ├─ SaveAllExposesProcessor  (persist to SQLite via IdMaintainer)
       ├─ Filter                   (price/size/rooms/already-seen)
       ├─ AddressResolver          (geocode from expose page)
       ├─ GMapsDurationProcessor   (Google Maps travel time)
       └─ SenderTelegram/Slack     (notify user)
```

Both `ProcessorChain` and `Filter` use the **builder pattern**. Processors implement `process_exposes(exposes)` from `abstract_processor.py` and compose via `functools.reduce`.

**Key abstractions:**
- `abstract_crawler.py` -- base for all crawlers; each site-specific crawler lives in `flathunter/crawler/`
- `abstract_notifier.py` -- base for notification senders in `flathunter/notifiers/`
- `abstract_processor.py` -- base `Processor` interface that the chain reduces over
- `config.py` -- loads YAML config with env var overrides (`FLATHUNTER_*` prefix)
- `idmaintainer.py` -- SQLite wrapper for deduplication (`processed_ids.db`)
- `flathunter/web/` -- Flask app with views, templates, static assets

**An "expose"** is the central data structure: a plain dict representing a single property listing, passed through the entire pipeline.

## Configuration

YAML file (`config.yaml`, see `config.yaml.dist` for all options) with environment variable overrides. All env vars use the `FLATHUNTER_` prefix (e.g., `FLATHUNTER_TARGET_URLS`, `FLATHUNTER_TELEGRAM_BOT_TOKEN`).

## CI

Three GitHub Actions workflows on push to main / PRs:
- **tests.yml** -- pytest with coverage (Python 3.10 & 3.11, installs Chrome for headless browser tests)
- **linter.yml** -- ruff via custom action in `.github/actions/pylint-runner/`
- **types.yml** -- pyright type checking
