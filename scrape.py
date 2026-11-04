import re
import sys
from datetime import datetime, timezone, timedelta
from email.utils import format_datetime
from urllib.parse import urljoin
from xml.sax.saxutils import escape

import requests
from bs4 import BeautifulSoup

PAGE_URL = "https://www.med.kyoto-u.ac.jp/news/category/pressrelease"
FEED_TITLE = "京都大学大学院医学研究科・医学部 お知らせ（非公式RSS）"
FEED_DESC = "京大医学部ニュースの「お知らせ」カテゴリを自動で拾ったRSSです。"
OUTPUT_FILE = "rss.xml"
JST = timezone(timedelta(hours=9))

# 「2026/11/4」のような日付を読み取る目印
DATE_PATTERN = re.compile(r"(\d{4})/(\d{1,2})/(\d{1,2})")


def clean(text):
    # 改行や余計な空白をきれいにする
    return re.sub(r"\s*\n\s*", " ", text).strip()


def fetch_items():
    headers = {"User-Agent": "Mozilla/5.0 (compatible; KyotoMed-rss/1.0; personal use)"}
    res = requests.get(PAGE_URL, headers=headers, timeout=30)
    res.raise_for_status()
    # 文字化け防止のため、バイト列をそのまま渡してBeautifulSoupに判定させる
    soup = BeautifulSoup(res.content, "html.parser")

    items = []
    seen = set()
    for article in soup.select("article.article"):
        link_tag = article.select_one("a.article__inner")
        time_tag = article.select_one("time")
        title_tag = article.select_one(".article__title")
        category_tag = article.select_one(".article__category")
        if not (link_tag and time_tag and title_tag):
            continue

        m = DATE_PATTERN.search(time_tag.get_text())
        if not m:
            continue
        y, mo, d = (int(x) for x in m.groups())
        date = datetime(y, mo, d, 0, 0, 0, tzinfo=JST)

        link = urljoin(PAGE_URL, link_tag.get("href", ""))
        if not link or link in seen:
            continue
        seen.add(link)

        items.append(
            {
                "title": clean(title_tag.get_text()),
                "link": link,
                "category": clean(category_tag.get_text()) if category_tag else "お知らせ",
                "date": date,
            }
        )
    return items


def build_rss(items):
    now = format_datetime(datetime.now(timezone.utc))
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0">',
        "<channel>",
        f"<title>{escape(FEED_TITLE)}</title>",
        f"<link>{escape(PAGE_URL)}</link>",
        f"<description>{escape(FEED_DESC)}</description>",
        "<language>ja</language>",
        f"<lastBuildDate>{now}</lastBuildDate>",
    ]
    for it in items:
        lines += [
            "<item>",
            f"<title>{escape(it['title'])}</title>",
            f"<link>{escape(it['link'])}</link>",
            f'<guid isPermaLink="true">{escape(it["link"])}</guid>',
            f"<category>{escape(it['category'])}</category>",
            f"<pubDate>{format_datetime(it['date'])}</pubDate>",
            "</item>",
        ]
    lines += ["</channel>", "</rss>", ""]
    return "\n".join(lines)


def main():
    items = fetch_items()
    if not items:
        # ページの作りが変わって1件も取れなかった時は、空のRSSで上書きしない
        print("記事が1件も取れませんでした。ページ構造が変わった可能性があります。")
        sys.exit(1)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(build_rss(items))
    print(f"{len(items)}件を書き出しました。")


if __name__ == "__main__":
    main()
