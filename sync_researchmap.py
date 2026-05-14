#!/usr/bin/env python3
"""
sync_researchmap.py
ResearchMap の最新情報を取得して index.html を自動更新するスクリプト

使い方:
    python3 sync_researchmap.py

依存パッケージのインストール:
    pip3 install requests beautifulsoup4
"""

import re
import sys
from pathlib import Path
from datetime import datetime

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("必要なパッケージをインストールしてください:")
    print("  pip3 install requests beautifulsoup4")
    sys.exit(1)

# ===== 設定 =====
RM_USER     = "UNIYA_Akira"
RM_BASE     = f"https://researchmap.jp/{RM_USER}"
HTML_PATH   = Path(__file__).parent / "index.html"
TIMEOUT     = 15  # 秒

# ResearchMap のURLを独自URLで上書きするマッピング
# キー: ResearchMap のアイテムID、値: 使用するURL
CUSTOM_LINKS = {
    "53433394": "https://b.kobe-u.ac.jp/papers/2026_06/",
    "53346571": "https://b.kobe-u.ac.jp/marec/d_paper/2026_d01.html",
}

SECTIONS = [
    ("published_papers",  "rm-papers"),
    ("presentations",     "rm-presentations"),
    ("misc",              "rm-misc"),
]

HEADERS_JA = {
    "Accept-Language": "ja,en;q=0.5",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
}
HEADERS_EN = {
    "Accept-Language": "en,ja;q=0.5",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
}

# ===== カードテンプレート =====
CARD_TMPL = """\
          <div class="gallery-card p-8">
            <div>
              <div class="flex items-center gap-2 mb-4">
                <span class="text-[10px] font-mono text-secondary">{year}</span>{badge}
              </div>
              <h4 class="text-base font-bold text-ink mb-3 leading-tight">
                {title}
              </h4>
              <p class="text-[11px] text-muted italic mb-6">
                {subtitle}
              </p>
            </div>
            <a href="{link}" target="_blank" rel="noopener" class="mt-auto text-[9px] font-bold uppercase tracking-widest border border-primary/20 text-primary px-4 py-2 rounded-full hover:bg-primary hover:text-white transition-all text-center">LINK</a>
          </div>"""

INVITED_BADGE = """\

                <span class="text-[8px] font-bold uppercase tracking-widest bg-secondary/20 text-primary px-2 py-0.5 rounded-full">
                  <span class="ja">招待</span><span class="en">Invited</span>
                </span>"""


def fetch_items(category: str) -> dict:
    """日英両方のページを取得し、アイテムIDをキーに統合して返す。"""
    items: dict[str, dict] = {}

    for lang, headers in [("ja", HEADERS_JA), ("en", HEADERS_EN)]:
        url = f"{RM_BASE}/{category}"
        try:
            r = requests.get(url, headers=headers, timeout=TIMEOUT)
            r.raise_for_status()
        except Exception as e:
            print(f"  ⚠  {lang} の取得に失敗: {e}", file=sys.stderr)
            continue

        soup = BeautifulSoup(r.text, "html.parser")
        for li in soup.select("li.list-group-item.rm-cv-disclosed"):
            content = li.select_one(".rm-cv-list-content")
            if not content:
                continue
            title_el = content.select_one(".rm-cv-list-title")
            if not title_el:
                continue

            href    = title_el.get("href", "")
            item_id = href.rstrip("/").split("/")[-1]
            link    = f"https://researchmap.jp{href}"

            if item_id not in items:
                items[item_id] = {
                    "id": item_id, "link": link,
                    "title": {}, "authors": {}, "meta": {},
                    "invited": False,
                }

            items[item_id]["title"][lang]   = title_el.get_text(strip=True)
            # カスタムURLが設定されていればそちらを優先
            items[item_id]["link"] = CUSTOM_LINKS.get(item_id, link)

            author_div = content.select_one(".rm-cv-list-author")
            if author_div:
                items[item_id]["authors"][lang] = author_div.get_text(strip=True)

            divs = content.find_all("div", recursive=False)
            if len(divs) >= 3:
                items[item_id]["meta"][lang] = divs[2].get_text(" ", strip=True)

            # 招待講演チェック
            label_el = li.select_one(".rm-cv-list-label")
            if label_el:
                label_text = label_el.get_text(strip=True)
                if "招待" in label_text or "invited" in label_text.lower():
                    items[item_id]["invited"] = True

    return items


def extract_year(item: dict) -> str:
    """メタテキストから年（.月）を抽出する。"""
    meta = item["meta"].get("ja") or item["meta"].get("en") or ""
    # "2026年7月" → "2026.07"
    m = re.search(r"(\d{4})年\s*(\d{1,2})月", meta)
    if m:
        return f"{m.group(1)}.{int(m.group(2)):02d}"
    # "2026-07" 形式
    m = re.search(r"(\d{4})-(\d{2})", meta)
    if m:
        return f"{m.group(1)}.{m.group(2)}"
    # 年だけ
    m = re.search(r"\d{4}", meta)
    return m.group(0) if m else ""


def clean_meta(text: str) -> str:
    """メタテキストから日付・役割ラベルを除去してクリーンにする。"""
    # YYYY年M月D日 → 除去
    text = re.sub(r"\d{4}年\s*\d{1,2}月\s*\d{1,2}日", "", text)
    # YYYY年M月 → 除去
    text = re.sub(r"\d{4}年\s*\d{1,2}月", "", text)
    # 残った「D日」 → 除去
    text = re.sub(r"\s*\d{1,2}日\b", "", text)
    # YYYY-MM-DD → 除去
    text = re.sub(r"\d{4}-\d{2}-\d{2}", "", text)
    # 役割ラベル → 除去
    text = re.sub(r"(筆頭著者|corresponding author|責任著者)", "", text, flags=re.IGNORECASE)
    # 余分なスペース整理
    text = re.sub(r"\s{2,}", " ", text).strip().strip("　 ,，、。")
    return text


def fix_authors(text: str) -> str:
    """ResearchMap の '姓, 名, 姓, 名' 形式を '姓 名, 姓 名' に変換する。"""
    if not text:
        return text
    # 日本語文字が含まれるか判定
    has_jp = any("　" <= c <= "鿿" or "゠" <= c <= "ヿ" for c in text)
    if not has_jp:
        return text  # 英語名はそのまま
    parts = [p.strip() for p in text.split(",")]
    if len(parts) >= 2 and len(parts) % 2 == 0:
        names = [f"{parts[i]} {parts[i+1]}" for i in range(0, len(parts), 2)]
        return "，".join(names)
    return text


def bilingual(d: dict, fallback_ja="", fallback_en="") -> str:
    """日英スパンを返す。同じ場合はスパンなし。"""
    ja = fix_authors(d.get("ja") or fallback_ja)
    en = fix_authors(d.get("en") or fallback_en or ja)
    if not ja:
        return en or ""
    if ja == en:
        return ja
    return f'<span class="ja">{ja}</span><span class="en">{en}</span>'


def make_cards(items: dict) -> str:
    if not items:
        return "          <!-- データなし -->"

    sorted_items = sorted(items.values(), key=extract_year, reverse=True)
    cards = []
    for item in sorted_items:
        year    = extract_year(item)
        title   = bilingual(item["title"])
        authors = bilingual(item["authors"], "鵜丹谷 瑛", "Akira Uniya")

        # メタ情報（雑誌名・学会名など）をサブタイトルに付加
        meta_ja = clean_meta(item["meta"].get("ja", ""))
        meta_en = clean_meta(item["meta"].get("en", "")) or meta_ja
        if meta_ja:
            if meta_ja == meta_en:
                subtitle = f'{authors}<br>{meta_ja}'
            else:
                subtitle = (
                    f'{authors}'
                    f'<br><span class="ja">{meta_ja}</span>'
                    f'<span class="en">{meta_en}</span>'
                )
        else:
            subtitle = authors

        badge = INVITED_BADGE if item["invited"] else ""
        cards.append(CARD_TMPL.format(
            year=year, badge=badge, title=title,
            subtitle=subtitle, link=item["link"]
        ))

    return "\n\n".join(cards)


def update_html(html: str, marker: str, content: str) -> str:
    """<!-- {marker}-start --> と <!-- {marker}-end --> の間を置き換える。"""
    pattern = (
        rf"(<!-- {marker}-start -->)"
        rf".*?"
        rf"(<!-- {marker}-end -->)"
    )
    replacement = rf"\1\n{content}\n          \2"
    new_html, n = re.subn(pattern, replacement, html, flags=re.DOTALL)
    if n == 0:
        print(f"  ⚠  マーカー <!-- {marker}-start/end --> が見つかりません", file=sys.stderr)
    return new_html


def main():
    print(f"\n[{datetime.now():%Y-%m-%d %H:%M}] ResearchMap → {HTML_PATH.name} 同期開始")
    print(f"  対象: {RM_BASE}\n")

    html = HTML_PATH.read_text(encoding="utf-8")

    for category, marker in SECTIONS:
        print(f"  📄 {category} を取得中...")
        items = fetch_items(category)
        print(f"     → {len(items)} 件取得")
        if items:
            cards = make_cards(items)
            html  = update_html(html, marker, cards)

    HTML_PATH.write_text(html, encoding="utf-8")
    print(f"\n  ✅ 完了: {HTML_PATH}\n")


if __name__ == "__main__":
    main()
