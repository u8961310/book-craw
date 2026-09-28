"""博客來新書爬蟲 CLI 入口。"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from book_craw.config import CATEGORIES, DEDUP_CATEGORIES, MIN_COVER_RATIO
from book_craw.emailer import build_html, send_email
from book_craw.pages import (
    generate_index_page,
    generate_stats_page,
    generate_weekly_page,
    load_previous_urls,
    rebuild_all,
)
from book_craw.scraper import Book, scrape_all


class HealthCheckError(RuntimeError):
    """爬取結果明顯壞掉（全部失敗、封面 0%），不該寄信也不該發佈。"""


def check_health(books_by_category: dict[str, list[Book]], failed: list[str]) -> list[str]:
    """檢查爬取結果，回傳要顯示給讀者的警告；嚴重異常直接拋 HealthCheckError。"""
    all_books = [b for books in books_by_category.values() for b in books]
    total = len(all_books)
    warnings: list[str] = []

    if failed:
        if total == 0:
            raise HealthCheckError(f"所有來源都爬取失敗：{'、'.join(failed)}")
        warnings.append(f"以下分類爬取失敗，本期可能缺書：{'、'.join(failed)}")

    empty = [c for c, books in books_by_category.items() if not books and c not in failed]
    if total and len(empty) >= max(3, len(books_by_category) // 2):
        warnings.append(f"有 {len(empty)} 個分類抓到 0 本，網頁結構可能改了：{'、'.join(empty)}")

    if total:
        ratio = sum(1 for b in all_books if b.image_url) / total
        if ratio == 0 and total >= 10:
            raise HealthCheckError(f"{total} 本書全部沒有封面，封面解析可能壞了")
        if ratio < MIN_COVER_RATIO:
            warnings.append(f"只有 {ratio:.0%} 的書有封面，封面解析可能有問題")

    return warnings


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
        help="不爬額外來源（電子書等）",
    )
    parser.add_argument(
        "--pages",
        metavar="DIR",
        help="產生靜態 HTML 頁面到指定目錄（供 GitHub Pages 部署）",
    )
    parser.add_argument(
        "--rebuild",
        metavar="DIR",
        help="不爬取，用既有書單資料把 DIR 內所有頁面換成目前版型",
    )
    args = parser.parse_args(argv)

    load_dotenv(Path.cwd() / ".env")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    log = logging.getLogger(__name__)

    if args.rebuild:
        n = rebuild_all(Path(args.rebuild))
        log.info("Rebuilt %d weekly pages in %s", n, args.rebuild)
        return

    if args.category:
        for code in args.category:
            if code not in CATEGORIES:
                log.error("Unknown category code: %s", code)
                sys.exit(1)

    log.info("Starting book-craw ...")
    failed: list[str] = []
    books_by_category = scrape_all(
        categories=args.category,
        include_preorders=not args.no_preorders,
        include_extra=not args.no_extra,
        failed=failed,
    )

    try:
        warnings = check_health(books_by_category, failed)
    except HealthCheckError as e:
        log.error("Health check failed: %s", e)
        print(f"::error::{e}")
        sys.exit(1)
    for w in warnings:
        log.warning("Health check: %s", w)
        print(f"::warning::{w}")

    # 去重：只對沒有日期過濾的來源，移除過去任一期已出現的書籍
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
        generate_weekly_page(books_by_category, date.today(), output_dir, warnings=warnings)
        generate_index_page(output_dir)
        generate_stats_page(output_dir)
        log.info("Pages generated in %s (%d books).", output_dir, total)

    html = build_html(books_by_category, warnings=warnings)

    if args.dry_run:
        print(html)
        return

    subject = f"博客來新書通知 - {date.today().isoformat()}"
    if warnings:
        subject = "⚠️ " + subject
    send_email(html, subject=subject)
    log.info("Done. %d books sent.", total)
