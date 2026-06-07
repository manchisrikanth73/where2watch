# Technical Design Document (TDD)

## Technology Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Language | Python 3.12 | Modern type hints, match statements, performance |
| Configuration | pydantic-settings | Type-safe env var loading with validation |
| HTTP | requests + tenacity | Simple HTTP with automatic retry/backoff |
| Image | Pillow (PIL) | Mature, zero-cost image manipulation |
| AI captions | OpenAI SDK (gpt-4o-mini) | Cheapest capable model; ~$0.01/day |
| CI/CD | GitHub Actions | Free tier sufficient; native artifact storage |
| State | Local JSON files | Zero infrastructure cost; version-controllable |
| Tests | pytest + responses | Standard Python testing; HTTP mocking |

## Key Design Decisions

### 1. TMDb as the sole data source
TMDb's free Discover API supports filtering by streaming provider and region, covers all 10 target platforms, and provides official poster artwork. No scraping required.

### 2. JSON file state over a database
Drafts are saved to `drafts/YYYY-MM-DD/` directories. GitHub Artifacts provide persistence across workflow runs. This eliminates all database costs and complexity.

### 3. GitHub Issues as the approval mechanism
Creating a GitHub Issue with `ott-pending` label is free, integrates naturally with the repo, and gives reviewers a familiar interface. Approval is signalled by adding `ott-approved` label.

### 4. Official poster artwork only
`PosterGenerator` downloads TMDb's hosted poster images (covered by TMDb's terms of service for non-commercial display). No AI image generation is used.

### 5. OpenAI JSON mode
All OpenAI calls use `response_format={"type": "json_object"}` to guarantee parseable output. Malformed responses fall back to safe defaults — the pipeline never crashes on a caption failure.

## Module Interface Contracts

### `OTTAggregator.fetch_releases()`
```
Input:  days_back: int, platforms: list[Platform]
Output: list[Release]
Side effects: HTTP GET to TMDb Discover API
```

### `TMDbService.enrich()`
```
Input:  release: Release
Output: Release  (mutated in-place, same object returned)
Side effects: 2× HTTP GET to TMDb Detail + Credits API
```

### `PosterGenerator.generate_daily()`
```
Input:  releases: list[Release], target_date: date
Output: PIL.Image.Image (1080×1080, RGB)
Side effects: HTTP GET for each poster_url (skipped if None)
```

### `CaptionGenerator.generate_daily()`
```
Input:  releases: list[Release], target_date: date
Output: GeneratedCaption
Side effects: 1× HTTP POST to OpenAI Chat Completions API
```

### `DraftManager.save()`
```
Input:  draft_date, releases, caption, poster (optional)
Output: Path  (directory where draft was saved)
Side effects: Creates files under drafts/YYYY-MM-DD/
```

## Error Handling Strategy

| Scenario | Behaviour |
|----------|-----------|
| TMDb API 5xx | Retry 3× with exponential backoff (4–30s). On final failure, log error and skip that platform. |
| Poster download failure | Log warning, use placeholder image with title text |
| OpenAI API failure | Log error, return default fallback caption (no crash) |
| GitHub API failure | Log warning, skip issue creation (draft still saved) |
| Zero releases found | Save empty draft; issue is still created for visibility |

## File Layout

```
drafts/
  2025-06-07/
    poster.png          # 1080×1080 RGB collage
    caption.txt         # Full post text (short + CTA + hashtags)
    hashtags.txt        # Hashtags only (for copy-paste)
    release_data.json   # Serialised list[Release]
    metadata.json       # status, created_at, instagram_post_id, etc.
```

## Retry Configuration

All external HTTP calls use `tenacity`:
- **TMDb**: 3 attempts, exponential backoff 4–30s, retry on `HTTPError`
- **OpenAI**: 3 attempts, exponential backoff 2–20s
- **Instagram Graph API**: 3 attempts, exponential backoff 4–60s
