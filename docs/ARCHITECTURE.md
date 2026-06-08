# Solution Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        GitHub Actions                           │
│                                                                 │
│  Schedule (6 AM UTC)  ──►  daily-ott-post.yml                  │
│                                  │                              │
│                                  ▼                              │
│              ┌───────────────────────────────────┐              │
│              │        Python Application          │              │
│              │                                   │              │
│              │  OTTAggregator                    │              │
│              │    └─► TMDb Discover API          │              │
│              │                                   │              │
│              │  TMDbService                      │              │
│              │    └─► TMDb Detail + Credits API  │              │
│              │                                   │              │
│              │  PosterGenerator (Pillow)          │              │
│              │    └─► Official poster artwork     │              │
│              │                                   │              │
│              │  CaptionGenerator (OpenAI)         │              │
│              │    └─► GPT-4o-mini                 │              │
│              │                                   │              │
│              │  DraftManager                     │              │
│              │    └─► drafts/YYYY-MM-DD/         │              │
│              │                                   │              │
│              │  ApprovalWorkflow                  │              │
│              │    └─► GitHub Issues API           │              │
│              └───────────────────────────────────┘              │
│                                  │                              │
│                    Upload Artifact (drafts/)                    │
└─────────────────────────────────────────────────────────────────┘
                                   │
              ┌────────────────────┘
              ▼
    ┌──────────────────┐
    │  Human Reviewer  │
    │                  │
    │  Reviews draft   │
    │  Adds label:     │
    │  ott-approved    │
    └────────┬─────────┘
             │  (Phase 2)
             ▼
    ┌──────────────────────────────┐
    │  publish-approved.yml        │
    │  (manual workflow_dispatch)  │
    │                              │
    │  InstagramPublisher          │
    │    └─► Instagram Graph API   │
    └──────────────────────────────┘
```

## Module Responsibilities

| Module | Responsibility |
|--------|----------------|
| `src/aggregator/ott_aggregator.py` | Calls TMDb `/discover/movie` and `/discover/tv` filtered by streaming provider ID and region |
| `src/metadata/tmdb_service.py` | Fetches full detail (genres, runtime, rating) and credits (cast) for each release |
| `src/image/poster_generator.py` | Builds 1080×1080 collage using Pillow — downloads official poster art from TMDb image CDN |
| `src/caption/caption_generator.py` | Sends structured prompt to OpenAI, parses JSON response into `GeneratedCaption` |
| `src/draft/draft_manager.py` | Persists `poster.png`, `caption.txt`, `hashtags.txt`, `release_data.json`, `metadata.json` |
| `src/approval/approval_workflow.py` | Creates GitHub Issue with review checklist; checks label to determine approval status |
| `src/publisher/instagram_publisher.py` | Posts via Instagram Graph API (Phase 2) |

## Data Flow

```
TMDb API
  └─► list[Release]  (raw, from Discover endpoint)
        └─► list[Release]  (enriched, with genres/cast/runtime)
              ├─► Image.Image  (1080×1080 poster collage)
              ├─► GeneratedCaption  (short + long + hashtags + CTA)
              └─► drafts/2025-06-07/
                    ├── poster.png
                    ├── caption.txt
                    ├── hashtags.txt
                    ├── release_data.json
                    └── metadata.json
```

## Platform Coverage

| Platform | TMDb Provider ID | Region | Primary Languages |
|----------|-----------------|--------|-------------------|
| Netflix | 8 | IN | hi, en, te, ta, ml, kn |
| Prime Video | 119 | IN | hi, en, te, ta, ml, kn |
| Disney+ Hotstar | 122 | IN | hi, en, te, ta, ml, kn |
| Aha | 532 | IN | te, ta |
| Zee5 | 232 | IN | hi, te, ta, ml, kn, en |
| SonyLIV | 237 | IN | hi, te, ta, en |
| JioHotstar | 220 | IN | hi, en, te, ta, ml, kn |
| Apple TV+ | 350 | IN | en |
| Hulu | 15 | US | en |
| Max | 1899 | US | en |

## Cost Breakdown (Monthly)

| Service | Usage | Cost |
|---------|-------|------|
| TMDb API | Unlimited requests | $0 (free) |
| OpenAI GPT-4o-mini | ~30 requests/month | ~$0.01 |
| GitHub Actions | ~31 runs × 3 min | Free tier |
| Instagram Graph API | Feed posts | $0 |
| **Total** | | **~$0.01** |
