"""博客來新書爬蟲 CLI 入口。"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from book_craw.config import CATEGORIES, DEDUP_CATEGORIES
from book_craw.emailer import build_html, send_email
from book_craw.pages import generate_index_page, generate_stats_page, generate_weekly_page, load_previous_urls
from book_craw.scraper import scrape_all


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="博客來新書爬蟲")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="輸出 HTML 到 stdout，不寄信",
    )
    parser.add_argument(
        "--category",
        action="append",
        metavar="CODE",
        help="只爬指定分類代碼（可多次使用），例如 --category 01 --category 19",
    )
    parser.add_argument(
        "--no-preorders",
        action="store_true",
        help="不爬預購書",
    )
    parser.add_argument(
        "--no-extra",
        action="store_true",
        help="不爬額外來源（簡體書、電子書等）",
    )
    parser.add_argument(
        "--pages",
        metavar="DIR",
        help="產生靜態 HTML 頁面到指定目錄（供 GitHub Pages 部署）",
    )
    args = parser.parse_args(argv)

    load_dotenv(Path.cwd() / ".env")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    log = logging.getLogger(__name__)

    if args.category:
        for code in args.category:
            if code not in CATEGORIES:
                log.error("Unknown category code: %s", code)
                sys.exit(1)

    log.info("Starting book-craw ...")
    books_by_category = scrape_all(
        categories=args.category,
        include_preorders=not args.no_preorders,
        include_extra=not args.no_extra,
    )

    # 去重：只對沒有日期過濾的來源，移除上期已出現的書籍
    if args.pages:
        prev_urls = load_previous_urls(Path(args.pages), date.today().isoformat())
        if prev_urls:
            before = sum(len(v) for v in books_by_category.values())
            for cat in books_by_category:
                if cat not in DEDUP_CATEGORIES:
                    continue
                books_by_category[cat] = [
                    b for b in books_by_category[cat]
                    if b.url.split("?")[0] not in prev_urls
                ]
            after = sum(len(v) for v in books_by_category.values())
            log.info("Dedup: %d → %d books (%d removed)", before, after, before - after)

    total = sum(len(v) for v in books_by_category.values())
    if total == 0:
        log.warning("No books found, skipping.")
        return

    if args.pages:
        output_dir = Path(args.pages)
        generate_weekly_page(books_by_category, date.today(), output_dir)
        generate_index_page(output_dir)
        generate_stats_page(output_dir)
        log.info("Pages generated in %s (%d books).", output_dir, total)

    html = build_html(books_by_category)

    if args.dry_run:
        print(html)
        return

    subject = f"博客來新書通知 - {date.today().isoformat()}"
    send_email(html, subject=subject)
    log.info("Done. %d books sent.", total)
