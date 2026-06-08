#!/usr/bin/env python3
"""
OTT Release Automation Platform — CLI entry point.

Commands
--------
  fetch          Fetch today's OTT releases and generate a draft (Phase 1 core)
  weekly         Generate a weekly watchlist draft (last 7 days)
  check-approval Check GitHub Issue approval status for a draft date
  upload         Upload poster to Imgur and print the public URL (Phase 2)
  publish        Publish an approved draft to Instagram (Phase 2)
  refresh-token  Inspect and refresh the Instagram access token (Phase 2)

Examples
--------
  python main.py fetch
  python main.py fetch --date 2025-06-07
  python main.py fetch --skip-enrich --skip-approval
  python main.py weekly
  python main.py check-approval --date 2025-06-07
  python main.py upload --date 2025-06-07
  python main.py upload --date 2025-06-07 --all-slides
  python main.py publish --date 2025-06-07 --image-url https://...
  python main.py refresh-token
  python main.py refresh-token --force
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import date, timedelta
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Command implementations ────────────────────────────────────────────────────

def cmd_fetch(args: argparse.Namespace) -> int:
    from src.aggregator.ott_aggregator import OTTAggregator
    from src.approval.approval_workflow import ApprovalWorkflow
    from src.caption.caption_generator import CaptionGenerator
    from src.config import get_settings
    from src.draft.draft_manager import DraftManager
    from src.image.poster_generator import PosterGenerator
    from src.metadata.tmdb_service import TMDbService

    settings = get_settings()
    target_date = date.fromisoformat(args.date) if args.date else date.today()

    logger.info("━━━ Step 1/5: Fetching OTT releases for %s ━━━", target_date)
    aggregator = OTTAggregator(settings)
    releases = aggregator.fetch_releases(days_back=settings.days_lookback)

    if not releases:
        logger.warning("No releases found for %s — draft will be saved as empty", target_date)

    if not args.skip_enrich and releases:
        logger.info("━━━ Step 2/5: Enriching metadata (%d releases) ━━━", len(releases))
        service = TMDbService(settings)
        releases = service.enrich_all(releases)
    else:
        logger.info("━━━ Step 2/5: Skipping metadata enrichment ━━━")

    logger.info("━━━ Step 3/5: Generating poster image ━━━")
    poster_gen = PosterGenerator(settings)
    poster = poster_gen.generate_daily(releases, target_date)

    logger.info("━━━ Step 4/5: Generating caption ━━━")
    caption_gen = CaptionGenerator(settings)
    caption = caption_gen.generate_daily(releases, target_date)

    logger.info("━━━ Step 5/5: Saving draft ━━━")
    draft_mgr = DraftManager(settings)
    draft_dir = draft_mgr.save(target_date, releases, caption, poster)

    if not args.skip_approval:
        run_id = os.environ.get("GITHUB_RUN_ID", "")
        approval = ApprovalWorkflow(settings)
        issue_num = approval.create_review_issue(target_date, len(releases), run_id=run_id)
        if issue_num:
            logger.info("Review issue created: #%d", issue_num)
        else:
            logger.info("(Set GITHUB_TOKEN + GITHUB_REPOSITORY to enable review issues)")

    print(f"\n✅  Draft saved → {draft_dir}")
    print(f"   Releases : {len(releases)}")
    print(f"   Caption  : {caption.short_caption[:80]}…")
    print(f"\nTo publish: python main.py publish --date {target_date.isoformat()} --image-url <url>")
    return 0


def cmd_weekly(args: argparse.Namespace) -> int:
    from src.aggregator.ott_aggregator import OTTAggregator
    from src.caption.caption_generator import CaptionGenerator
    from src.config import get_settings
    from src.draft.draft_manager import DraftManager
    from src.image.poster_generator import PosterGenerator
    from src.metadata.tmdb_service import TMDbService

    settings = get_settings()
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    week_label = f"{week_start.strftime('%b %d')} – {week_end.strftime('%b %d, %Y')}"

    logger.info("Generating weekly watchlist for %s", week_label)
    releases = OTTAggregator(settings).fetch_releases(days_back=7)
    releases = TMDbService(settings).enrich_all(releases)

    by_platform: dict[str, list] = {}
    for r in releases:
        by_platform.setdefault(r.platform, []).append(r)

    poster_gen = PosterGenerator(settings)
    slides = poster_gen.generate_weekly_slides(by_platform, week_label)

    caption_gen = CaptionGenerator(settings)
    caption = caption_gen.generate_weekly(releases, week_label)

    draft_mgr = DraftManager(settings)
    draft_dir = draft_mgr.save(today, releases, caption, slides[0] if slides else None)

    slides_dir = draft_dir / "slides"
    slides_dir.mkdir(exist_ok=True)
    for i, slide in enumerate(slides, 1):
        slide.save(str(slides_dir / f"slide_{i:02d}.png"), format="PNG")

    print(f"\n✅  Weekly draft → {draft_dir}  ({len(slides)} slides, {len(releases)} releases)")
    return 0


def cmd_upload(args: argparse.Namespace) -> int:
    """Uploads poster (or weekly slides) to Imgur. Prints public URL(s) to stdout."""
    from src.config import get_settings
    from src.draft.draft_manager import DraftManager
    from src.publisher.image_host import upload_poster, upload_slides

    settings = get_settings()
    target_date = date.fromisoformat(args.date) if args.date else date.today()
    draft_mgr = DraftManager(settings)

    if args.all_slides:
        slides_dir = settings.drafts_dir / target_date.isoformat() / "slides"
        slide_paths = sorted(slides_dir.glob("slide_*.png")) if slides_dir.exists() else []
        if not slide_paths:
            # Fall back to single poster if no slides
            poster = draft_mgr.get_poster_path(target_date)
            slide_paths = [poster] if poster else []

        if not slide_paths:
            logger.error("No slides or poster found for %s", target_date)
            return 1

        urls = upload_slides(slide_paths, settings)
        if not urls:
            logger.error("All uploads failed")
            return 1

        print(json.dumps(urls))  # JSON array — consumed by publish-approved.yml
        return 0

    # Single poster upload
    poster_path = draft_mgr.get_poster_path(target_date)
    if not poster_path:
        logger.error("No poster found for %s", target_date)
        return 1

    url = upload_poster(poster_path, settings)
    if not url:
        return 1

    print(url)  # Single URL — captured by the workflow
    return 0


def cmd_check_approval(args: argparse.Namespace) -> int:
    from src.approval.approval_workflow import ApprovalWorkflow
    from src.config import get_settings

    target_date = date.fromisoformat(args.date) if args.date else date.today()
    status = ApprovalWorkflow(get_settings()).check_approval(target_date)
    print(f"Approval status for {target_date}: {status.upper()}")
    return 0 if status == "approved" else 1


def cmd_publish(args: argparse.Namespace) -> int:
    from src.approval.approval_workflow import ApprovalWorkflow
    from src.config import get_settings
    from src.draft.draft_manager import DraftManager
    from src.publisher.instagram_publisher import InstagramPublisher

    settings = get_settings()
    target_date = date.fromisoformat(args.date) if args.date else date.today()

    if not args.force:
        status = ApprovalWorkflow(settings).check_approval(target_date)
        if status == "rejected":
            logger.error("Draft for %s was REJECTED — aborting", target_date)
            return 1
        if status == "pending":
            logger.error("Draft for %s is PENDING approval. Use --force to override.", target_date)
            return 1

    draft_mgr = DraftManager(settings)
    caption_path = settings.drafts_dir / target_date.isoformat() / "caption.txt"
    if not caption_path.exists():
        logger.error("No caption file found for %s", target_date)
        return 1

    caption_text = caption_path.read_text(encoding="utf-8")

    # Accept either --image-url (single) or --carousel-urls (JSON array for weekly)
    image_url = args.image_url
    carousel_urls_raw = args.carousel_urls

    if not image_url and not carousel_urls_raw:
        logger.error(
            "Provide --image-url <url> for a single post, or "
            "--carousel-urls '[\"url1\",\"url2\"]' for a carousel."
        )
        return 1

    publisher = InstagramPublisher(settings)
    if not publisher.verify_credentials():
        return 1

    if carousel_urls_raw:
        urls: list[str] = json.loads(carousel_urls_raw)
        result = publisher.publish_carousel(urls, caption_text)
    else:
        result = publisher.publish_single(image_url, caption_text)

    if result.success:
        draft_mgr.update_status(target_date, "published", instagram_post_id=result.post_id)
        # Close the GitHub review issue
        from src.approval.approval_workflow import ApprovalWorkflow
        approval = ApprovalWorkflow(settings)
        issue_num = approval.find_issue_number(target_date)
        if issue_num:
            approval.close_issue(
                issue_num,
                f"✅ Published to Instagram!\n\n**Post ID:** `{result.post_id}`",
            )
        print(f"\n✅  Published!  Post ID: {result.post_id}")
        return 0

    draft_mgr.update_status(target_date, "failed", error=result.error)
    logger.error("❌  Publish failed: %s", result.error)
    return 1


def cmd_refresh_token(args: argparse.Namespace) -> int:
    """Inspect and conditionally refresh the Instagram access token.

    Prints the new token to stdout ONLY when a refresh occurred (so the calling
    workflow can capture it via command substitution).  Exits 0 when healthy or
    successfully refreshed, exits 1 on failure.
    """
    from src.config import get_settings
    from src.publisher.token_refresher import TokenRefresher

    settings = get_settings()
    refresher = TokenRefresher(settings)

    if not settings.instagram_access_token:
        logger.error("INSTAGRAM_ACCESS_TOKEN is not set — nothing to inspect")
        return 1

    if not settings.facebook_app_id or not settings.facebook_app_secret:
        logger.error(
            "FACEBOOK_APP_ID and FACEBOOK_APP_SECRET are required for token refresh. "
            "Register a Facebook App at https://developers.facebook.com/apps/"
        )
        return 1

    try:
        info = refresher.inspect_token()
    except Exception as exc:
        logger.error("Failed to inspect token: %s", exc)
        return 1

    if not info.is_valid:
        logger.error("Token is INVALID: %s", info.error)
        # Still attempt a refresh — sometimes debug_token is wrong but exchange works
        should_refresh = True
    elif info.never_expires:
        logger.info("Token never expires — no refresh needed")
        return 0
    else:
        days = info.days_remaining or 0
        logger.info("Token expires in %d day(s)", days)
        should_refresh = args.force or refresher.needs_refresh(threshold_days=14)

    if not should_refresh:
        logger.info("Token is healthy — no refresh needed")
        return 0

    logger.info("Refreshing token…")
    try:
        new_token = refresher.refresh()
    except Exception as exc:
        logger.error("Token refresh failed: %s", exc)
        return 1

    # Print the new token to stdout so the workflow can capture it.
    # The workflow must mask it immediately with `echo "::add-mask::$NEW_TOKEN"`.
    print(new_token)
    return 0


# ── Argument parser ────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="where2watch",
        description="OTT Release Automation Platform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = p.add_subparsers(dest="command", required=True)

    pf = sub.add_parser("fetch", help="Fetch releases and generate a draft")
    pf.add_argument("--date", help="Override target date (YYYY-MM-DD)")
    pf.add_argument("--skip-enrich", action="store_true", help="Skip TMDb metadata enrichment")
    pf.add_argument("--skip-approval", action="store_true", help="Skip GitHub review issue creation")

    sub.add_parser("weekly", help="Generate weekly watchlist draft (last 7 days)")

    pca = sub.add_parser("check-approval", help="Check GitHub Issue approval status")
    pca.add_argument("--date", help="Draft date (YYYY-MM-DD)")

    pu = sub.add_parser("upload", help="Upload poster to Imgur and print public URL")
    pu.add_argument("--date", help="Draft date (YYYY-MM-DD), defaults to today")
    pu.add_argument("--all-slides", action="store_true", help="Upload all weekly slides; print JSON array")

    pp = sub.add_parser("publish", help="Publish an approved draft to Instagram")
    pp.add_argument("--date", help="Draft date (YYYY-MM-DD), defaults to today")
    pp.add_argument("--image-url", help="Public HTTPS URL to the poster image (single post)")
    pp.add_argument("--carousel-urls", help="JSON array of public URLs for a carousel post")
    pp.add_argument("--force", action="store_true", help="Skip approval check")

    prt = sub.add_parser("refresh-token", help="Inspect and refresh the Instagram access token")
    prt.add_argument(
        "--force",
        action="store_true",
        help="Refresh even if the token is healthy and not near expiry",
    )

    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    handlers = {
        "fetch": cmd_fetch,
        "weekly": cmd_weekly,
        "check-approval": cmd_check_approval,
        "upload": cmd_upload,
        "publish": cmd_publish,
        "refresh-token": cmd_refresh_token,
    }
    fn = handlers.get(args.command)
    if fn is None:
        parser.print_help()
        sys.exit(1)
    sys.exit(fn(args))


if __name__ == "__main__":
    main()
