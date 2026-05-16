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
        "id": "breaking", "icon": "🚨", "title": "重要ニュース",
        "type": "breaking", "color": "#EF4444", "bg": "#FFF5F5",
        "queries": [
            "EC eコマース 重要ニュース 最新 {yearmonth}",
            "Amazon 楽天 メルカリ ZOZO 重大発表 最新 {year}",
        ],
    },
    {
        "id": "ir", "icon": "📊", "title": "IR・決算情報",
        "type": "ir", "color": "#2563EB", "bg": "#EFF6FF",
        "queries": [
            "楽天グループ Amazon メルカリ ZOZO BASE 決算 業績 売上 {year}",
            "EC企業 IR 決算発表 資金調達 株価 {yearmonth}",
        ],
    },
    {
        "id": "platform", "icon": "🛒", "title": "プラットフォーム動向",
        "type": "accordion", "color": "#7C3AED", "bg": "#F5F3FF",
        "queries": [
            "Amazon 楽天市場 Yahoo 手数料 規約変更 新機能 {yearmonth}",
            "ECモール セール キャンペーン スーパーSALE {yearmonth}",
        ],
    },
    {
        "id": "ads", "icon": "📢", "title": "広告・マーケティング費用",
        "type": "accordion", "color": "#D97706", "bg": "#FFFBEB",
        "queries": [
            "EC広告 ROAS CPC CPM 相場 最新 {year}",
            "Amazon広告 楽天広告 スポンサー 運用 事例 {yearmonth}",
        ],
    },
    {
        "id": "logistics", "icon": "🚚", "title": "物流・フルフィルメント",
        "type": "accordion", "color": "#059669", "bg": "#ECFDF5",
        "queries": [
            "EC 物流 配送 送料改定 ヤマト運輸 佐川急便 {yearmonth}",
            "FBA 楽天物流 3PL フルフィルメント 最新 {year}",
        ],
    },
    {
        "id": "consumer", "icon": "👥", "title": "消費者トレンド",
        "type": "accordion", "color": "#EC4899", "bg": "#FDF2F8",
        "queries": [
            "消費者 購買トレンド EC ランキング 人気 {yearmonth}",
            "TikTok バイラル 話題 商品 トレンド {yearmonth}",
        ],
    },
    {
        "id": "legal", "icon": "⚖️", "title": "法規制・業界ニュース",
        "type": "accordion", "color": "#6366F1", "bg": "#EEF2FF",
        "queries": [
            "EC 景表法 特商法 規制 法改正 {year}",
            "個人情報 セキュリティ EC 不正アクセス {yearmonth}",
        ],
    },
    {
        "id": "competitor", "icon": "🏪", "title": "他社EC運営情報",
        "type": "accordion", "color": "#0891B2", "bg": "#ECFEFF",
        "queries": [
            "EC 運営 成功事例 D2C ブランド 施策 {year}",
            "越境EC Temu Shein 日本 海外展開 {yearmonth}",
        ],
    },
    {
        "id": "cart", "icon": "🖥️", "title": "ECカートシステム",
        "type": "accordion", "color": "#8B5CF6", "bg": "#FAF5FF",
        "queries": [
            "Shopify MakeShop カラーミー BASE STORES futureshop 新機能 {yearmonth}",
            "ECカート 乗り換え 比較 費用 {year}",
        ],
    },
    {
        "id": "tools", "icon": "🔧", "title": "ECツール情報",
        "type": "accordion", "color": "#16A34A", "bg": "#F0FDF4",
        "queries": [
            "EC ツール 新サービス MA CRM メール配信 リリース {yearmonth}",
            "EC 在庫管理 分析 価格監視 AI 自動化 {year}",
        ],
    },
    {
        "id": "marketing", "icon": "📣", "title": "マーケティング全般",
        "type": "accordion", "color": "#EA580C", "bg": "#FFF7ED",
        "queries": [
            "Google Meta LINE TikTok 広告 マーケティング アップデート {yearmonth}",
            "SEO コンテンツ AI 生成AI マーケティング トレンド {year}",
        ],
    },
]

# ── CSS（Python固定定義）────────────────────────────────────────
CSS = """
    *, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; }
    :root {
      --radius: 16px;
      --shadow: 0 4px 24px rgba(0,0,0,0.07), 0 1px 4px rgba(0,0,0,0.04);
      --border: rgba(0,0,0,0.06);
    }
    body {
      font-family: 'Noto Sans JP', -apple-system, sans-serif;
      background: #F0F4FF;
      color: #0F172A;
      font-size: 14px;
      line-height: 1.65;
      -webkit-font-smoothing: antialiased;
    }
    a { color: inherit; text-decoration: none; }
    a:hover { opacity: 0.75; }

    /* ── カテゴリカラーマップ ── */
    [data-cat]              { --cc: #2563EB; --cb: #EFF6FF; }
    [data-cat="breaking"]   { --cc: #EF4444; --cb: #FFF5F5; }
    [data-cat="ir"]         { --cc: #2563EB; --cb: #EFF6FF; }
    [data-cat="platform"]   { --cc: #7C3AED; --cb: #F5F3FF; }
    [data-cat="ads"]        { --cc: #D97706; --cb: #FFFBEB; }
    [data-cat="logistics"]  { --cc: #059669; --cb: #ECFDF5; }
    [data-cat="consumer"]   { --cc: #EC4899; --cb: #FDF2F8; }
    [data-cat="legal"]      { --cc: #6366F1; --cb: #EEF2FF; }
    [data-cat="competitor"] { --cc: #0891B2; --cb: #ECFEFF; }
    [data-cat="cart"]       { --cc: #8B5CF6; --cb: #FAF5FF; }
    [data-cat="tools"]      { --cc: #16A34A; --cb: #F0FDF4; }
    [data-cat="marketing"]  { --cc: #EA580C; --cb: #FFF7ED; }

    /* ── ヘッダー ── */
    .header {
      background: linear-gradient(135deg, #0F172A 0%, #1E3A8A 100%);
      color: white;
      position: sticky; top: 0; z-index: 100;
      box-shadow: 0 4px 24px rgba(0,0,0,0.3);
    }
    .header-inner {
      max-width: 1200px; margin: 0 auto;
      padding: 16px 28px;
      display: flex; align-items: center; justify-content: space-between; gap: 16px;
    }
    .header-left { display: flex; align-items: center; gap: 12px; }
    .header-logo {
      width: 38px; height: 38px; border-radius: 10px;
      background: linear-gradient(135deg,#60A5FA,#2563EB);
      display: flex; align-items: center; justify-content: center;
      font-size: 20px;
    }
    .header h1 { font-size: 19px; font-weight: 800; letter-spacing: -0.3px; }
    .header-sub { font-size: 11px; color: rgba(255,255,255,0.5); margin-top: 1px; }
    .header-badge {
      background: rgba(255,255,255,0.12);
      border: 1px solid rgba(255,255,255,0.2);
      padding: 6px 16px; border-radius: 24px;
      font-size: 13px; font-weight: 600;
      display: flex; align-items: center; gap: 8px;
    }
    .live-dot {
      width: 7px; height: 7px; border-radius: 50%;
      background: #4ADE80;
      animation: blink 2s infinite;
    }
    @keyframes blink { 0%,100%{opacity:1} 50%{opacity:.3} }

    /* ── ナビゲーション ── */
    .category-nav {
      background: white;
      border-bottom: 1px solid var(--border);
      overflow-x: auto; white-space: nowrap;
      position: sticky; top: 58px; z-index: 99;
      box-shadow: 0 2px 8px rgba(0,0,0,0.04);
      scrollbar-width: none;
    }
    .category-nav::-webkit-scrollbar { display: none; }
    .category-nav-inner {
      max-width: 1200px; margin: 0 auto;
      padding: 8px 28px;
      display: flex; gap: 6px;
    }
    .nav-link {
      display: inline-flex; align-items: center; gap: 5px;
      padding: 6px 14px; border-radius: 24px;
      font-size: 12px; font-weight: 600;
      background: #F1F5F9; color: #64748B;
      transition: all .2s; white-space: nowrap;
    }
    .nav-link:hover { background: var(--cb,#EFF6FF); color: var(--cc,#2563EB); opacity:1; }

    /* ── コンテナ ── */
    .container { max-width: 1200px; margin: 0 auto; padding: 28px; }

    /* ── セクションカード ── */
    .section-card {
      background: white;
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      margin-bottom: 24px;
      overflow: hidden;
      border: 1px solid var(--border);
      border-left: 4px solid var(--cc, #2563EB);
    }
    .section-header {
      padding: 18px 24px;
      background: linear-gradient(120deg, var(--cb,#EFF6FF) 0%, rgba(255,255,255,0) 65%);
      border-bottom: 1px solid var(--border);
      display: flex; align-items: center; gap: 14px;
    }
    .cat-icon {
      width: 46px; height: 46px; border-radius: 13px;
      background: var(--cc,#2563EB);
      display: flex; align-items: center; justify-content: center;
      font-size: 22px; flex-shrink: 0;
      box-shadow: 0 4px 12px color-mix(in srgb, var(--cc,#2563EB) 30%, transparent);
    }
    .section-title-wrap { flex: 1; }
    .section-title { font-size: 16px; font-weight: 800; color: #0F172A; }
    .section-sub { font-size: 11px; color: #94A3B8; margin-top: 2px; }
    .section-badge {
      background: var(--cc,#2563EB); color: white;
      padding: 3px 12px; border-radius: 20px;
      font-size: 11px; font-weight: 700; flex-shrink: 0;
    }
    .section-body { padding: 20px 24px; }

    /* ── ニュースアイテム ── */
    .news-list { list-style: none; }
    .news-item {
      display: flex; gap: 14px;
      padding: 14px 0;
      border-bottom: 1px solid #F8FAFC;
      align-items: flex-start;
    }
    .news-item:last-child { border-bottom: none; padding-bottom: 0; }
    .news-num {
      min-width: 28px; height: 28px; border-radius: 8px;
      background: var(--cc,#2563EB); color: white;
      font-size: 11px; font-weight: 800;
      display: flex; align-items: center; justify-content: center;
      flex-shrink: 0; margin-top: 1px;
    }
    .news-content { flex: 1; min-width: 0; }
    .news-title { font-weight: 700; color: #0F172A; font-size: 13px; line-height: 1.5; margin-bottom: 4px; }
    .news-snippet { color: #64748B; font-size: 12px; line-height: 1.65; margin-bottom: 7px; }
    .news-meta { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
    .news-source {
      background: #F1F5F9; color: #64748B;
      padding: 2px 9px; border-radius: 5px;
      font-size: 10px; font-weight: 600;
    }
    .news-tag {
      background: var(--cb,#EFF6FF); color: var(--cc,#2563EB);
      padding: 2px 9px; border-radius: 5px;
      font-size: 10px; font-weight: 600;
    }

    /* ── アコーディオン ── */
    details summary {
      list-style: none; cursor: pointer;
      padding: 14px 24px;
      display: flex; align-items: center; justify-content: space-between;
      border-bottom: 1px solid var(--border);
      background: #FAFBFF; user-select: none;
    }
    details summary::-webkit-details-marker { display: none; }
    .summary-label { color: #64748B; font-size: 13px; font-weight: 500; }
    .toggle-icon { color: #CBD5E1; transition: transform .25s; font-size: 14px; }
    details[open] .toggle-icon { transform: rotate(180deg); }
    .details-body { padding: 20px 24px; }

    /* ── ハイライトセクション ── */
    .highlight-grid {
      display: grid; grid-template-columns: 1fr 1fr; gap: 10px;
    }
    .highlight-item {
      background: linear-gradient(135deg,#F0F9FF,white);
      border: 1px solid #BAE6FD;
      border-left: 4px solid #0EA5E9;
      border-radius: 9px; padding: 12px 15px;
      font-size: 13px; color: #0F172A; line-height: 1.55; font-weight: 500;
    }

    /* ── 重要ニュース ── */
    .breaking-banner {
      background: linear-gradient(135deg,#EF4444,#B91C1C);
      color: white; padding: 8px 24px;
      font-size: 10px; font-weight: 800;
      letter-spacing: 2.5px; text-transform: uppercase;
    }

    /* ── IR メトリクス ── */
    .metric-grid {
      display: grid; grid-template-columns: repeat(auto-fit,minmax(130px,1fr));
      gap: 12px; margin-bottom: 20px;
    }
    .metric-card {
      background: linear-gradient(135deg,#EFF6FF,white);
      border: 1px solid #BFDBFE; border-radius: 12px;
      padding: 16px; text-align: center;
    }
    .metric-value { font-size: 21px; font-weight: 800; color: #1D4ED8; line-height: 1.2; }
    .metric-label { font-size: 10px; color: #64748B; margin-top: 4px; font-weight: 500; }
    .metric-trend { font-size: 11px; font-weight: 700; margin-top: 4px; }
    .trend-up   { color: #059669; }
    .trend-down { color: #EF4444; }
    .ir-charts { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 20px; }
    .chart-box {
      position: relative; height: 220px; padding: 12px;
      border: 1px solid #E2E8F0; border-radius: 12px; background: #FAFCFF;
    }
    .ir-table { width: 100%; border-collapse: collapse; font-size: 12px; margin-top: 16px; }
    .ir-table th {
      background: #F8FAFC; padding: 10px 12px; text-align: left;
      font-weight: 700; border-bottom: 2px solid #E2E8F0;
      color: #475569; white-space: nowrap;
    }
    .ir-table td { padding: 10px 12px; border-bottom: 1px solid #F1F5F9; vertical-align: top; }
    .ir-table tr:hover td { background: #F8FAFC; }
    .tag-up   { color: #059669; font-weight: 700; }
    .tag-down { color: #EF4444; font-weight: 700; }

    /* ── フッター ── */
    .footer {
      background: #0F172A; color: #475569;
      text-align: center; padding: 28px;
      font-size: 12px; margin-top: 32px; line-height: 2.2;
    }

    /* ── レスポンシブ ── */
    @media (max-width: 768px) {
      .container { padding: 16px; }
      .header-inner { flex-wrap: wrap; }
      .header h1 { font-size: 16px; }
      .ir-charts, .highlight-grid { grid-template-columns: 1fr; }
      .metric-grid { grid-template-columns: repeat(2,1fr); }
      .category-nav { position: relative; top: auto; }
    }
"""

HTML_CLASS_GUIDE = """
【使用するHTMLクラス構造】

通常セクション(type=accordion):
<section id="{id}" class="section-card" data-cat="{id}">
  <div class="section-header">
    <div class="cat-icon">{icon}</div>
    <div class="section-title-wrap">
      <div class="section-title">{title}</div>
      <div class="section-sub">最新 {N}件</div>
    </div>
    <span class="section-badge">{N}</span>
  </div>
  <details open>
    <summary>
      <span class="summary-label">ニュース一覧を見る</span>
      <span class="toggle-icon">▼</span>
    </summary>
    <div class="details-body">
      <ul class="news-list">
        <li class="news-item">
          <div class="news-num">01</div>
          <div class="news-content">
            <div class="news-title">タイトル</div>
            <div class="news-snippet">詳細内容（具体的に）</div>
            <div class="news-meta">
              <span class="news-source"><a href="URL">出典</a></span>
            </div>
          </div>
        </li>
      </ul>
    </div>
  </details>
</section>

重要ニュース(type=breaking):
<section id="breaking" class="section-card" data-cat="breaking">
  <div class="breaking-banner">🚨 BREAKING — 重要ニュース</div>
  <div class="section-header">
    <div class="cat-icon">🚨</div>
    <div class="section-title-wrap">
      <div class="section-title">重要ニュース</div>
      <div class="section-sub">本日の注目トピック</div>
    </div>
    <span class="section-badge">{N}</span>
  </div>
  <div class="section-body">
    <ul class="news-list">（ニュースアイテム）</ul>
  </div>
</section>

IRセクション(type=ir):
<section id="ir" class="section-card" data-cat="ir">
  <div class="section-header">
    <div class="cat-icon">📊</div>
    <div class="section-title-wrap">
      <div class="section-title">IR・決算情報</div>
      <div class="section-sub">主要EC企業の業績</div>
    </div>
  </div>
  <div class="section-body">
    <div class="metric-grid">
      <div class="metric-card">
        <div class="metric-value">X.X兆円</div>
        <div class="metric-label">楽天グループ売上</div>
        <div class="metric-trend trend-up">↑ X.X%</div>
      </div>
      （企業ごとにmetric-cardを追加）
    </div>
    <div class="ir-charts">
      <div class="chart-box"><canvas id="revenueChart"></canvas></div>
      <div class="chart-box"><canvas id="growthChart"></canvas></div>
    </div>
    <table class="ir-table">
      <thead><tr><th>企業</th><th>最新売上</th><th>前年比</th><th>注目ポイント</th></tr></thead>
      <tbody>...</tbody>
    </table>
    <ul class="news-list">（IRニュース）</ul>
    <script>
      new Chart(document.getElementById('revenueChart'),{type:'bar',data:{labels:[...],datasets:[{label:'売上高（億円）',data:[...],backgroundColor:'#2563EB',borderRadius:6}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}}}});
      new Chart(document.getElementById('growthChart'),{type:'bar',data:{labels:[...],datasets:[{label:'成長率（%）',data:[...],backgroundColor:'#059669',borderRadius:6}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}}}});
    </script>
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
    year, month, _ = date_str.split("-")
    yearmonth = f"{year}年{month}月"
    year_str  = f"{year}年"

    news = {}
    for cat in CATEGORIES:
        cat_id = cat["id"]
        news[cat_id] = []
        for query_tmpl in cat["queries"]:
            query = query_tmpl.format(yearmonth=yearmonth, year=year_str)
            print(f"  🔍 [{cat_id}] {query[:50]}...")
            results = ddg_search(query, max_results=4)
            news[cat_id].extend(results)
            time.sleep(0.5)

        # 取得不足時のフォールバック（日時なし広域クエリ）
        if len(news[cat_id]) < 3:
            fallback = re.sub(r"\{[^}]+\}", "", cat["queries"][0]).strip()
            print(f"  [FALLBACK] {cat_id}: 広域クエリ再試行...")
            news[cat_id].extend(ddg_search(fallback, max_results=5))

    return news


# ── 3. Gemini API ─────────────────────────────────────────────
def call_gemini(prompt: str, retries: int = 5) -> str:
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    )
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 16384, "temperature": 0.7},
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
                wait = 60 * (attempt + 1)  # 60s, 120s, 180s, 240s
                print(f"  [WARN] レート制限 → {wait}秒待機...")
                time.sleep(wait)
            else:
                raise


def clean_output(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```html?\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    return text.strip()


# ── 4. HTML生成（JSON方式：Gemini→JSON、Python→HTML）──────────
def build_news_ctx(news: dict, cat_ids: list) -> str:
    lines = []
    for cat in CATEGORIES:
        if cat["id"] not in cat_ids:
            continue
        items = news.get(cat["id"], [])[:4]
        lines.append(f"\n### {cat['icon']} {cat['title']} (id={cat['id']})")
        for item in items:
            lines.append(f"- {item['title']}: {item['snippet'][:120]} [{item['url']}]")
    return "\n".join(lines)


def summarize_json(news: dict, date_jp: str, cat_ids: list, include_highlights: bool = False) -> dict:
    news_ctx = build_news_ctx(news, cat_ids)
    highlight_field = '"highlights": ["ハイライト項目（30文字以内）"],' if include_highlights else ""
    ir_field = ''
    if "ir" in cat_ids:
        ir_field = '''"ir": {
    "news": [{"title":"...","snippet":"...","url":"..."}],
    "metrics": [{"company":"楽天","value":"X.X兆円","growth":"+X.X%"}],
    "chart": {"labels":["楽天","メルカリ","ZOZO","BASE","Amazon"],"revenue":[1000,200,300,50,5000],"growth_pct":[5,10,3,2,8]}
  },'''
    other_fields = "\n  ".join(
        f'"{cid}": [{{"title":"...","snippet":"70文字以内","url":"..."}}],'
        for cid in cat_ids if cid != "ir"
    )

    prompt = f"""あなたはEC業界アナリストです。{date_jp}のニュースデータを分析し、以下のJSON形式で返してください。

{{
  {highlight_field}
  {ir_field}
  {other_fields}
}}

【ルール】
- 各カテゴリ最大4件、snippetは70文字以内で具体的に
- highlights（あれば）6〜8項目、各30文字以内
- データがない場合は空配列[]
- JSONのみ返す（コードブロック記号```不要）

【ニュースデータ】
{news_ctx}"""

    text = call_gemini(prompt)
    text = re.sub(r"^```json?\n?", "", text.strip())
    text = re.sub(r"\n?```$", "", text.strip())
    try:
        return json.loads(text)
    except Exception:
        try:
            return json.loads(text.rstrip(",\n ") + "\n}")
        except Exception:
            print("  [WARN] JSONパース失敗")
            return {}


def _esc(s: str) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_news_items(items: list) -> str:
    if not items:
        return '<p style="color:#94A3B8;font-size:13px;padding:8px 0">本日のニュースを取得できませんでした。</p>'
    html = '<ul class="news-list">'
    for i, item in enumerate(items, 1):
        url = item.get("url", "")
        href = f"https://{url}" if url and not url.startswith("http") else url
        domain = url.split("/")[0] if url else "出典"
        html += f'''<li class="news-item">
          <div class="news-num">{i:02d}</div>
          <div class="news-content">
            <div class="news-title">{_esc(item.get("title",""))}</div>
            <div class="news-snippet">{_esc(item.get("snippet",""))}</div>
            <div class="news-meta"><span class="news-source"><a href="{href}" target="_blank" rel="noopener">{_esc(domain)}</a></span></div>
          </div></li>'''
    return html + "</ul>"


def render_summary(highlights: list, date_jp: str) -> str:
    items_html = "".join(f'<div class="highlight-item">{_esc(h)}</div>' for h in highlights[:8])
    return f'''<section id="summary" class="section-card" data-cat="ir">
  <div class="section-header">
    <div class="cat-icon">✨</div>
    <div class="section-title-wrap">
      <div class="section-title">本日のハイライト</div>
      <div class="section-sub">{date_jp} EC業界トピックス</div>
    </div>
  </div>
  <div class="section-body"><div class="highlight-grid">{items_html}</div></div>
</section>'''


def render_ir(cat: dict, data: dict) -> str:
    news_items = data.get("news", []) if isinstance(data, dict) else []
    metrics = data.get("metrics", []) if isinstance(data, dict) else []
    chart = data.get("chart", {}) if isinstance(data, dict) else {}
    n = len(news_items)

    metrics_html = ""
    if metrics:
        cards = ""
        for m in metrics[:6]:
            g = str(m.get("growth", ""))
            tc = "trend-up" if "+" in g else ("trend-down" if "-" in g else "")
            cards += f'<div class="metric-card"><div class="metric-value">{_esc(m.get("value","-"))}</div><div class="metric-label">{_esc(m.get("company",""))}</div><div class="metric-trend {tc}">{_esc(g)}</div></div>'
        metrics_html = f'<div class="metric-grid">{cards}</div>'

    labels = json.dumps(chart.get("labels", ["楽天","メルカリ","ZOZO","BASE","Amazon"]), ensure_ascii=False)
    revenue = json.dumps(chart.get("revenue", []))
    growth  = json.dumps(chart.get("growth_pct", []))
    chart_html = f'''<div class="ir-charts">
      <div class="chart-box"><canvas id="revenueChart"></canvas></div>
      <div class="chart-box"><canvas id="growthChart"></canvas></div>
    </div>
    <script>
      new Chart(document.getElementById('revenueChart'),{{type:'bar',data:{{labels:{labels},datasets:[{{label:'売上高（参考・億円）',data:{revenue},backgroundColor:'#2563EB',borderRadius:6}}]}},options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{display:false}}}}}}}});
      new Chart(document.getElementById('growthChart'),{{type:'bar',data:{{labels:{labels},datasets:[{{label:'成長率（参考・%）',data:{growth},backgroundColor:'#059669',borderRadius:6}}]}},options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{display:false}}}}}}}});
    </script>'''

    return f'''<section id="ir" class="section-card" data-cat="ir">
  <div class="section-header">
    <div class="cat-icon">{cat["icon"]}</div>
    <div class="section-title-wrap"><div class="section-title">{cat["title"]}</div><div class="section-sub">主要EC企業の業績</div></div>
    <span class="section-badge">{n}</span>
  </div>
  <div class="section-body">{metrics_html}{chart_html}{render_news_items(news_items)}</div>
</section>'''


def render_section(cat: dict, items: list) -> str:
    cat_id, n = cat["id"], len(items)
    news_html = render_news_items(items)
    if cat["type"] == "breaking":
        return f'''<section id="{cat_id}" class="section-card" data-cat="{cat_id}">
  <div class="breaking-banner">🚨 BREAKING — 重要ニュース</div>
  <div class="section-header">
    <div class="cat-icon">{cat["icon"]}</div>
    <div class="section-title-wrap"><div class="section-title">{cat["title"]}</div><div class="section-sub">本日の注目トピック</div></div>
    <span class="section-badge">{n}</span>
  </div>
  <div class="section-body">{news_html}</div>
</section>'''
    return f'''<section id="{cat_id}" class="section-card" data-cat="{cat_id}">
  <div class="section-header">
    <div class="cat-icon">{cat["icon"]}</div>
    <div class="section-title-wrap"><div class="section-title">{cat["title"]}</div><div class="section-sub">最新 {n}件</div></div>
    <span class="section-badge">{n}</span>
  </div>
  <details open>
    <summary><span class="summary-label">ニュース一覧を見る</span><span class="toggle-icon">▼</span></summary>
    <div class="details-body">{news_html}</div>
  </details>
</section>'''


def build_html_shell(date_str: str, body_content: str) -> str:
    year, month, day = date_str.split("-")
    date_jp = f"{year}年{month}月{day}日"

    nav_links = "\n      ".join(
        f'<a href="#{cat["id"]}" class="nav-link" data-cat="{cat["id"]}" '
        f'style="--cc:{cat["color"]};--cb:{cat["bg"]}">{cat["icon"]} {cat["title"]}</a>'
        for cat in CATEGORIES
    )

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>EC業界ダッシュボード - {date_jp}</title>
  <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700;800&display=swap" rel="stylesheet">
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
{CSS}
  </style>
</head>
<body>

<header class="header">
  <div class="header-inner">
    <div class="header-left">
      <div class="header-logo">📈</div>
      <div>
        <h1>EC業界ダッシュボード</h1>
        <div class="header-sub">毎日自動更新 · Powered by Gemini AI</div>
      </div>
    </div>
    <div class="header-badge">
      <span class="live-dot"></span>{date_jp}
    </div>
  </div>
</header>

<nav class="category-nav">
  <div class="category-nav-inner">
    <a href="#summary" class="nav-link" style="--cc:#0EA5E9;--cb:#F0F9FF">✨ ハイライト</a>
    {nav_links}
  </div>
</nav>

<main class="container">
{body_content}
</main>

<footer class="footer">
  <div>本ダッシュボードはAIが自動生成しています。情報の正確性は保証しません。</div>
  <div>更新日時: {date_jp} ｜ Powered by Gemini API + DuckDuckGo</div>
</footer>

</body>
</html>"""


def generate_html(date_str: str, news: dict) -> str:
    year, month, day = date_str.split("-")
    date_jp = f"{year}年{month}月{day}日"

    # Batch1: ハイライト + 前半6カテゴリ → JSON
    batch1_ids = ["breaking", "ir", "platform", "ads", "logistics", "consumer"]
    print("  🤖 Batch1: ハイライト〜消費者（JSON）...")
    data1 = summarize_json(news, date_jp, batch1_ids, include_highlights=True)
    time.sleep(20)

    # Batch2: 後半5カテゴリ → JSON
    batch2_ids = ["legal", "competitor", "cart", "tools", "marketing"]
    print("  🤖 Batch2: 法規制〜マーケティング（JSON）...")
    data2 = summarize_json(news, date_jp, batch2_ids)

    all_data = {**data1, **data2}

    # PythonでHTML組み立て（絶対に欠けない）
    sections = [render_summary(all_data.get("highlights", []), date_jp)]
    for cat in CATEGORIES:
        raw = all_data.get(cat["id"], [])
        if cat["id"] == "ir":
            sections.append(render_ir(cat, raw if isinstance(raw, dict) else {}))
        else:
            sections.append(render_section(cat, raw if isinstance(raw, list) else []))

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
