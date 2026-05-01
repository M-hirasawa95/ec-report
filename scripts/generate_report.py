#!/usr/bin/env python3
"""
EC業界日次情報レポート 自動生成スクリプト
毎日 23:00 UTC (翌08:00 JST) に GitHub Actions で実行される
"""

import os
import json
import base64
import urllib.request
import urllib.error
import urllib.parse
import time
import re
from datetime import datetime

# ── 環境変数 ────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
GH_PAT            = os.environ.get("GH_PAT", "")
CHATWORK_TOKEN    = os.environ.get("CHATWORK_TOKEN", "")
CHATWORK_ROOM_ID  = os.environ.get("CHATWORK_ROOM_ID", "")

GH_OWNER = "M-hirasawa95"
GH_REPO  = "ec-report"
GH_FILE  = "index.html"
GH_BRANCH = "main"


# ── 1. JST 日付取得 ──────────────────────────────────────────
def get_jst_date() -> str:
    """timeapi.io から JST 日付を取得して返す (YYYY-MM-DD)"""
    try:
        url = "https://timeapi.io/api/time/current/zone?timeZone=Asia%2FTokyo"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        return f"{data['year']:04d}-{data['month']:02d}-{data['day']:02d}"
    except Exception as e:
        print(f"[WARN] timeapi.io 失敗: {e} → システム時刻フォールバック")
        # UTC+9 offset
        ts = time.time() + 9 * 3600
        dt = datetime.utcfromtimestamp(ts)
        return dt.strftime("%Y-%m-%d")


# ── 2. DuckDuckGo でニュース収集 ────────────────────────────
def ddg_search(query: str, max_results: int = 5) -> list[dict]:
    """DuckDuckGo HTML 検索から snippet を取得"""
    results = []
    try:
        q = urllib.parse.quote_plus(query)
        url = f"https://html.duckduckgo.com/html/?q={q}"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64)",
                "Accept-Language": "ja,en;q=0.9",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        # タイトル・URL・スニペットを簡易抽出
        snippets = re.findall(
            r'class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL
        )
        titles = re.findall(r'class="result__a"[^>]*>(.*?)</a>', html, re.DOTALL)
        urls = re.findall(r'class="result__url"[^>]*>(.*?)</span>', html, re.DOTALL)

        for i in range(min(max_results, len(snippets))):
            title = re.sub(r"<[^>]+>", "", titles[i]).strip() if i < len(titles) else ""
            url_t = re.sub(r"<[^>]+>", "", urls[i]).strip() if i < len(urls) else ""
            snip  = re.sub(r"<[^>]+>", "", snippets[i]).strip()
            if snip:
                results.append({"title": title, "url": url_t, "snippet": snip})
    except Exception as e:
        print(f"[WARN] DuckDuckGo 検索失敗 ({query}): {e}")
    return results


def collect_news(date_str: str) -> dict:
    """各セクション向けのニュースを収集"""
    year, month, day = date_str.split("-")
    date_jp = f"{year}年{month}月{day}日"

    queries = {
        "ec_general":   f"EC eコマース ニュース {date_jp}",
        "amazon":       f"Amazon アマゾン 日本 {date_jp} ニュース",
        "rakuten":      f"楽天 EC ショッピング {date_jp}",
        "mercari":      f"メルカリ フリマ {date_jp}",
        "zozo":         f"ZOZO ゾゾタウン {date_jp}",
        "shopify":      f"Shopify ショッピファイ {date_jp}",
        "logistics":    f"物流 配送 EC {date_jp}",
        "payment":      f"決済 フィンテック EC {date_jp}",
        "ai_seo":       f"AI SEO EC マーケティング {date_jp}",
        "tiktok":       f"TikTok バイラル 商品 トレンド {date_jp}",
        "campaign":     f"EC キャンペーン セール {date_jp}",
        "ir":           f"楽天 Amazon メルカリ ZOZO 決算 IR {year}年",
        "cybear":       f"サイバーエージェント AbemaTV Ameba EC {date_jp}",
        "ad_roas":      f"EC 広告 ROAS リターン {date_jp}",
    }

    news = {}
    for key, query in queries.items():
        print(f"  🔍 {key}: {query[:40]}...")
        results = ddg_search(query, max_results=4)
        news[key] = results
        time.sleep(0.5)

    return news


# ── 3. Claude API でHTML生成 ─────────────────────────────────
def call_claude(prompt: str, max_tokens: int = 8000) -> str:
    """Anthropic Messages API を直接呼び出す"""
    url = "https://api.anthropic.com/v1/messages"
    payload = json.dumps({
        "model": "claude-3-5-sonnet-20241022",
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode())
    return data["content"][0]["text"]


def build_news_context(news: dict) -> str:
    """収集ニュースを Claude プロンプト用テキストに変換"""
    lines = []
    for key, items in news.items():
        lines.append(f"\n### {key}")
        for item in items:
            lines.append(f"- {item['title']}: {item['snippet'][:200]} [{item['url']}]")
    return "\n".join(lines)


SYSTEM_STYLE = """
デザイン仕様:
- フォント: Noto Sans JP (Google Fonts)
- 背景色: #1A1D23（ほぼ黒）
- アクセント: #2B5CE6（青）
- セクション境界線: rgba(43,92,230,0.3)
- テキスト色: #E2E8F0（明るいグレー）
- サイバーレコードセクション背景: #0F172A（ダークネイビー）
- アコーディオン式UI（クリックで展開）
- レスポンシブ対応
- Chart.js でIRダッシュボード棒グラフ2つ（売上高・成長率）
"""

IR_COMPANIES = """
IR対象12社: 楽天グループ、Amazon、メルカリ、ZOZO、サイバーエージェント、
BASE、Shopify、LINEヤフー、アンドエスティHD（旧アダストリア、2025年9月社名変更）、
オイシックス、スクロール、Qoo10/eBay Japan
"""


def generate_html(date_str: str, news: dict) -> str:
    """3分割でHTML生成して結合"""
    year, month, day = date_str.split("-")
    date_jp = f"{year}年{month}月{day}日"
    news_ctx = build_news_context(news)

    # ── Part1: ヘッダー〜IRダッシュボード ──────────────────
    print("  🤖 Part1 生成中...")
    prompt1 = f"""
あなたはEC業界専門のアナリストです。
以下の収集ニュースを参考に、{date_jp} 付けのEC業界日次情報レポートのHTMLを生成してください。

{SYSTEM_STYLE}

【収集ニュース】
{news_ctx}

{IR_COMPANIES}

以下のHTML（Part1: 冒頭〜IRダッシュボードまで）を生成してください。
必ず <!DOCTYPE html> から始めて、</body></html> は含めないこと（Part3で閉じる）。

含めるセクション（この順番で）:
1. ヘッダー: タイトル「EC業界日次情報レポート」、日付「{date_jp}」、サブタイトル
2. 本日のサマリー（Today's Highlights）: 箇条書き5〜8項目、重要ニュースを凝縮
3. 📈 IRダッシュボード: {IR_COMPANIES}の12社について最新の決算・株価情報をテーブル＋Chart.js棒グラフ2つ（売上高・成長率）。グラフはcanvasで実装。
4. 🛒 Amazon最新動向: 収集ニュース参照、ソースURLリンク付き
5. 🎯 楽天グループ動向: 収集ニュース参照、ソースURLリンク付き

アコーディオン式（<details><summary>）を使用。
各ニュース項目には出典URLを [ソース](url) 形式で付与。

HTMLのみ出力（説明文・コードブロックマーカー不要）。
"""
    part1 = call_claude(prompt1, max_tokens=8000)

    # ── Part2: ECプラットフォーム〜AI/SEO ─────────────────
    print("  🤖 Part2 生成中...")
    prompt2 = f"""
EC業界日次情報レポート {date_jp} のHTMLのPart2を生成します。
HTMLタグは開かず、セクションの<section>タグから始めてください（Part1に続けて結合します）。

{SYSTEM_STYLE}

【収集ニュース】
{news_ctx}

含めるセクション:
6. 💜 メルカリ・フリマ市場: 収集ニュース参照
7. 👗 ZOZO・ファッションEC: 収集ニュース参照
8. 🏪 その他ECプラットフォーム（BASE/Shopify/Qoo10等）: 収集ニュース参照
9. 🤖 AI・SEOトレンド: EC×AIの最新動向、収集ニュース参照
10. 🎵 TikTokバイラル商品トレンド: 収集ニュース参照、今話題の商品・ハッシュタグ

各セクションはアコーディオン式（<details><summary>）。
ニュース項目に出典URLを付与。

HTMLセクションのみ出力（説明文不要）。
"""
    part2 = call_claude(prompt2, max_tokens=8000)

    # ── Part3: 物流〜フッター ──────────────────────────────
    print("  🤖 Part3 生成中...")
    prompt3 = f"""
EC業界日次情報レポート {date_jp} のHTMLのPart3（最終部分）を生成します。
セクションの<section>タグから始め、最後は </body></html> で閉じてください。

{SYSTEM_STYLE}

【収集ニュース】
{news_ctx}

含めるセクション:
11. 🚚 物流・フルフィルメント: 収集ニュース参照
12. 💳 決済・フィンテック: 収集ニュース参照
13. 📅 ECキャンペーンカレンダー（今後約5週間）: 主要セール・イベント日程一覧テーブル
14. 📊 広告ROASベンチマーク: EC広告のROAS目安・業種別比較テーブル

フッター:
- 「本レポートは自動生成です。情報の正確性は保証しません。」
- 生成日時: {date_jp}

各セクションはアコーディオン式（<details><summary>）。
ニュース項目に出典URLを付与。
最後に </body></html> を含めること。

HTMLのみ出力（説明文不要）。
"""
    part3 = call_claude(prompt3, max_tokens=8000)

    # ── 結合 ───────────────────────────────────────────────
    html = part1 + "\n" + part2 + "\n" + part3
    return html


# ── 4. GitHub へ push ────────────────────────────────────────
def get_file_sha() -> str | None:
    """現在の index.html の SHA を取得"""
    url = f"https://api.github.com/repos/{GH_OWNER}/{GH_REPO}/contents/{GH_FILE}?ref={GH_BRANCH}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"token {GH_PAT}",
            "Accept": "application/vnd.github.v3+json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        return data.get("sha")
    except Exception:
        return None


def push_to_github(html: str, date_str: str) -> str:
    """index.html を GitHub に push して commit SHA を返す"""
    sha = get_file_sha()
    content_b64 = base64.b64encode(html.encode()).decode()

    payload = {
        "message": f"Daily EC report {date_str}",
        "content": content_b64,
        "branch": GH_BRANCH,
    }
    if sha:
        payload["sha"] = sha

    url = f"https://api.github.com/repos/{GH_OWNER}/{GH_REPO}/contents/{GH_FILE}"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"token {GH_PAT}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
        },
        method="PUT",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())
    return data["commit"]["sha"]


# ── 5. Chatwork 通知 ─────────────────────────────────────────
def notify_chatwork(date_str: str, commit_sha: str):
    """Chatwork に [toall] で配信通知"""
    url_report = f"https://{GH_OWNER.lower()}.github.io/{GH_REPO}/"
    year, month, day = date_str.split("-")
    msg = (
        f"[toall]\n"
        f"【EC業界日次情報レポート {year}年{month}月{day}日版】を公開しました。\n\n"
        f"▼ レポートはこちら\n{url_report}\n\n"
        f"commit: {commit_sha[:7]}\n"
        f"本レポートは自動生成です。"
    )
    url = f"https://api.chatwork.com/v2/rooms/{CHATWORK_ROOM_ID}/messages"
    data = urllib.parse.urlencode({"body": msg}).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "X-ChatWorkToken": CHATWORK_TOKEN,
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        result = json.loads(resp.read().decode())
    return result.get("message_id")


# ── メイン ───────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("EC業界日次情報レポート 自動生成開始")
    print("=" * 60)

    # 1. 日付取得
    print("\n[1/5] JST日付取得...")
    date_str = get_jst_date()
    print(f"  → {date_str}")

    # 2. ニュース収集
    print("\n[2/5] ニュース収集...")
    news = collect_news(date_str)
    total = sum(len(v) for v in news.values())
    print(f"  → {total}件取得")

    # 3. HTML生成
    print("\n[3/5] HTML生成（3分割）...")
    html = generate_html(date_str, news)
    print(f"  → {len(html):,} bytes")

    # 4. GitHub push
    print("\n[4/5] GitHub push...")
    commit_sha = push_to_github(html, date_str)
    print(f"  → commit: {commit_sha[:12]}")

    # 5. Chatwork通知
    print("\n[5/5] Chatwork通知...")
    message_id = notify_chatwork(date_str, commit_sha)
    print(f"  → message_id: {message_id}")

    print("\n✅ 完了!")
    print(f"   レポートURL: https://m-hirasawa95.github.io/ec-report/")
    print(f"   commit SHA: {commit_sha[:12]}")
    print(f"   Chatwork message_id: {message_id}")


if __name__ == "__main__":
    main()
