# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**where2watch** — OTT Release Automation Platform. Fetches daily OTT releases from TMDb, generates a 1080×1080 Instagram-ready poster collage + AI caption, saves a draft for human review, and (Phase 2) publishes to Instagram after approval.

## Branch Conventions

- `master` — production-ready code
- `test` — pre-production testing  
- `dev` — active development

Development flow: `feature branch` → `dev` → `test` → `master`

## Commands

```bash
# Install
pip install -r requirements.txt          # production
pip install -r requirements-dev.txt      # development + tests

# Run the pipeline
python main.py fetch                     # fetch today's releases + generate draft
python main.py fetch --date 2025-06-07   # specific date
python main.py fetch --skip-enrich       # skip TMDb enrichment (faster)
python main.py fetch --skip-approval     # skip GitHub Issue creation
python main.py weekly                    # weekly watchlist (7-day lookback)
python main.py check-approval --date 2025-06-07
python main.py publish --date 2025-06-07 --image-url https://...

# Tests
pytest                                   # all tests with coverage
pytest tests/test_aggregator.py          # single test file
pytest -k test_fetch_releases            # single test by name
pytest --no-cov                          # without coverage report

# Lint / format
ruff check src/ tests/                   # lint
black src/ tests/                        # format
mypy src/                                # type check
```

## Architecture

```
main.py  (CLI, argparse)
  │
  ├── OTTAggregator          src/aggregator/ott_aggregator.py
  │     ├── TMDb /discover/movie + /discover/tv
  │     └── models: Release, ContentType    src/aggregator/models.py
  │
  ├── TMDbService            src/metadata/tmdb_service.py
  │     └── TMDb /{media_type}/{id} + /credits
  │
  ├── PosterGenerator        src/image/poster_generator.py
  │     └── Pillow 1080×1080 collage, official TMDb poster art
  │
  ├── CaptionGenerator       src/caption/caption_generator.py
  │     └── OpenAI gpt-4o-mini, JSON mode, returns GeneratedCaption
  │
  ├── DraftManager           src/draft/draft_manager.py
  │     └── drafts/YYYY-MM-DD/{poster.png, caption.txt, metadata.json, ...}
  │
  ├── ApprovalWorkflow       src/approval/approval_workflow.py
  │     └── GitHub Issues API — labels: ott-pending / ott-approved / ott-rejected
  │
  └── InstagramPublisher     src/publisher/instagram_publisher.py
        └── Instagram Graph API v19.0 (Phase 2)
```

## Configuration

All settings live in `src/config.py` (pydantic-settings). Copy `.env.example` to `.env`:

```
TMDB_API_KEY=...         # required
OPENAI_API_KEY=...       # required
INSTAGRAM_ACCESS_TOKEN=  # Phase 2
INSTAGRAM_USER_ID=       # Phase 2
GITHUB_TOKEN=            # auto-injected in Actions
GITHUB_REPOSITORY=       # auto-injected in Actions
```

Platform definitions (TMDb provider IDs, regions, language filters) are in `config/platforms.json`.

## GitHub Actions

`.github/workflows/daily-ott-post.yml` — runs at 06:00 UTC daily.

Required repository secrets: `TMDB_API_KEY`, `OPENAI_API_KEY`.  
Workflow permissions must be set to **read and write** (for issue creation).

Draft artifacts are uploaded as `ott-draft-{run_id}` with 7-day retention.

## Key Conventions

- `Release.to_dict()` / `Release.from_dict()` are the serialisation boundary — always use these for JSON persistence.
- All external HTTP calls go through `tenacity` retry decorators — do not call `requests` directly without retry handling.
- `CaptionGenerator._chat()` always uses `response_format={"type": "json_object"}` — OpenAI must return valid JSON; fallback defaults are defined in `generate_daily()`.
- `PosterGenerator` never generates AI images — only official poster art from `https://image.tmdb.org/t/p/w500{poster_path}` is used. If a poster fails to download, a coloured placeholder with the title is rendered instead.
- Draft `metadata.json` is the source of truth for status (`pending` → `approved`/`rejected` → `published`/`failed`).

## Docs

- `docs/ARCHITECTURE.md` — component diagram, data flow, cost breakdown
- `docs/TDD.md` — design decisions, module contracts, error handling
- `docs/DEPLOYMENT.md` — step-by-step setup and troubleshooting
- `docs/BRD.md` — business requirements and constraints
