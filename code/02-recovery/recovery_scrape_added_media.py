"""
recovery_scrape_added_media.py v1.0

機能メモ:
- 追加: READMEに記録した追加リカバリー対象23媒体を個別にスクレイプ
- 追加: 媒体別CSVと実行サマリーCSVを code/02-recovery/output/yyyyMMdd_HHmm に保存
- 追加: Yahoo!ニュースのHTMLクラス変更に備え、記事URL抽出をhrefベースで実施
"""

from __future__ import annotations

import argparse
import csv
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import requests
import urllib3
from bs4 import BeautifulSoup, Tag


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_ROOT = Path(__file__).resolve().parent / "output"
BASE_URL = "https://news.yahoo.co.jp"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


@dataclass(frozen=True)
class RecoveryMedia:
    media_en: str
    media_jp: str
    url: str


RECOVERY_MEDIA = [
    RecoveryMedia("biz_it_sj", "スマートジャパン", "https://news.yahoo.co.jp/media/biz_it_sj"),
    RecoveryMedia("choani", "超！アニメディア", "https://news.yahoo.co.jp/media/choani"),
    RecoveryMedia("clc_toho", "東方新報", "https://news.yahoo.co.jp/media/clc_toho"),
    RecoveryMedia("cosmopoli", "コスモポリタン", "https://news.yahoo.co.jp/media/cosmopoli"),
    RecoveryMedia("dewsv", "ダンスニュースメディアサイト Dews", "https://news.yahoo.co.jp/media/dewsv"),
    RecoveryMedia("gendaibiz", "現代ビジネス", "https://news.yahoo.co.jp/media/gendaibiz"),
    RecoveryMedia("hitoc", "ひとシネマ", "https://news.yahoo.co.jp/media/hitoc"),
    RecoveryMedia("hokuriku", "北陸新幹線で行こう！ 北陸・信越観光ナビ", "https://news.yahoo.co.jp/media/hokuriku"),
    RecoveryMedia("jalan", "じゃらんニュース", "https://news.yahoo.co.jp/media/jalan"),
    RecoveryMedia("kansensho", "感染症・予防接種ナビ", "https://news.yahoo.co.jp/media/kansensho"),
    RecoveryMedia("kyoikuict", "教育とICT Online", "https://news.yahoo.co.jp/media/kyoikuict"),
    RecoveryMedia("nakamaaru", "なかまぁる", "https://news.yahoo.co.jp/media/nakamaaru"),
    RecoveryMedia("rekishin", "歴史人", "https://news.yahoo.co.jp/media/rekishin"),
    RecoveryMedia("rikunabin", "リクナビNEXTジャーナル", "https://news.yahoo.co.jp/media/rikunabin"),
    RecoveryMedia("sakae", "月刊糖尿病ライフ さかえ", "https://news.yahoo.co.jp/media/sakae"),
    RecoveryMedia("shikihos", "会社四季報オンライン", "https://news.yahoo.co.jp/media/shikihos"),
    RecoveryMedia("sjournal", "就職ジャーナル", "https://news.yahoo.co.jp/media/sjournal"),
    RecoveryMedia("socra", "ニュースソクラ", "https://news.yahoo.co.jp/media/socra"),
    RecoveryMedia("srnijugo", "新R25", "https://news.yahoo.co.jp/media/srnijugo"),
    RecoveryMedia("tptj", "ザ・プレーヤーズ・トリビューン ジャパン", "https://news.yahoo.co.jp/media/tptj"),
    RecoveryMedia("umakeiba", "優馬", "https://news.yahoo.co.jp/media/umakeiba"),
    RecoveryMedia("usoccer", "超WORLDサッカー！", "https://news.yahoo.co.jp/media/usoccer"),
    RecoveryMedia("ykf", "夕刊フジ", "https://news.yahoo.co.jp/media/ykf"),
]


def normalize_text(value: str) -> str:
    return " ".join(value.split()).strip()


def clean_title(title: str, date_original: str) -> str:
    if date_original and date_original in title:
        title = title.split(date_original, 1)[0]
    return normalize_text(title)


def nearest_article_container(anchor: Tag) -> Tag:
    for parent in anchor.parents:
        if not isinstance(parent, Tag):
            continue
        if parent.name in {"li", "article"}:
            return parent
        class_text = " ".join(parent.get("class", []))
        if "newsFeed_item" in class_text or "sc-" in class_text:
            return parent
    return anchor


def extract_articles(soup: BeautifulSoup, media: RecoveryMedia, seen_links: set[str]) -> list[dict[str, str]]:
    articles: list[dict[str, str]] = []

    for anchor in soup.find_all("a", href=True):
        href = urljoin(BASE_URL, str(anchor["href"]))
        if "/articles/" not in href or href in seen_links:
            continue

        title = normalize_text(anchor.get_text(" ", strip=True))
        if not title:
            continue

        container = nearest_article_container(anchor)
        time_tag = container.find("time") if isinstance(container, Tag) else None
        date_original = normalize_text(time_tag.get_text(" ", strip=True)) if time_tag else ""
        title = clean_title(title, date_original)
        if not title:
            continue

        seen_links.add(href)
        articles.append(
            {
                "media_en": media.media_en,
                "media_jp": media.media_jp,
                "title_articles": title,
                "date_original": date_original,
                "source_name": media.media_jp,
                "article_link": href,
            }
        )

    return articles


def scrape_media(
    session: requests.Session,
    media: RecoveryMedia,
    output_dir: Path,
    timestamp: str,
    max_pages: int,
    interval: float,
) -> dict[str, str | int]:
    seen_links: set[str] = set()
    rows: list[dict[str, str]] = []
    pages_scraped = 0
    status = "success"
    error = ""

    for page in range(1, max_pages + 1):
        page_url = f"{media.url}?page={page}"
        try:
            response = session.get(page_url, headers=HEADERS, timeout=30, verify=False)
            if response.status_code in {404, 410}:
                status = "not_found" if not rows else "success"
                error = f"HTTP {response.status_code}" if not rows else ""
                break
            response.raise_for_status()
        except requests.RequestException as exc:
            status = "request_error" if not rows else "partial"
            error = str(exc)
            break

        soup = BeautifulSoup(response.text, "html.parser")
        page_rows = extract_articles(soup, media, seen_links)
        if not page_rows:
            if not rows:
                status = "no_data"
            break

        rows.extend(page_rows)
        pages_scraped = page
        print(f"{media.media_en}: page {page} rows={len(page_rows)} total={len(rows)}", flush=True)
        time.sleep(interval)

    output_file = ""
    if rows:
        output_file = str(output_dir / f"html_{media.media_en}_{timestamp}.csv")
        with Path(output_file).open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=[
                    "media_en",
                    "media_jp",
                    "title_articles",
                    "date_original",
                    "source_name",
                    "article_link",
                ],
                lineterminator="\r\n",
            )
            writer.writeheader()
            writer.writerows(rows)

    return {
        "media_en": media.media_en,
        "media_jp": media.media_jp,
        "url": media.url,
        "status": status,
        "pages_scraped": pages_scraped,
        "article_count": len(rows),
        "output_file": output_file,
        "error": error,
    }


def write_summary(output_dir: Path, timestamp: str, rows: list[dict[str, str | int]]) -> Path:
    summary_path = output_dir / f"recovery_scrape_summary_{timestamp}.csv"
    with summary_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "media_en",
                "media_jp",
                "url",
                "status",
                "pages_scraped",
                "article_count",
                "output_file",
                "error",
            ],
            lineterminator="\r\n",
        )
        writer.writeheader()
        writer.writerows(rows)
    return summary_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="追加リカバリー対象23媒体をスクレイプします。")
    parser.add_argument("--max-pages", type=int, default=100)
    parser.add_argument("--interval", type=float, default=1.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    output_dir = OUTPUT_ROOT / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    summary_rows = [
        scrape_media(session, media, output_dir, timestamp, args.max_pages, args.interval)
        for media in RECOVERY_MEDIA
    ]
    summary_path = write_summary(output_dir, timestamp, summary_rows)

    total_articles = sum(int(row["article_count"]) for row in summary_rows)
    print(f"summary={summary_path}", flush=True)
    print(f"media_count={len(summary_rows)}", flush=True)
    print(f"total_articles={total_articles}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
