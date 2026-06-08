# Deployment Guide

## Prerequisites

- Python 3.12+
- GitHub repository with Actions enabled
- TMDb API key (free at https://developer.themoviedb.org/)
- OpenAI API key (https://platform.openai.com/)

## Local Setup

```bash
# 1. Clone and create virtual environment
git clone https://github.com/manchisrikanth73/where2watch.git
cd where2watch
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure secrets
cp .env.example .env
# Edit .env and fill in your API keys

# 4. Run a test fetch (uses today's date)
python main.py fetch --skip-approval

# 5. Check the generated draft
ls drafts/$(date +%Y-%m-%d)/
```

## GitHub Actions Setup

### Step 1 — Add Repository Secrets

In your GitHub repository → **Settings → Secrets and variables → Actions**:

| Secret Name | Value |
|-------------|-------|
| `TMDB_API_KEY` | Your TMDb API v3 key |
| `OPENAI_API_KEY` | Your OpenAI API key |
| `INSTAGRAM_ACCESS_TOKEN` | (Phase 2) Instagram Graph API token |
| `INSTAGRAM_USER_ID` | (Phase 2) Instagram Business Account user ID |

> **Note:** `GITHUB_TOKEN` is automatically provided by Actions — do not add it manually.

### Step 2 — Enable Workflow Permissions

**Settings → Actions → General → Workflow permissions**:
- Select **"Read and write permissions"**
- Check **"Allow GitHub Actions to create and approve pull requests"**

This allows the workflow to create GitHub Issues for review.

### Step 3 — Trigger Manually (First Run)

Go to **Actions → Daily OTT Post Generator → Run workflow**.

Optionally specify:
- **date**: `2025-06-07` (leave blank for today)
- **skip_enrich**: `false`
- **skip_approval**: `false`

### Step 4 — Review the Draft

After the workflow completes:
1. Check **Actions → Run → Artifacts** — download `ott-draft-{run_id}` to preview `poster.png` and `caption.txt`
2. Open the GitHub Issue created by the workflow (titled `OTT Draft Review — June 07, 2025`)
3. Add the label `ott-approved` to approve, or `ott-rejected` to reject

### Step 5 — Verify Daily Schedule

The workflow runs at **06:00 UTC** (11:30 AM IST) every day via cron.  
Check **Actions** tab to confirm runs are scheduled.

## Platform Configuration

Edit `config/platforms.json` to:
- Add or remove streaming platforms
- Adjust `tmdb_provider_id` if results seem incorrect
- Change `region` (e.g. `"US"` for US-only platforms)
- Filter `languages` to focus on specific languages

## Tuning Release Volume

In `.env` or GitHub Actions environment:

```bash
# How many days back to look for new releases (default: 1)
DAYS_LOOKBACK=1

# Max releases per platform per media type (default: 5)
MAX_RELEASES_PER_PLATFORM=5
```

## Phase 2 — Instagram Publishing

Once `INSTAGRAM_ACCESS_TOKEN` and `INSTAGRAM_USER_ID` are set:

```bash
# Publish an approved draft (image must be at a public HTTPS URL)
python main.py publish --date 2025-06-07 --image-url https://your-cdn.com/poster.png
```

For fully automated publishing, a `publish-approved.yml` workflow (Phase 2) will:
1. Detect approved GitHub Issues
2. Upload the poster to a CDN or GitHub release asset
3. Call `python main.py publish` automatically

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| `No releases found` | Date range too narrow or provider ID wrong | Increase `DAYS_LOOKBACK` or verify provider IDs in `platforms.json` |
| `ValidationError: TMDB_API_KEY` | Secret not set | Add `TMDB_API_KEY` to GitHub Secrets or `.env` |
| `Font not found` | No TrueType fonts on system | Install `fonts-dejavu-core` (Ubuntu) or the workflow step handles this automatically |
| `OpenAI quota exceeded` | API limit hit | Captions fall back to defaults; check OpenAI billing |
| `GitHub Issue not created` | Missing workflow write permission | Enable read/write permissions in Actions settings |
