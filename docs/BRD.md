# Business Requirements Document (BRD)

## Project: OTT Release Automation Platform (where2watch)

**Version:** 1.0  
**Phase:** 1 — Working MVP

---

## Business Objective

Automate daily Instagram content publishing for OTT (Over-The-Top) streaming platform releases, reducing manual effort from ~2 hours/day to near zero while maintaining content quality through a human approval gate.

## Problem Statement

Manually tracking new releases across 10 streaming platforms, creating poster collages, writing captions, and posting to Instagram is time-consuming and error-prone. Content creators often miss release dates or post low-quality images.

## Solution Summary

A GitHub Actions-powered Python pipeline that daily:
1. Fetches new OTT releases from TMDb API
2. Generates a professional poster collage using official artwork
3. Generates an AI-written caption with hashtags
4. Saves a draft for human review
5. Publishes to Instagram after approval

## Supported Platforms

Netflix, Prime Video, Disney+ Hotstar, Aha, Zee5, SonyLIV, JioHotstar, Apple TV+, Hulu, Max

## Supported Languages

Telugu, Hindi, Tamil, Malayalam, Kannada, English

## Supported Content Types

Movies, Web Series, Documentaries, Anime

## Success Criteria

| Metric | Target |
|--------|--------|
| Daily automation rate | ≥ 95% of days with a valid draft |
| Manual effort per post | < 5 minutes (review + approve only) |
| Infrastructure cost | $0–$10/month |
| Draft generation time | < 5 minutes per run |
| Image quality | 1080×1080 PNG, using official poster art |

## Constraints

- No managed databases (Aurora, RDS)
- No serverless functions (Lambda)
- No message queues (SQS)
- No container orchestration (Kubernetes, ECS)
- All state stored in local JSON files and GitHub Artifacts
- Monthly cost target: $0–$10

## Phased Delivery

| Phase | Scope |
|-------|-------|
| 1 | Working MVP — fetch, generate, draft, review |
| 2 | Instagram auto-publishing after approval |
| 3 | Multi-platform publishing (Telegram, Twitter/X) |
| 4 | Analytics dashboard (GitHub Pages) |
