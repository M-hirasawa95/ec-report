#!/usr/bin/env python3
"""
EC業界日次情報レポート 自動生成スクリプト
毎日 23:00 UTC (翌08:00 JST) に GitHub Actions で実行される
Google Gemini API 使用（無料枠）
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
GEMINI_API_KEY  = os.environ.get("GEMINI_API_KEY", "")
GH_PAT          = os.environ.get("GH_PAT", "")
CHATWORK_TOKEN  = os.environ.get("CHATWORK_TOKEN", "")
CHATWORK_ROOM_ID = os.environ.get("CHATWORK_ROOM_ID", "")

GH_OWNER  = "M-hirasawa95"
GH_REPO   = "ec-report"
GH_FILE   = "index.html"
GH_BRANCH = "main"

GEMINI_MODEL = "gemini-2.5-flash-lite"


# ── 1. JST 日付取得 ──────────────────────────────────────────
def get_jst_date() -> str:
    try:
        url = "https://timeapi.io/api/time/current/zone?timeZone=Asia%2FTokyo"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        return f"{data['year']:04d}-{data['month']:02d}-{data['day']:02d}"
    except Exception as e:
        print(f"[WARN] timeapi.io 失敗: {e} → UTC+9フォールバック")
        ts = time.time() + 9 * 3600
        dt = datetime.utcfromtimestamp(ts)
        return dt.strftime("%Y-%m-%d")


# ── 2. DuckDuckGo でニュース収集 ────────────────────────────
def ddg_search(query: str, max_results: int = 5) -> list[dict]:
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

        snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)
        titles   = re.findall(r'class="result__a"[^>]*>(.*?)</a>', html, re.DOTALL)
        urls     = re.findall(r'class="result__url"[^>]*>(.*?)</span>', html, re.DOTALL)

        for i in range(min(max_results, len(snippets))):
            title = re.sub(r"<[^>]+>", "", titles[i]).strip() if i < len(titles) else ""
            url_t = re.sub(r"<[^>]+>", "", urls[i]).strip() if i < len(urls) else ""
            snip  = re.sub(r"<[^>]+>", "", snippets[i]).strip()
            if snip:
                results.append({"title": title, "url": url_t, "snippet": snip})
    except Exception as e:
        print(f"[WARN] DuckDuckGo検索失敗 ({query[:30]}): {e}")
    return results


def collect_news(date_str: str) -> dict:
    year, month, day = date_str.split("-")
    date_jp = f"{year}年{month}月{day}日"

    queries = {
        "ec_general": f"EC eコマース ニュース {date_jp}",
        "amazon":     f"Amazon アマゾン 日本 {date_jp} ニュース",
        "rakuten":    f"楽天 EC ショッピング {date_jp}",
        "mercari":    f"メルカリ フリマ {date_jp}",
        "zozo":       f"ZOZO ゾゾタウン {date_jp}",
        "shopify":    f"Shopify ショッピファイ {date_jp}",
        "logistics":  f"物流 配送 EC {date_jp}",
        "payment":    f"決済 フィンテック EC {date_jp}",
        "ai_seo":     f"AI SEO EC マーケティング {date_jp}",
        "tiktok":     f"TikTok バイラル 商品 トレンド {date_jp}",
        "campaign":   f"EC キャンペーン セール {date_jp}",
        "ir":         f"楽天 Amazon メルカリ ZOZO 決算 IR {year}年",
        "ad_roas":    f"EC 広告 ROAS {date_jp}",
    }

    news = {}
    for key, query in queries.items():
        print(f"  🔍 {key}: {query[:40]}...")
        results = ddg_search(query, max_results=4)
        news[key] = results
        time.sleep(0.5)
    return news


# ── 3. Gemini API でHTML生成 ─────────────────────────────────
def call_gemini(prompt: str) -> str:
    api_key = GEMINI_API_KEY or os.environ.get("GOOGLE_API_KEY", "")
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={api_key}"
    )
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "maxOutputTokens": 8192,
            "temperature": 0.7,
        },
    }).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode())
    return data["candidates"][0]["content"]["parts"][0]["text"]


def build_news_context(news: dict) -> str:
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
- アコーディオン式UI（<details><summary>タグ使用）
- レスポンシブ対応
- Chart.js でIRダッシュボード棒グラフ2つ（売上高・成長率）
"""

IR_COMPANIES = """
IR対象12社: 楽天グループ、Amazon、メルカリ、ZOZO、サイバーエージェント、
BASE、Shopify、LINEヤフー、アンドエスティHD（旧アダストリア、2025年9月社名変更）、
オイシックス、スクロール、Qoo10/eBay Japan
"""


def generate_html(date_str: str, news: dict) -> str:
    year, month, day = date_str.split("-")
    date_jp = f"{year}年{month}月{day}日"
    news_ctx = build_news_context(news)

    # ── Part1 ──────────────────────────────────────────────
    print("  🤖 Part1 生成中...")
    prompt1 = f"""
あなたはEC業界専門のアナリストです。
{date_jp} 付けのEC業界日次情報レポートのHTMLを生成してください。

{SYSTEM_STYLE}

【収集ニュース】
{news_ctx}

{IR_COMPANIES}

以下のHTML（Part1）を生成してください。
必ず <!DOCTYPE html> から始めて、</body></html> は含めないこと（後で追加します）。

含めるセクション:
1. ヘッダー: タイトル「EC業界日次情報レポート」、日付「{date_jp}」
2. 本日のサマリー（Today's Highlights）: 箇条書き5〜8項目
3. 📈 IRダッシュボード: {IR_COMPANIES}の12社の最新決算・株価テーブル＋Chart.js棒グラフ2つ（売上高・成長率）
4. 🛒 Amazon最新動向: ソースURLリンク付き
5. 🎯 楽天グループ動向: ソースURLリンク付き

HTMLのみ出力（説明文・コードブロック記号```不要）。
"""
    part1 = call_gemini(prompt1)
    part1 = re.sub(r"^```html?\n?", "", part1.strip())
    part1 = re.sub(r"\n?```$", "", part1.strip())
    time.sleep(2)  # レート制限対策

    # ── Part2 ──────────────────────────────────────────────
    print("  🤖 Part2 生成中...")
    prompt2 = f"""
EC業界日次情報レポート {date_jp} のHTMLのPart2を生成します。
<section>タグから始めてください（前後のHTMLタグは不要）。

{SYSTEM_STYLE}

【収集ニュース】
{news_ctx}

含めるセクション:
6. 💜 メルカリ・フリマ市場
7. 👗 ZOZO・ファッションEC
8. 🏪 その他ECプラットフォーム（BASE/Shopify/Qoo10等）
9. 🤖 AI・SEOトレンド
10. 🎵 TikTokバイラル商品トレンド

各セクションは<details><summary>のアコーディオン式。ニュース項目に出典URLリンク付与。
HTMLセクションのみ出力（```記号不要）。
"""
    part2 = call_gemini(prompt2)
    part2 = re.sub(r"^```html?\n?", "", part2.strip())
    part2 = re.sub(r"\n?```$", "", part2.strip())
    time.sleep(2)

    # ── Part3 ──────────────────────────────────────────────
    print("  🤖 Part3 生成中...")
    prompt3 = f"""
EC業界日次情報レポート {date_jp} のHTMLのPart3（最終部分）を生成します。
<section>タグから始め、最後は</body></html>で閉じてください。

{SYSTEM_STYLE}

【収集ニュース】
{news_ctx}

含めるセクション:
11. 🚚 物流・フルフィルメント
12. 💳 決済・フィンテック
13. 📅 ECキャンペーンカレンダー（今後約5週間の主要セール・イベント一覧テーブル）
14. 📊 広告ROASベンチマーク（EC広告のROAS目安・業種別比較テーブル）

フッター:「本レポートは自動生成です。情報の正確性は保証しません。」生成日時: {date_jp}

各セクションは<details><summary>アコーディオン式。ニュース項目に出典URLリンク付与。
最後に</body></html>を含めること。HTMLのみ出力（```記号不要）。
"""
    part3 = call_gemini(prompt3)
    part3 = re.sub(r"^```html?\n?", "", part3.strip())
    part3 = re.sub(r"\n?```$", "", part3.strip())

    return part1 + "\n" + part2 + "\n" + part3


# ── 4. GitHub へ push ────────────────────────────────────────
def get_file_sha() -> str | None:
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
    print("EC業界日次情報レポート 自動生成開始（Gemini API）")
    print("=" * 60)

    print("\n[1/5] JST日付取得...")
    date_str = get_jst_date()
    print(f"  → {date_str}")

    print("\n[2/5] ニュース収集...")
    news = collect_news(date_str)
    total = sum(len(v) for v in news.values())
    print(f"  → {total}件取得")

    print("\n[3/5] HTML生成（Gemini・3分割）...")
    html = generate_html(date_str, news)
    print(f"  → {len(html):,} bytes")

    print("\n[4/5] GitHub push...")
    commit_sha = push_to_github(html, date_str)
    print(f"  → commit: {commit_sha[:12]}")

    print("\n[5/5] Chatwork通知...")
    message_id = notify_chatwork(date_str, commit_sha)
    print(f"  → message_id: {message_id}")

    print("\n✅ 完了!")
    print(f"   レポートURL: https://m-hirasawa95.github.io/ec-report/")
    print(f"   commit SHA: {commit_sha[:12]}")
    print(f"   Chatwork message_id: {message_id}")


if __name__ == "__main__":
    main()
