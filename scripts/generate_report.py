#!/usr/bin/env python3
"""
EC業界ダッシュボード 自動生成スクリプト
毎日 23:00 UTC (翌08:00 JST) に GitHub Actions で実行
Gemini REST API（SDKなし）+ GitHub Pages
"""

import os, json, base64, urllib.request, urllib.error, urllib.parse, time, re
from datetime import datetime

# ── 環境変数 ────────────────────────────────────────────────────
GEMINI_API_KEY   = os.environ.get("GEMINI_API_KEY", "")
GH_PAT           = os.environ.get("GH_PAT", "")
CHATWORK_TOKEN   = os.environ.get("CHATWORK_TOKEN", "")
CHATWORK_ROOM_ID = os.environ.get("CHATWORK_ROOM_ID", "")
CHATWORK_ENABLED = os.environ.get("CHATWORK_ENABLED", "false").lower() == "true"

GH_OWNER  = "M-hirasawa95"
GH_REPO   = "ec-report"
GH_FILE   = "index.html"
GH_BRANCH = "main"
GEMINI_MODEL = "gemini-2.5-flash-lite"

# ── カテゴリ定義 ─────────────────────────────────────────────────
CATEGORIES = [
    {
        "id": "breaking",
        "icon": "🚨",
        "title": "重要ニュース",
        "type": "breaking",
        "queries": [
            "EC eコマース 重要 大型発表 速報 {date}",
            "Amazon 楽天 メルカリ 重大発表 障害 {date}",
        ],
    },
    {
        "id": "ir",
        "icon": "📊",
        "title": "IR・決算情報",
        "type": "ir",
        "queries": [
            "楽天グループ Amazon メルカリ ZOZO BASE 決算 業績 {year}",
            "EC企業 株価 IR 決算発表 資金調達 {date}",
        ],
    },
    {
        "id": "platform",
        "icon": "🛒",
        "title": "プラットフォーム動向",
        "type": "accordion",
        "queries": [
            "Amazon 楽天 Yahoo 新機能 手数料 規約変更 {date}",
            "ECモール セール キャンペーン スーパーSALE {date}",
        ],
    },
    {
        "id": "ads",
        "icon": "📢",
        "title": "広告・マーケティング費用",
        "type": "accordion",
        "queries": [
            "EC広告 ROAS CPC CPM 相場 {date}",
            "Amazon広告 楽天広告 スポンサー広告 運用 {date}",
        ],
    },
    {
        "id": "logistics",
        "icon": "🚚",
        "title": "物流・フルフィルメント",
        "type": "accordion",
        "queries": [
            "物流 配送 EC 送料改定 ヤマト 佐川 {date}",
            "FBA 楽天物流 3PL フルフィルメント {date}",
        ],
    },
    {
        "id": "consumer",
        "icon": "👥",
        "title": "消費者トレンド",
        "type": "accordion",
        "queries": [
            "消費者 購買トレンド EC ランキング {date}",
            "TikTok バイラル 流行 商品 トレンド {date}",
        ],
    },
    {
        "id": "legal",
        "icon": "⚖️",
        "title": "法規制・業界ニュース",
        "type": "accordion",
        "queries": [
            "EC 景表法 特商法 規制 法改正 {date}",
            "個人情報 セキュリティ EC 不正アクセス {date}",
        ],
    },
    {
        "id": "competitor",
        "icon": "🏪",
        "title": "他社EC運営情報",
        "type": "accordion",
        "queries": [
            "EC 運営 成功事例 D2C ブランド 施策 {date}",
            "越境EC 海外展開 Temu Shein 事例 {date}",
        ],
    },
    {
        "id": "cart",
        "icon": "🖥️",
        "title": "ECカートシステム",
        "type": "accordion",
        "queries": [
            "Shopify MakeShop カラーミー BASE STORES futureshop アップデート {date}",
            "ECカート 新機能 乗り換え 比較 {date}",
        ],
    },
    {
        "id": "tools",
        "icon": "🔧",
        "title": "ECツール情報",
        "type": "accordion",
        "queries": [
            "EC ツール 新サービス MA CRM メール配信 リリース {date}",
            "EC在庫管理 分析 価格監視 AI ツール {date}",
        ],
    },
    {
        "id": "marketing",
        "icon": "📣",
        "title": "マーケティング全般",
        "type": "accordion",
        "queries": [
            "Google Meta LINE TikTok 広告 マーケティング アップデート {date}",
            "SEO コンテンツ AI マーケティング トレンド {date}",
        ],
    },
]

# ── CSS（Python固定・Gemini非生成）──────────────────────────────
CSS = """
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: 'Noto Sans JP', sans-serif;
      background: #F1F5F9;
      color: #1E293B;
      font-size: 14px;
      line-height: 1.6;
    }
    a { color: #2563EB; text-decoration: none; }
    a:hover { text-decoration: underline; }

    .header {
      background: linear-gradient(135deg, #1E40AF, #2563EB);
      color: white;
      position: sticky;
      top: 0;
      z-index: 100;
      box-shadow: 0 2px 8px rgba(0,0,0,0.15);
    }
    .header-inner {
      max-width: 1200px;
      margin: 0 auto;
      padding: 14px 24px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .header h1 { font-size: 20px; font-weight: 700; }
    .date-badge {
      background: rgba(255,255,255,0.25);
      padding: 4px 14px;
      border-radius: 20px;
      font-size: 13px;
      font-weight: 500;
    }

    .category-nav {
      background: white;
      border-bottom: 1px solid #E2E8F0;
      overflow-x: auto;
      white-space: nowrap;
      position: sticky;
      top: 52px;
      z-index: 99;
      box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .category-nav-inner {
      max-width: 1200px;
      margin: 0 auto;
      padding: 0 24px;
      display: flex;
    }
    .nav-link {
      display: inline-block;
      padding: 10px 12px;
      text-decoration: none !important;
      color: #64748B;
      font-size: 12px;
      font-weight: 500;
      border-bottom: 2px solid transparent;
      transition: all 0.2s;
    }
    .nav-link:hover { color: #2563EB; border-bottom-color: #2563EB; }

    .container { max-width: 1200px; margin: 0 auto; padding: 24px; }

    .section-card {
      background: white;
      border-radius: 12px;
      border: 1px solid #E2E8F0;
      margin-bottom: 20px;
      overflow: hidden;
      box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    }
    .section-header {
      padding: 14px 20px;
      border-bottom: 1px solid #E2E8F0;
      background: #F8FAFC;
    }
    .section-title { font-size: 15px; font-weight: 700; color: #1E293B; }
    .section-body { padding: 20px; }

    .highlight-section {
      background: #EFF6FF;
      border: 1px solid #BFDBFE;
      border-radius: 8px;
      padding: 16px 20px;
    }
    .highlight-title { font-weight: 700; color: #1D4ED8; margin-bottom: 12px; font-size: 14px; }
    .highlight-list {
      list-style: none;
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px 32px;
    }
    .highlight-list li {
      color: #1E293B;
      font-size: 13px;
      padding-left: 16px;
      position: relative;
      line-height: 1.5;
    }
    .highlight-list li::before {
      content: '▸';
      position: absolute;
      left: 0;
      color: #2563EB;
      font-size: 10px;
      top: 3px;
    }

    .breaking-card { border-top: 3px solid #EF4444; }
    .breaking-card .section-header { background: #FFF5F5; }
    .breaking-card .section-title { color: #DC2626; }

    .news-list { list-style: none; }
    .news-item {
      padding: 10px 0;
      border-bottom: 1px solid #F1F5F9;
      display: flex;
      gap: 10px;
      align-items: flex-start;
    }
    .news-item:last-child { border-bottom: none; }
    .news-bullet { color: #2563EB; font-size: 10px; flex-shrink: 0; margin-top: 4px; }
    .news-content { flex: 1; min-width: 0; }
    .news-title { font-weight: 600; color: #1E293B; margin-bottom: 3px; font-size: 13px; }
    .news-snippet { color: #64748B; font-size: 12px; line-height: 1.6; }
    .news-source { color: #94A3B8; font-size: 11px; margin-top: 3px; }

    details summary {
      list-style: none;
      cursor: pointer;
      padding: 12px 20px;
      border-bottom: 1px solid #E2E8F0;
      display: flex;
      align-items: center;
      justify-content: space-between;
      background: #F8FAFC;
      user-select: none;
    }
    details summary::-webkit-details-marker { display: none; }
    .summary-label { color: #475569; font-size: 13px; }
    .toggle-icon { color: #94A3B8; transition: transform 0.2s; font-size: 12px; }
    details[open] .toggle-icon { transform: rotate(180deg); }
    .details-body { padding: 20px; }

    .ir-charts { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px; }
    .chart-box {
      position: relative;
      height: 240px;
      padding: 10px;
      border: 1px solid #E2E8F0;
      border-radius: 8px;
      background: #FAFAFA;
    }
    .ir-table { width: 100%; border-collapse: collapse; font-size: 12px; }
    .ir-table th {
      background: #F8FAFC;
      padding: 8px 10px;
      text-align: left;
      font-weight: 600;
      border-bottom: 2px solid #E2E8F0;
      color: #475569;
      white-space: nowrap;
    }
    .ir-table td { padding: 8px 10px; border-bottom: 1px solid #F1F5F9; }
    .ir-table tr:hover td { background: #F8FAFC; }
    .tag-up { color: #059669; font-weight: 600; }
    .tag-down { color: #DC2626; font-weight: 600; }
    .tag-neutral { color: #64748B; }

    .footer {
      background: #1E293B;
      color: #94A3B8;
      text-align: center;
      padding: 20px;
      font-size: 12px;
      margin-top: 24px;
      line-height: 2;
    }

    @media (max-width: 768px) {
      .container { padding: 16px; }
      .header-inner { flex-wrap: wrap; gap: 8px; }
      .header h1 { font-size: 16px; }
      .ir-charts { grid-template-columns: 1fr; }
      .highlight-list { grid-template-columns: 1fr; }
      .category-nav { position: relative; top: auto; }
    }
"""

HTML_CLASS_GUIDE = """
【使用するHTMLクラス構造】

通常セクション(type=accordion):
<section id="{cat_id}" class="section-card">
  <div class="section-header"><span class="section-title">{icon} {title}</span></div>
  <details open>
    <summary><span class="summary-label">ニュース一覧</span><span class="toggle-icon">▼</span></summary>
    <div class="details-body">
      <ul class="news-list">
        <li class="news-item">
          <span class="news-bullet">▸</span>
          <div class="news-content">
            <div class="news-title">タイトル</div>
            <div class="news-snippet">詳細内容</div>
            <div class="news-source"><a href="URL">出典</a></div>
          </div>
        </li>
      </ul>
    </div>
  </details>
</section>

重要ニュース(type=breaking):
<section id="breaking" class="section-card breaking-card">
  <div class="section-header"><span class="section-title">🚨 重要ニュース</span></div>
  <div class="section-body">
    <ul class="news-list">（ニュースアイテム）</ul>
  </div>
</section>

IRセクション(type=ir):
<section id="ir" class="section-card">
  <div class="section-header"><span class="section-title">📊 IR・決算情報</span></div>
  <div class="section-body">
    <div class="ir-charts">
      <div class="chart-box"><canvas id="revenueChart"></canvas></div>
      <div class="chart-box"><canvas id="growthChart"></canvas></div>
    </div>
    <table class="ir-table">
      <thead><tr><th>企業</th><th>最新売上</th><th>前年比</th><th>注目ポイント</th></tr></thead>
      <tbody>...</tbody>
    </table>
    <ul class="news-list">（IRニュース）</ul>
    <script>/* Chart.js初期化 */</script>
  </div>
</section>
"""


# ── 1. JST日付取得 ────────────────────────────────────────────
def get_jst_date() -> str:
    try:
        url = "https://timeapi.io/api/time/current/zone?timeZone=Asia%2FTokyo"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        return f"{data['year']:04d}-{data['month']:02d}-{data['day']:02d}"
    except Exception as e:
        print(f"[WARN] timeapi.io失敗: {e}")
        ts = time.time() + 9 * 3600
        return datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")


# ── 2. ニュース収集 ────────────────────────────────────────────
def ddg_search(query: str, max_results: int = 4) -> list[dict]:
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
            html_content = resp.read().decode("utf-8", errors="replace")

        snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html_content, re.DOTALL)
        titles   = re.findall(r'class="result__a"[^>]*>(.*?)</a>', html_content, re.DOTALL)
        urls     = re.findall(r'class="result__url"[^>]*>(.*?)</span>', html_content, re.DOTALL)

        for i in range(min(max_results, len(snippets))):
            title = re.sub(r"<[^>]+>", "", titles[i]).strip() if i < len(titles) else ""
            url_t = re.sub(r"<[^>]+>", "", urls[i]).strip() if i < len(urls) else ""
            snip  = re.sub(r"<[^>]+>", "", snippets[i]).strip()
            if snip:
                results.append({"title": title, "url": url_t, "snippet": snip})
    except Exception as e:
        print(f"[WARN] DuckDuckGo検索失敗 ({query[:30]}): {e}")
    return results


def collect_all_news(date_str: str) -> dict:
    year, month, day = date_str.split("-")
    date_jp = f"{year}年{month}月{day}日"
    news = {}
    for cat in CATEGORIES:
        cat_id = cat["id"]
        news[cat_id] = []
        for query_tmpl in cat["queries"]:
            query = query_tmpl.format(date=date_jp, year=f"{year}年")
            print(f"  🔍 [{cat_id}] {query[:50]}...")
            results = ddg_search(query, max_results=4)
            news[cat_id].extend(results)
            time.sleep(0.5)
    return news


# ── 3. Gemini API ─────────────────────────────────────────────
def call_gemini(prompt: str, retries: int = 3) -> str:
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    )
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 8192, "temperature": 0.7},
    }).encode()

    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url, data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode())
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries - 1:
                wait = 30 * (attempt + 1)
                print(f"  [WARN] レート制限 → {wait}秒待機...")
                time.sleep(wait)
            else:
                raise


def clean_output(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```html?\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    return text.strip()


# ── 4. HTML生成 ───────────────────────────────────────────────
def build_news_context(cat_id: str, news: dict, max_items: int = 6) -> str:
    items = news.get(cat_id, [])[:max_items]
    if not items:
        return "（ニュースなし）"
    lines = []
    for item in items:
        lines.append(f"- タイトル: {item['title']}")
        lines.append(f"  内容: {item['snippet'][:200]}")
        lines.append(f"  URL: {item['url']}")
    return "\n".join(lines)


def generate_summary_section(news: dict, date_jp: str) -> str:
    top_snippets = []
    for cat in CATEGORIES:
        items = news.get(cat["id"], [])
        if items:
            top_snippets.append(f"[{cat['title']}] {items[0]['snippet'][:80]}")

    prompt = f"""EC業界ダッシュボード {date_jp} の「本日のハイライト」セクションのHTMLを生成してください。

【ニュースサマリー】
{chr(10).join(top_snippets)}

以下の構造で出力してください:
<section id="summary" class="section-card">
  <div class="section-header"><span class="section-title">✨ 本日のハイライト</span></div>
  <div class="section-body">
    <div class="highlight-section">
      <div class="highlight-title">📋 {date_jp} EC業界トピックス</div>
      <ul class="highlight-list">
        <li>（ハイライト項目）</li>
      </ul>
    </div>
  </div>
</section>

重要ポイントを6〜8項目、各40文字以内で簡潔にまとめてください。
コードブロック記号```は不要。<section>タグのみ出力。"""

    return clean_output(call_gemini(prompt))


def generate_sections_batch(categories_batch: list, news: dict, date_jp: str) -> str:
    news_parts = []
    for cat in categories_batch:
        ctx = build_news_context(cat["id"], news)
        news_parts.append(
            f"\n=== {cat['icon']} {cat['title']} (id={cat['id']}, type={cat['type']}) ===\n{ctx}"
        )

    sections_desc = "\n".join(
        f"  - {cat['icon']} {cat['title']} / id={cat['id']} / type={cat['type']}"
        for cat in categories_batch
    )

    ir_extra = ""
    if any(cat["id"] == "ir" for cat in categories_batch):
        ir_extra = """
IRセクション追加指示:
- ir-chartsにChart.js棒グラフを2つ（revenueChart: 売上高, growthChart: 成長率）
- セクション内に<script>タグでChart.js初期化コードを含める
- ニュースデータから数値を推測（不明は0）
- ir-tableで企業別テーブルも表示（企業名・最新売上・前年比・注目ポイント）
"""

    prompt = f"""EC業界ダッシュボード {date_jp} のHTMLセクション群を生成してください。

{HTML_CLASS_GUIDE}

【生成するセクション（順番通り）】
{sections_desc}
{ir_extra}
【収集ニュースデータ】
{"".join(news_parts)}

【出力ルール】
- 各セクションを<section>タグで生成（<!DOCTYPE html>等は不要）
- ニュース項目はURLをそのまま<a href>に使用
- 内容は具体的に日本語で記述
- コードブロック記号```は絶対に使わない
- 最初の文字は必ず<section で始める
"""
    return clean_output(call_gemini(prompt))


def build_html_shell(date_str: str, body_content: str) -> str:
    year, month, day = date_str.split("-")
    date_jp = f"{year}年{month}月{day}日"

    nav_links = "\n      ".join(
        f'<a href="#{cat["id"]}" class="nav-link">{cat["icon"]} {cat["title"]}</a>'
        for cat in CATEGORIES
    )

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>EC業界ダッシュボード - {date_jp}</title>
  <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700&display=swap" rel="stylesheet">
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
{CSS}
  </style>
</head>
<body>

<header class="header">
  <div class="header-inner">
    <h1>📈 EC業界ダッシュボード</h1>
    <span class="date-badge">{date_jp}</span>
  </div>
</header>

<nav class="category-nav">
  <div class="category-nav-inner">
    <a href="#summary" class="nav-link">✨ ハイライト</a>
    {nav_links}
  </div>
</nav>

<main class="container">
{body_content}
</main>

<footer class="footer">
  <p>本ダッシュボードは自動生成です。情報の正確性は保証しません。</p>
  <p>生成日時: {date_jp} ｜ Powered by Gemini API + DuckDuckGo</p>
</footer>

</body>
</html>"""


def generate_html(date_str: str, news: dict) -> str:
    year, month, day = date_str.split("-")
    date_jp = f"{year}年{month}月{day}日"
    sections = []

    print("  🤖 ハイライト生成中...")
    sections.append(generate_summary_section(news, date_jp))
    time.sleep(5)

    print("  🤖 Batch1: 重要ニュース・IR...")
    batch1 = [c for c in CATEGORIES if c["id"] in ("breaking", "ir")]
    sections.append(generate_sections_batch(batch1, news, date_jp))
    time.sleep(5)

    print("  🤖 Batch2: プラットフォーム〜消費者...")
    batch2 = [c for c in CATEGORIES if c["id"] in ("platform", "ads", "logistics", "consumer")]
    sections.append(generate_sections_batch(batch2, news, date_jp))
    time.sleep(5)

    print("  🤖 Batch3: 法規制〜マーケティング...")
    batch3 = [c for c in CATEGORIES if c["id"] in ("legal", "competitor", "cart", "tools", "marketing")]
    sections.append(generate_sections_batch(batch3, news, date_jp))

    return build_html_shell(date_str, "\n\n".join(sections))


# ── 5. GitHub Push ─────────────────────────────────────────────
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
        "message": f"Daily EC dashboard {date_str}",
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


# ── 6. Chatwork通知（承認後に有効化）────────────────────────────
def notify_chatwork(date_str: str, commit_sha: str):
    if not CHATWORK_ENABLED:
        print("  [SKIP] Chatwork通知は無効（CHATWORK_ENABLED=false）")
        return None
    url_report = f"https://{GH_OWNER.lower()}.github.io/{GH_REPO}/"
    year, month, day = date_str.split("-")
    msg = (
        f"[toall]\n"
        f"【EC業界ダッシュボード {year}年{month}月{day}日版】を公開しました。\n\n"
        f"▼ ダッシュボードはこちら\n{url_report}\n\n"
        f"commit: {commit_sha[:7]}\n"
        f"本ダッシュボードは自動生成です。"
    )
    url = f"https://api.chatwork.com/v2/rooms/{CHATWORK_ROOM_ID}/messages"
    data = urllib.parse.urlencode({"body": msg}).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={
            "X-ChatWorkToken": CHATWORK_TOKEN,
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        result = json.loads(resp.read().decode())
    return result.get("message_id")


# ── メイン ────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("EC業界ダッシュボード 自動生成開始")
    print("=" * 60)

    print("\n[1/5] JST日付取得...")
    date_str = get_jst_date()
    print(f"  → {date_str}")

    print("\n[2/5] ニュース収集（11カテゴリ）...")
    news = collect_all_news(date_str)
    total = sum(len(v) for v in news.values())
    print(f"  → {total}件取得")

    print("\n[3/5] HTML生成（Gemini・4分割）...")
    html = generate_html(date_str, news)
    print(f"  → {len(html):,} bytes")

    print("\n[4/5] GitHub push...")
    commit_sha = push_to_github(html, date_str)
    print(f"  → commit: {commit_sha[:12]}")

    print("\n[5/5] Chatwork通知...")
    notify_chatwork(date_str, commit_sha)

    print("\n✅ 完了!")
    print(f"   ダッシュボードURL: https://m-hirasawa95.github.io/ec-report/")
    print(f"   commit SHA: {commit_sha[:12]}")


if __name__ == "__main__":
    main()
