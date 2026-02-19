"""博客來新書/預購書爬蟲。"""

from __future__ import annotations

import logging
import random
import re
import time
from dataclasses import dataclass
from datetime import date, timedelta

import httpx
from bs4 import BeautifulSoup

from book_craw.config import (
    CATEGORIES,
    EBOOK_CATEGORIES,
    EBOOK_NEW_URL_TEMPLATE,
    EXTRA_SOURCES,
    NEW_BOOKS_URL_TEMPLATE,
    PREORDER_URL,
    REQUEST_DELAY_MAX,
    REQUEST_DELAY_MIN,
    REQUEST_HEADERS,
    REQUEST_MAX_RETRIES,
    REQUEST_TIMEOUT,
)

log = logging.getLogger(__name__)

# 全域共用 HTTP client（維持 cookies 與連線池，像正常使用者連續瀏覽）
_client: httpx.Client | None = None


def _get_client() -> httpx.Client:
    """取得或建立共用的 HTTP client。"""
    global _client
    if _client is None:
        _client = httpx.Client(
            headers=REQUEST_HEADERS,
            timeout=REQUEST_TIMEOUT,
            follow_redirects=True,
        )
    return _client


def _random_delay() -> None:
    """隨機等待，模擬人類瀏覽間隔。"""
    delay = random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX)
    time.sleep(delay)


@dataclass
class Book:
    title: str
    url: str
    author: str = ""
    publisher: str = ""
    price: str = ""
    image_url: str = ""
    category: str = ""
    pub_date: str = ""  # e.g. "2026-02-13"


def fetch_page(url: str) -> str:
    """GET 頁面並回傳 HTML，失敗時自動重試（指數退避）。"""
    client = _get_client()
    for attempt in range(1, REQUEST_MAX_RETRIES + 1):
        try:
            resp = client.get(url)
            resp.raise_for_status()
            resp.encoding = "utf-8"
            return resp.text
        except (httpx.HTTPStatusError, httpx.TransportError) as e:
            if attempt == REQUEST_MAX_RETRIES:
                raise
            # 指數退避：10s, 20s, 40s...
            wait = 10 * (2 ** (attempt - 1))
            log.warning("請求失敗 (%s)，%d 秒後重試 (%d/%d): %s",
                        e, wait, attempt, REQUEST_MAX_RETRIES, url)
            time.sleep(wait)
    return ""  # unreachable


def _parse_recent_books(html: str, category: str = "") -> list[Book]:
    """Parse the '近期新書' section which contains pub dates."""
    soup = BeautifulSoup(html, "lxml")
    books: list[Book] = []

    # Find the 近期新書 section
    h3 = None
    for tag in soup.find_all("h3"):
        if "近期新書" in tag.get_text():
            h3 = tag
            break
    if h3 is None:
        log.warning("Could not find '近期新書' section (category=%s)", category)
        return books

    section = h3.find_parent("div", class_=re.compile(r"mod_a"))
    if section is None:
        return books

    for item_div in section.find_all("div", class_="item"):
        # Title & URL
        h4 = item_div.find("h4")
        if not h4:
            continue
        link = h4.find("a", href=re.compile(r"/products/"))
        if not link:
            continue
        title = link.get_text(strip=True)
        href = link["href"]
        if not href.startswith("http"):
            href = "https://www.books.com.tw" + href

        # Author
        author = ""
        author_link = item_div.find("a", href=re.compile(r"adv_author"))
        if author_link:
            author = author_link.get_text(strip=True)

        # Publisher & pub date from <li class="info">
        publisher = ""
        pub_date = ""
        info_li = item_div.find("li", class_="info")
        if info_li:
            pub_link = info_li.find("a", href=re.compile(r"pubid"))
            if pub_link:
                publisher = pub_link.get_text(strip=True)
            info_text = info_li.get_text()
            m = re.search(r"出版日期：(\d{4}-\d{2}-\d{2})", info_text)
            if m:
                pub_date = m.group(1)

        # Price
        price = ""
        price_box = item_div.find("div", class_="price_box") or item_div
        price_text = price_box.get_text()
        m = re.search(r"(\d+)\s*折\s*(\d+)\s*元", price_text)
        if m:
            price = f"{m.group(1)}折 {m.group(2)}元"

        # Cover image
        image_url = ""
        img = item_div.find("img", class_="cover")
        if img and img.get("src"):
            image_url = img["src"]
            if image_url.startswith("//"):
                image_url = "https:" + image_url

        books.append(
            Book(
                title=title,
                url=href,
                author=author,
                publisher=publisher,
                price=price,
                image_url=image_url,
                category=category,
                pub_date=pub_date,
            )
        )

    log.info("Parsed %d books from 近期新書 (category=%s)", len(books), category)
    return books


def _filter_recent(books: list[Book], days: int = 7) -> list[Book]:
    """Keep only books published within the last N days."""
    cutoff = date.today() - timedelta(days=days)
    result = []
    for b in books:
        if not b.pub_date:
            continue
        try:
            pub = date.fromisoformat(b.pub_date)
        except ValueError:
            continue
        if pub >= cutoff:
            result.append(b)
    log.info("Filtered to %d books published after %s", len(result), cutoff)
    return result


_EXTRA_SOURCE_CONFIG: dict[str, dict] = {
    "簡體電子書新書": {"keywords": ["最新上架"], "date_filter": False},
}


def _parse_extra_source(
    html: str,
    category: str,
    keywords: list[str],
    apply_date_filter: bool,
    recent_days: int = 7,
) -> list[Book]:
    """Parse books from an extra source page by section keywords."""
    soup = BeautifulSoup(html, "lxml")

    # Find sections matching keywords
    sections = []
    for h3 in soup.find_all("h3"):
        text = h3.get_text(strip=True)
        if any(kw in text for kw in keywords):
            parent = h3.find_parent("div", class_=re.compile(r"^mod"))
            if parent:
                sections.append(parent)

    if not sections:
        log.warning("No section found for keywords %s (category=%s)", keywords, category)
        return []

    # Pick the section with the most items
    best = max(sections, key=lambda s: len(s.find_all(["li", "div"], class_="item")))

    items = best.find_all(["li", "div"], class_="item")
    books: list[Book] = []
    seen_urls: set[str] = set()

    for item in items:
        # Title & URL
        h4 = item.find("h4")
        if not h4:
            continue
        link = h4.find("a", href=re.compile(r"/products/"))
        if not link:
            continue
        title = link.get_text(strip=True)
        href = link["href"]
        if not href.startswith("http"):
            href = "https://www.books.com.tw" + href

        # Deduplicate (carousel pages may repeat items)
        clean_url = href.split("?")[0]
        if clean_url in seen_urls:
            continue
        seen_urls.add(clean_url)

        # Author — support both adv_author and /f/author
        author = ""
        author_link = item.find("a", href=re.compile(r"(adv_author|/f/author)"))
        if author_link:
            author = author_link.get_text(strip=True)

        # Publisher & pub date from li.info (cebook_new has these)
        publisher = ""
        pub_date = ""
        info_li = item.find("li", class_="info")
        if info_li:
            pub_link = info_li.find("a", href=re.compile(r"pubid"))
            if pub_link:
                publisher = pub_link.get_text(strip=True)
            info_text = info_li.get_text()
            m = re.search(r"出版日期：(\d{4}-\d{2}-\d{2})", info_text)
            if m:
                pub_date = m.group(1)

        # Price — try price_box first, then price_a, then whole item
        price = ""
        price_el = (
            item.find("div", class_="price_box")
            or item.find("li", class_="price_a")
            or item
        )
        price_text = price_el.get_text()
        m = re.search(r"(\d+)\s*折\s*(\d+)\s*元", price_text)
        if m:
            price = f"{m.group(1)}折 {m.group(2)}元"
        else:
            m = re.search(r"(\d+)\s*元", price_text)
            if m:
                price = f"{m.group(1)}元"

        # Cover image
        image_url = ""
        img = item.find("img", class_="cover")
        if img and img.get("src"):
            image_url = img["src"]
            if image_url.startswith("//"):
                image_url = "https:" + image_url

        books.append(
            Book(
                title=title,
                url=href,
                author=author,
                publisher=publisher,
                price=price,
                image_url=image_url,
                category=category,
                pub_date=pub_date,
            )
        )

    log.info("Parsed %d books from %s (category=%s)", len(books), keywords, category)

    if apply_date_filter:
        books = _filter_recent(books, days=recent_days)

    return books


def scrape_extra_source(name: str, url: str, recent_days: int = 7) -> list[Book]:
    """Scrape a single extra source."""
    cfg = _EXTRA_SOURCE_CONFIG.get(name)
    if not cfg:
        log.error("No config for extra source: %s", name)
        return []
    log.info("Fetching extra source %s: %s", name, url)
    html = fetch_page(url)
    return _parse_extra_source(
        html,
        category=name,
        keywords=cfg["keywords"],
        apply_date_filter=cfg["date_filter"],
        recent_days=recent_days,
    )


def scrape_extra_sources(recent_days: int = 7) -> dict[str, list[Book]]:
    """Scrape all extra sources."""
    result: dict[str, list[Book]] = {}
    for name, url in EXTRA_SOURCES.items():
        try:
            result[name] = scrape_extra_source(name, url, recent_days=recent_days)
        except Exception:
            log.exception("Failed to scrape extra source %s", name)
            result[name] = []
        _random_delay()
    return result


def scrape_ebook_category(code: str, recent_days: int = 7) -> list[Book]:
    """爬取單一電子中文書新書分類，依出版日期篩選近 N 天。"""
    name = EBOOK_CATEGORIES.get(code, code)
    url = EBOOK_NEW_URL_TEMPLATE.format(code=code)
    log.info("Fetching ebook category %s (%s): %s", code, name, url)
    html_text = fetch_page(url)
    category = f"電子書-{name}"
    return _parse_extra_source(
        html_text,
        category=category,
        keywords=["新上架"],
        apply_date_filter=True,
        recent_days=recent_days,
    )


def scrape_ebook_categories(recent_days: int = 7) -> dict[str, list[Book]]:
    """爬取所有電子中文書新書分類。"""
    result: dict[str, list[Book]] = {}
    for code in EBOOK_CATEGORIES:
        name = f"電子書-{EBOOK_CATEGORIES[code]}"
        try:
            result[name] = scrape_ebook_category(code, recent_days=recent_days)
        except Exception:
            log.exception("Failed to scrape ebook category %s", name)
            result[name] = []
        _random_delay()
    return result


def scrape_category(code: str, recent_days: int = 7) -> list[Book]:
    """Scrape new books for a single category, filtered to last N days."""
    name = CATEGORIES.get(code, code)
    url = NEW_BOOKS_URL_TEMPLATE.format(code=code)
    log.info("Fetching category %s (%s): %s", code, name, url)
    html = fetch_page(url)
    books = _parse_recent_books(html, category=name)
    books = _filter_recent(books, days=recent_days)
    return books


def scrape_preorders() -> list[Book]:
    """Scrape pre-order books (no date filter)."""
    log.info("Fetching pre-orders: %s", PREORDER_URL)
    html = fetch_page(PREORDER_URL)
    return _parse_recent_books(html, category="預購書")


def scrape_all(
    categories: list[str] | None = None,
    include_preorders: bool = True,
    include_extra: bool = True,
    recent_days: int = 7,
) -> dict[str, list[Book]]:
    """Scrape all (or selected) categories, extra sources, and pre-orders."""
    codes = categories or list(CATEGORIES.keys())
    result: dict[str, list[Book]] = {}

    for code in codes:
        name = CATEGORIES.get(code, code)
        try:
            result[name] = scrape_category(code, recent_days=recent_days)
        except Exception:
            log.exception("Failed to scrape category %s (%s)", code, name)
            result[name] = []
        _random_delay()

    if include_extra:
        result.update(scrape_ebook_categories(recent_days=recent_days))
        result.update(scrape_extra_sources(recent_days=recent_days))

    if include_preorders:
        try:
            result["預購書"] = scrape_preorders()
        except Exception:
            log.exception("Failed to scrape pre-orders")
            result["預購書"] = []

    total = sum(len(v) for v in result.values())
    log.info("Total: %d books across %d categories", total, len(result))
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    books = scrape_category("19")
    for b in books[:10]:
        print(f"  {b.pub_date} | {b.title} | {b.author} | {b.publisher} | {b.price}")
    print(f"... {len(books)} books within last 7 days in 電腦資訊")
