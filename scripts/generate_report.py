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
GEMINI_MODEL = "gemini-2.5-flash-lite"  # v2

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
    {
        "id": "retail", "icon": "🏬", "title": "小売・OMO動向",
        "type": "accordion", "color": "#0F766E", "bg": "#F0FDFA",
        "queries": [
            "小売 OMO オムニチャネル 実店舗 EC 連携 {yearmonth}",
            "小売業 DX デジタル化 店舗 オンライン 統合 {year}",
        ],
    },
]

# ── 競合ベンチマーク対象企業（EC運営代行・ECコンサル・マーケ支援）────────
BENCHMARK_COMPANIES = [
    {"name": "いつも",                  "search": "いつも EC運営代行 コンサル 新サービス"},
    {"name": "フルスピード",             "search": "フルスピード EC デジタルマーケティング 動向"},
    {"name": "ソウルドアウト",           "search": "ソウルドアウト EC 広告 新サービス 発表"},
    {"name": "ecbeing",                 "search": "ecbeing EC 新機能 リリース 価格"},
    {"name": "シナブル",                "search": "シナブル EC CRM メール 新機能"},
    {"name": "スクロール360",           "search": "スクロール360 EC 物流 フルフィルメント"},
    {"name": "Hamee（ネクストエンジン）", "search": "Hamee ネクストエンジン EC 新機能"},
    {"name": "フィードフォース",         "search": "フィードフォース EC フィード 新サービス"},
    {"name": "ブレインパッド",           "search": "ブレインパッド EC データ分析 AI"},
    {"name": "デジタルアイデンティティ", "search": "デジタルアイデンティティ EC マーケティング"},
    {"name": "ロックオン",              "search": "ロックオン アドエビス EC マーケティング"},
    {"name": "オーリーズ",              "search": "オーリーズ EC 広告運用 新サービス"},
    {"name": "ファングリー",            "search": "ファングリー EC コンテンツ SEO"},
    {"name": "ディーゼロ",             "search": "ディーゼロ EC Web 制作 運営"},
    {"name": "電通デジタル",           "search": "電通デジタル EC コマース 支援"},
    {"name": "博報堂（EC）",           "search": "博報堂 EC デジタルコマース 支援"},
    {"name": "サイバーエージェント（EC）", "search": "サイバーエージェント EC コマース 支援"},
    {"name": "ネットショップ支援室",    "search": "ネットショップ支援室 Shopify EC"},
    {"name": "カスタメディア",         "search": "カスタメディア EC 運営代行"},
    {"name": "ベイクルーズ（EC）",     "search": "ベイクルーズ EC 自社 運営 D2C"},
]

# ── CSS（Python固定定義）────────────────────────────────────────
CSS = """
    /* ═══════════════════════════════════════════════════
       Premium Editorial Dashboard — Less is More
       Rule: 2 colors max, space is expensive, type first
    ═══════════════════════════════════════════════════ */
    *, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; }

    :root {
      --ink:    #0A0F1E;
      --ink-2:  #3D4757;
      --ink-3:  #8892A4;
      --ink-4:  #B8C0CC;
      --line:   #ECEEF2;
      --line-2: #F4F5F8;
      --bg:     #F6F7F9;
      --white:  #FFFFFF;
      --blue:   #1A56DB;
      --blue-l: #EBF0FD;
      --red:    #DC2626;
      --green:  #059669;
      --amber:  #D97706;
      --sh-sm: 0 1px 2px rgba(10,15,30,0.04);
      --sh:    0 2px 8px rgba(10,15,30,0.06), 0 12px 32px rgba(10,15,30,0.05);
      --sh-lg: 0 4px 16px rgba(10,15,30,0.08), 0 24px 56px rgba(10,15,30,0.08);
      --r:    12px;
      --r-sm: 6px;
      --r-lg: 20px;
    }

    body {
      font-family: 'Noto Sans JP', -apple-system, BlinkMacSystemFont, sans-serif;
      background: var(--bg); color: var(--ink);
      font-size: 14px; line-height: 1.7;
      -webkit-font-smoothing: antialiased;
      scroll-behavior: smooth;
    }
    a { color: inherit; text-decoration: none; }

    /* カテゴリカラー — アクセントのみに使用 */
    [data-cat]              { --cc:#1A56DB; }
    [data-cat="breaking"]   { --cc:#DC2626; }
    [data-cat="ir"]         { --cc:#1A56DB; }
    [data-cat="platform"]   { --cc:#6D28D9; }
    [data-cat="ads"]        { --cc:#B45309; }
    [data-cat="logistics"]  { --cc:#047857; }
    [data-cat="consumer"]   { --cc:#BE185D; }
    [data-cat="legal"]      { --cc:#4338CA; }
    [data-cat="competitor"] { --cc:#0369A1; }
    [data-cat="cart"]       { --cc:#7C3AED; }
    [data-cat="tools"]      { --cc:#15803D; }
    [data-cat="marketing"]  { --cc:#C2410C; }
    [data-cat="retail"]     { --cc:#0F766E; }

    /* ════════════════════
       HEADER
    ════════════════════ */
    .header {
      background: var(--ink);
      color: white;
      position: sticky; top: 0; z-index: 100;
    }
    .header-inner {
      max-width: 1200px; margin: 0 auto;
      padding: 0 32px;
      height: 60px;
      display: flex; align-items: center; justify-content: space-between;
    }
    .header-left { display: flex; align-items: center; gap: 16px; }
    .header-logo {
      width: 34px; height: 34px; border-radius: 9px;
      background: var(--blue);
      display: flex; align-items: center; justify-content: center;
      font-size: 17px; flex-shrink: 0;
    }
    .header h1 { font-size: 15px; font-weight: 700; letter-spacing: -0.3px; }
    .header-sub { font-size: 11px; color: rgba(255,255,255,0.35); margin-top: 1px; }
    .header-right { display: flex; align-items: center; gap: 12px; }
    .header-label {
      font-size: 10px; font-weight: 700; letter-spacing: 1px;
      color: rgba(255,255,255,0.4); text-transform: uppercase;
    }
    .header-date {
      display: flex; align-items: center; gap: 7px;
      border: 1px solid rgba(255,255,255,0.15);
      padding: 5px 14px; border-radius: 20px;
      font-size: 12.5px; font-weight: 600;
    }
    .live-dot {
      width: 6px; height: 6px; border-radius: 50%;
      background: #4ADE80;
      animation: blink 2.5s ease infinite;
    }
    @keyframes blink { 0%,100%{opacity:1} 50%{opacity:.4} }

    /* ════════════════════
       NAVIGATION
    ════════════════════ */
    .category-nav {
      background: rgba(255,255,255,0.92);
      backdrop-filter: blur(16px);
      border-bottom: 1px solid var(--line);
      position: sticky; top: 60px; z-index: 99;
    }
    .category-nav-inner {
      max-width: 1200px; margin: 0 auto;
      padding: 0 32px;
      display: flex; gap: 0;
      overflow-x: auto; white-space: nowrap;
      scrollbar-width: none; height: 48px; align-items: center;
    }
    .category-nav-inner::-webkit-scrollbar { display: none; }
    .nav-link {
      display: inline-flex; align-items: center; gap: 5px;
      padding: 6px 12px; border-radius: 6px;
      font-size: 12px; font-weight: 500; color: var(--ink-3);
      transition: all 0.15s; white-space: nowrap;
    }
    .nav-link:hover, .nav-link.active {
      background: var(--line-2); color: var(--ink); opacity: 1;
    }
    .nav-dot {
      width: 5px; height: 5px; border-radius: 50%;
      background: var(--cc,#1A56DB); opacity: 0; transition: opacity 0.15s;
    }
    .nav-link:hover .nav-dot, .nav-link.active .nav-dot { opacity: 1; }

    /* ════════════════════
       KPI BAR
    ════════════════════ */
    .kpi-bar {
      display: grid; grid-template-columns: repeat(4, 1fr);
      gap: 12px; margin-bottom: 28px;
    }
    .kpi-card {
      background: var(--white);
      border-radius: 14px; padding: 22px 24px;
      box-shadow: var(--sh-sm);
      border: 1px solid var(--line);
    }
    .kpi-value {
      font-size: 32px; font-weight: 900; color: var(--ink);
      line-height: 1; letter-spacing: -1px; margin-bottom: 6px;
    }
    .kpi-label { font-size: 12px; color: var(--ink-3); font-weight: 500; }

    /* ════════════════════
       LAYOUT
    ════════════════════ */
    .container { max-width: 1200px; margin: 0 auto; padding: 28px 32px; }

    /* ════════════════════
       SECTION CARDS
    ════════════════════ */
    .section-card {
      background: var(--white);
      border-radius: 16px;
      box-shadow: var(--sh);
      margin-bottom: 16px;
      border: 1px solid var(--line);
      overflow: hidden;
      transition: box-shadow 0.2s;
    }
    .section-card:hover { box-shadow: var(--sh-lg); }

    .section-header {
      padding: 22px 28px 20px;
      display: flex; align-items: center; gap: 14px;
      border-bottom: 1px solid var(--line-2);
    }
    .cat-icon {
      width: 40px; height: 40px; border-radius: 10px;
      background: var(--line-2);
      display: flex; align-items: center; justify-content: center;
      font-size: 20px; flex-shrink: 0;
    }
    .section-title-wrap { flex: 1; }
    .section-title {
      font-size: 16px; font-weight: 800; color: var(--ink); letter-spacing: -0.3px;
    }
    .section-sub { font-size: 11.5px; color: var(--ink-3); margin-top: 1px; }
    .section-badge {
      font-size: 12px; font-weight: 700;
      color: var(--ink-3); background: var(--line-2);
      padding: 3px 11px; border-radius: 20px;
      border: 1px solid var(--line);
    }
    .section-body { padding: 4px 28px 24px; }

    /* ════════════════════
       NEWS ITEMS
    ════════════════════ */
    .news-list { list-style: none; }
    .news-item {
      display: flex; gap: 16px;
      padding: 18px 0;
      border-bottom: 1px solid var(--line-2);
      align-items: flex-start;
    }
    .news-item:last-child { border-bottom: none; }
    .news-num {
      font-size: 13px; font-weight: 800;
      color: var(--ink-4);
      min-width: 24px; padding-top: 2px;
      font-variant-numeric: tabular-nums;
      flex-shrink: 0;
    }
    .news-content { flex: 1; min-width: 0; }
    .news-title {
      font-size: 14.5px; font-weight: 700; color: var(--ink);
      line-height: 1.5; margin-bottom: 5px;
    }
    .news-title a { color: inherit; transition: color 0.15s; }
    .news-title a:hover { color: var(--blue); }
    .news-snippet {
      font-size: 12.5px; color: var(--ink-2);
      line-height: 1.7; margin-bottom: 8px;
    }
    .news-meta { display: flex; gap: 6px; align-items: center; }
    .news-source {
      font-size: 10.5px; font-weight: 600; color: var(--ink-3);
      background: var(--line-2); border: 1px solid var(--line);
      padding: 2px 9px; border-radius: 4px;
    }

    /* ════════════════════
       ACTION BLOCK
    ════════════════════ */
    .action-block {
      margin-top: 16px; padding: 18px 20px;
      border-left: 3px solid var(--amber);
      background: #FFFDF7;
      border-radius: 0 10px 10px 0;
    }
    .action-title {
      font-size: 10px; font-weight: 800; letter-spacing: 1.2px;
      color: var(--amber); margin-bottom: 10px; text-transform: uppercase;
    }
    .action-list { list-style: none; }
    .action-item {
      display: flex; gap: 10px; align-items: baseline;
      padding: 6px 0; font-size: 13px; color: var(--ink-2); line-height: 1.55;
    }
    .action-item + .action-item { border-top: 1px solid rgba(217,119,6,0.1); }
    .action-bullet {
      font-size: 10px; font-weight: 800; color: var(--amber);
      flex-shrink: 0; width: 16px;
    }

    /* ════════════════════
       ACCORDION
    ════════════════════ */
    details summary {
      list-style: none; cursor: pointer;
      padding: 14px 28px;
      display: flex; align-items: center; justify-content: space-between;
      border-bottom: 1px solid var(--line-2);
      background: var(--white); user-select: none;
      transition: background 0.15s;
    }
    details summary:hover { background: var(--line-2); }
    details summary::-webkit-details-marker { display: none; }
    details[open] summary { border-bottom: 1px solid var(--line); }
    .summary-label { color: var(--ink-3); font-size: 12px; font-weight: 500; }
    .toggle-icon { color: var(--ink-4); transition: transform 0.25s; font-size: 11px; }
    details[open] .toggle-icon { transform: rotate(180deg); }
    .details-body { padding: 4px 28px 24px; }

    /* ════════════════════
       HIGHLIGHTS
    ════════════════════ */
    .highlight-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    .highlight-item {
      padding: 14px 16px;
      border-left: 3px solid var(--blue);
      background: var(--blue-l);
      border-radius: 0 8px 8px 0;
      font-size: 13px; color: var(--ink); line-height: 1.6; font-weight: 500;
      transition: transform 0.15s;
    }
    .highlight-item:hover { transform: translateX(2px); }

    /* ════════════════════
       BREAKING
    ════════════════════ */
    .breaking-banner {
      background: var(--red); color: white;
      padding: 8px 28px;
      font-size: 9.5px; font-weight: 800;
      letter-spacing: 2px; text-transform: uppercase;
      display: flex; align-items: center; gap: 8px;
    }
    .breaking-dot {
      width: 6px; height: 6px; border-radius: 50%; background: white;
      animation: blink 1.5s ease infinite; flex-shrink: 0;
    }

    /* ════════════════════
       IR / METRICS
    ════════════════════ */
    .metric-grid {
      display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
      gap: 12px; margin-bottom: 20px;
    }
    .metric-card {
      background: var(--line-2); border: 1px solid var(--line);
      border-radius: 12px; padding: 18px;
      text-align: center; transition: box-shadow 0.15s;
    }
    .metric-card:hover { box-shadow: var(--sh); }
    .metric-value { font-size: 24px; font-weight: 900; color: var(--ink); line-height: 1.1; letter-spacing: -0.5px; }
    .metric-label { font-size: 10.5px; color: var(--ink-3); margin-top: 5px; font-weight: 500; }
    .metric-trend { font-size: 12px; font-weight: 700; margin-top: 6px; }
    .trend-up   { color: var(--green); }
    .trend-down { color: var(--red); }
    .ir-charts { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 20px; }
    .chart-box {
      position: relative; height: 200px; padding: 14px;
      border: 1px solid var(--line); border-radius: 12px; background: var(--line-2);
    }
    .ir-table { width: 100%; border-collapse: collapse; font-size: 12.5px; margin-top: 16px; }
    .ir-table th {
      background: var(--line-2); padding: 10px 14px; text-align: left;
      font-weight: 700; border-bottom: 2px solid var(--line);
      color: var(--ink-2); font-size: 11px;
    }
    .ir-table td { padding: 10px 14px; border-bottom: 1px solid var(--line-2); }
    .ir-table tbody tr:hover td { background: var(--line-2); }
    .ir-table tbody tr:last-child td { border-bottom: none; }
    .tag-up   { color: var(--green); font-weight: 700; }
    .tag-down { color: var(--red);   font-weight: 700; }

    /* ════════════════════
       FOOTER
    ════════════════════ */
    .footer {
      background: var(--ink); color: rgba(255,255,255,0.3);
      text-align: center; padding: 40px 32px;
      font-size: 12px; margin-top: 40px; line-height: 2.4;
    }
    .footer-logo { font-size: 24px; margin-bottom: 4px; opacity: 0.5; }
    .footer-brand { color: rgba(255,255,255,0.5); font-weight: 700; font-size: 13px; }
    .footer-divider { width: 32px; height: 1px; background: rgba(255,255,255,0.1); margin: 12px auto; }

    /* ════════════════════
       RESPONSIVE
    ════════════════════ */
    @media (max-width: 900px) { .kpi-bar { grid-template-columns: repeat(2,1fr); } .bench-grid { grid-template-columns: 1fr; } }
    @media (max-width: 768px) {
      .container { padding: 16px; }
      .header-inner { padding: 0 16px; }
      .category-nav-inner { padding: 0 16px; }
      .category-nav { position: relative; top: auto; }
      .section-header { padding: 18px 20px 16px; }
      .section-body, .details-body { padding: 4px 20px 20px; }
      details summary { padding: 12px 20px; }
      .ir-charts, .highlight-grid { grid-template-columns: 1fr; }
      .metric-grid { grid-template-columns: repeat(2,1fr); }
      .kpi-bar { grid-template-columns: 1fr 1fr; gap: 10px; }
      .bench-grid { grid-template-columns: 1fr; }
    }

    /* ── 競合ベンチマーク ── */
    .bench-summary {
      background: var(--blue-l); border-left: 3px solid var(--blue);
      border-radius: var(--r); padding: 16px 20px; margin-bottom: 24px;
      font-size: 13.5px; color: var(--ink-2); line-height: 1.7;
    }
    .bench-summary-title {
      font-size: 11px; font-weight: 700; letter-spacing: .08em;
      text-transform: uppercase; color: var(--blue); margin-bottom: 8px;
    }
    .bench-top-actions {
      margin-top: 14px; display: flex; flex-direction: column; gap: 6px;
    }
    .bench-top-action {
      display: flex; align-items: flex-start; gap: 10px;
      font-size: 13px; font-weight: 600; color: var(--ink);
    }
    .bench-top-action::before {
      content: "→"; color: var(--blue); flex-shrink: 0; font-weight: 700;
    }
    .bench-grid {
      display: grid; grid-template-columns: repeat(2, 1fr); gap: 14px;
    }
    .bench-card {
      background: var(--white); border: 1px solid var(--line);
      border-radius: var(--r); padding: 18px 20px;
      box-shadow: var(--sh-sm); transition: box-shadow .2s;
    }
    .bench-card:hover { box-shadow: var(--sh); }
    .bench-card-header {
      display: flex; align-items: center; justify-content: space-between;
      margin-bottom: 10px;
    }
    .bench-company {
      font-size: 13px; font-weight: 800; color: var(--ink); letter-spacing: -.01em;
    }
    .bench-threat {
      font-size: 10px; font-weight: 700; letter-spacing: .06em;
      padding: 3px 8px; border-radius: 99px;
    }
    .bench-threat.high   { background: #FEE2E2; color: #B91C1C; }
    .bench-threat.medium { background: #FEF3C7; color: #92400E; }
    .bench-threat.low    { background: #DCFCE7; color: #166534; }
    .bench-move {
      font-size: 12.5px; color: var(--ink-2); line-height: 1.6;
      margin-bottom: 12px; padding-bottom: 12px; border-bottom: 1px solid var(--line);
    }
    .bench-actions-label {
      font-size: 10px; font-weight: 700; letter-spacing: .07em;
      text-transform: uppercase; color: var(--amber); margin-bottom: 7px;
    }
    .bench-action-list {
      list-style: none; display: flex; flex-direction: column; gap: 5px;
    }
    .bench-action-item {
      font-size: 12px; color: var(--ink); display: flex; gap: 8px;
      align-items: flex-start; line-height: 1.5;
    }
    .bench-action-item::before {
      content: "▸"; color: var(--amber); flex-shrink: 0; font-size: 10px; margin-top: 2px;
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
def google_news_rss(query: str, max_results: int = 5) -> list[dict]:
    """Google News RSSから最新ニュース取得（レート制限なし・構造化データ）"""
    results = []
    try:
        q = urllib.parse.quote_plus(query)
        url = f"https://news.google.com/rss/search?q={q}&hl=ja&gl=JP&ceid=JP:ja"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64)",
            "Accept-Language": "ja,en;q=0.9",
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            xml = resp.read().decode("utf-8", errors="replace")

        for item_xml in re.findall(r"<item>(.*?)</item>", xml, re.DOTALL)[:max_results]:
            title_m  = re.search(r"<title>(.*?)</title>", item_xml)
            link_m   = re.search(r"<link>(https?://[^<]+)</link>", item_xml)
            source_m = re.search(r'<source[^>]+url="([^"]+)"', item_xml)

            raw = re.sub(r"<!\[CDATA\[|\]\]>", "", title_m.group(1) if title_m else "").strip()
            raw = re.sub(r"<[^>]+>", "", raw).strip()
            # 「タイトル - 出典名」の形式から出典名を除去
            parts = raw.rsplit(" - ", 1)
            title = parts[0].strip() if len(parts) > 1 else raw

            article_url = (link_m.group(1) if link_m else "").strip()
            source_url  = (source_m.group(1) if source_m else "").strip()

            if title:
                results.append({"title": title, "url": article_url, "source_url": source_url, "snippet": ""})
    except Exception as e:
        print(f"[WARN] Google News RSS失敗 ({query[:30]}): {e}")
    return results


def ddg_search(query: str, max_results: int = 5) -> list[dict]:
    """DuckDuckGo HTMLから検索結果取得（フォールバック用）"""
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
            results = google_news_rss(query, max_results=4)
            if not results:
                print(f"    → RSS 0件、DuckDuckGoへ切替...")
                results = ddg_search(query, max_results=4)
            news[cat_id].extend(results)
            time.sleep(1)

        # 取得不足時のフォールバック
        if len(news[cat_id]) < 3:
            fallback_q = f"{cat['title']} EC {year_str}"
            print(f"  [FALLBACK] {cat_id}: 広域クエリ再試行...")
            extra = google_news_rss(fallback_q, max_results=5)
            if not extra:
                fallback = re.sub(r"\{[^}]+\}", "", cat["queries"][0]).strip()
                extra = ddg_search(fallback, max_results=5)
            news[cat_id].extend(extra)
            time.sleep(1)

    return news


def collect_benchmark_news() -> list[dict]:
    """競合20社の直近ニュースを収集（各社2件）"""
    results = []
    for co in BENCHMARK_COMPANIES:
        print(f"  🔍 [bench] {co['name']}...")
        items = google_news_rss(co["search"], max_results=2)
        if not items:
            items = ddg_search(co["search"], max_results=2)
        results.append({"company": co["name"], "news": items})
        time.sleep(0.8)
    return results


# ── 3. Gemini API ─────────────────────────────────────────────
def call_gemini(prompt: str, retries: int = 5, timeout: int = 120) -> str:
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
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode())
            candidates = data.get("candidates", [])
            if not candidates:
                raise RuntimeError(f"Gemini candidates空: {data}")
            return candidates[0]["content"]["parts"][0]["text"]
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries - 1:
                wait = min(60 * (attempt + 1), 120)  # 最大120秒
                print(f"  [WARN] レート制限 → {wait}秒待機...")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("Gemini API: 全リトライ失敗")


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
            snip = item.get("snippet", "").strip()
            title = item.get("title", "")
            desc = f": {snip[:120]}" if snip and snip != title else ""
            lines.append(f"- {title}{desc} [{item['url']}]")
    return "\n".join(lines)


def summarize_json(news: dict, date_jp: str, cat_ids: list, include_highlights: bool = False) -> dict:
    news_ctx = build_news_ctx(news, cat_ids)
    highlight_field = '"highlights": ["ハイライト項目（30文字以内）"],' if include_highlights else ""
    ir_field = ''
    if "ir" in cat_ids:
        ir_field = '''"ir": {
    "news": [{"title":"ニュースタイトル","snippet":"内容70文字以内","url":"https://..."}],
    "metrics": [{"company":"楽天グループ","value":"2.1兆円","growth":"+5.2%"},{"company":"メルカリ","value":"2,100億円","growth":"+12%"}],
    "chart": {"labels":["楽天","メルカリ","ZOZO","BASE","Amazon Japan"],"revenue":[21000,2100,1900,200,30000],"growth_pct":[5,12,3,2,8]},
    "actions": ["アクション（40文字以内）"]
  },'''
    other_fields = "\n  ".join(
        f'"{cid}": {{"items":[{{"title":"...","snippet":"70文字以内","url":"..."}}],"actions":["アクション（40文字以内）"]}},'
        for cid in cat_ids if cid != "ir"
    )

    prompt = f"""あなたはEC業界アナリストで、株式会社サイバーレコードのEC事業部向けにレポートを作成しています。
{date_jp}のニュースデータを分析し、以下のJSON形式で返してください。

{{
  {highlight_field}
  {ir_field}
  {other_fields}
}}

【ルール】
- 各カテゴリ items: 最大4件、snippetは70文字以内で具体的に（記事内容が不明な場合はタイトルからEC文脈で補足説明を生成）
- 各カテゴリ actions: サイバーレコードEC事業部が今週中に取るべき具体的アクションを2〜3件、各40文字以内
  （例: 「楽天の新手数料改定を確認し費用シミュレーションを更新する」「TikTok広告のCPM上昇に備え予算配分を見直す」）
- highlights（あれば）6〜8項目、各30文字以内
- ir.metrics: 各社の実際の売上・成長率を知識から補完して必ず具体的な数値で記載（「X.X兆円」などプレースホルダー禁止）
- ir.chart: revenue は億円単位の実数値、growth_pct は実数値（%記号なし）
- データがない場合はitemsを空配列[]、actionsも空配列[]
- urlはニュースデータのURLをそのまま使用
- JSONのみ返す（コードブロック記号```不要）

【ニュースデータ】
{news_ctx}"""

    text = call_gemini(prompt)
    text = re.sub(r"(?i)^```[a-z]*\n?", "", text.strip())
    text = re.sub(r"\n?```$", "", text.strip())
    try:
        return json.loads(text)
    except Exception:
        try:
            return json.loads(text.rstrip(",\n ") + "\n}")
        except Exception:
            print("  [WARN] JSONパース失敗")
            return {}


def summarize_benchmark_json(bench_news: list, date_jp: str) -> dict:
    """競合ベンチマーク分析をGeminiに依頼"""
    lines = []
    for co in bench_news:
        lines.append(f"\n### {co['company']}")
        for item in co["news"]:
            snip = item.get("snippet", "").strip()
            desc = f": {snip[:120]}" if snip and snip != item.get("title","") else ""
            lines.append(f"- {item.get('title','')}{desc}")
        if not co["news"]:
            lines.append("- （最新ニュースなし）")
    news_ctx = "\n".join(lines)

    prompt = f"""あなたはEC業界アナリストです。株式会社サイバーレコード（EC運営代行・コンサル会社）の競合分析を行います。
競合他社ニュースデータを分析し、以下のJSON形式で返してください。

{{
  "summary": "競合全体の動向サマリー（80文字以内）",
  "top_actions": ["サイバーレコードが今すぐ取るべき対抗策（40文字以内）×3件"],
  "companies": [
    {{"name": "会社名", "recent_move": "動向（50文字以内）", "threat": "high|medium|low", "actions": ["推奨アクション×2件（40文字以内）"]}}
  ]
}}

【ルール】
- companies: ニュースが取得できた企業のみ記載（全社不要）
- threat: high=直接競合, medium=部分競合, low=間接競合
- JSONのみ返す（```不要）

【競合他社ニュースデータ】
{news_ctx}"""

    text = call_gemini(prompt, timeout=180)
    text = re.sub(r"(?i)^```[a-z]*\n?", "", text.strip())
    text = re.sub(r"\n?```$", "", text.strip())
    try:
        return json.loads(text)
    except Exception:
        try:
            return json.loads(text.rstrip(",\n ") + "\n}")
        except Exception:
            print("  [WARN] ベンチマークJSONパース失敗")
            return {}


def _esc(s: str) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_news_items(items: list) -> str:
    if not items:
        return '<p style="color:#94A3B8;font-size:13px;padding:8px 0">本日のニュースを取得できませんでした。</p>'
    html = '<ul class="news-list">'
    for i, item in enumerate(items, 1):
        url = item.get("url", "")
        source_url = item.get("source_url", "")
        href = f"https://{url}" if url and not url.startswith("http") else url
        display_url = source_url if source_url else url
        if display_url.startswith("http"):
            domain = re.sub(r"^https?://(www\.)?", "", display_url).split("/")[0]
        else:
            domain = display_url.split("/")[0] if display_url else "出典"
        title_html = (f'<a href="{_esc(href)}" target="_blank" rel="noopener">{_esc(item.get("title",""))}</a>'
                      if href else _esc(item.get("title", "")))
        html += f'''<li class="news-item">
          <div class="news-num">{i:02d}</div>
          <div class="news-content">
            <div class="news-title">{title_html}</div>
            <div class="news-snippet">{_esc(item.get("snippet",""))}</div>
            <div class="news-meta"><span class="news-source">{_esc(domain)}</span></div>
          </div></li>'''
    return html + "</ul>"


def render_actions(actions: list) -> str:
    if not actions:
        return ""
    items_html = "".join(
        f'<li class="action-item"><span class="action-bullet">{i}</span><span>{_esc(a)}</span></li>'
        for i, a in enumerate(actions[:3], 1)
    )
    return f'<div class="action-block"><div class="action-title">⚡ サイバーレコードEC事業部 推奨アクション</div><ul class="action-list">{items_html}</ul></div>'


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


def render_ir(cat: dict, data: dict, actions: list = None) -> str:
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
  <div class="section-body">{metrics_html}{chart_html}{render_news_items(news_items)}{render_actions(actions or [])}</div>
</section>'''


def render_section(cat: dict, items: list, actions: list = None) -> str:
    cat_id, n = cat["id"], len(items)
    news_html = render_news_items(items)
    actions_html = render_actions(actions or [])
    if cat["type"] == "breaking":
        return f'''<section id="{cat_id}" class="section-card" data-cat="{cat_id}">
  <div class="breaking-banner"><span class="breaking-dot"></span>BREAKING — 重要ニュース</div>
  <div class="section-header">
    <div class="cat-icon">{cat["icon"]}</div>
    <div class="section-title-wrap"><div class="section-title">{cat["title"]}</div><div class="section-sub">本日の注目トピック</div></div>
    <span class="section-badge">{n}</span>
  </div>
  <div class="section-body">{news_html}{actions_html}</div>
</section>'''
    return f'''<section id="{cat_id}" class="section-card" data-cat="{cat_id}">
  <div class="section-header">
    <div class="cat-icon">{cat["icon"]}</div>
    <div class="section-title-wrap"><div class="section-title">{cat["title"]}</div><div class="section-sub">最新 {n}件</div></div>
    <span class="section-badge">{n}</span>
  </div>
  <details open>
    <summary><span class="summary-label">ニュース一覧を見る</span><span class="toggle-icon">▼</span></summary>
    <div class="details-body">{news_html}{actions_html}</div>
  </details>
</section>'''


def render_benchmark_section(bench_data: dict) -> str:
    """競合ベンチマークセクションのHTMLを生成"""
    if not bench_data:
        return ""

    summary = _esc(bench_data.get("summary", ""))
    top_actions = bench_data.get("top_actions", [])
    companies = bench_data.get("companies", [])
    n = len(companies)

    top_acts_html = "".join(
        f'<div class="bench-top-action">{_esc(a)}</div>'
        for a in top_actions[:3]
    )
    summary_html = f'''<div class="bench-summary">
  <div class="bench-summary-title">競合全体サマリー</div>
  {summary}
  <div class="bench-top-actions">{top_acts_html}</div>
</div>'''

    cards_html = ""
    for co in companies:
        threat = co.get("threat", "medium")
        threat_label = {"high": "⚠ 高脅威", "medium": "● 中脅威", "low": "○ 低脅威"}.get(threat, "● 中脅威")
        actions_li = "".join(
            f'<li class="bench-action-item">{_esc(a)}</li>'
            for a in co.get("actions", [])[:2]
        )
        cards_html += f'''<div class="bench-card">
  <div class="bench-card-header">
    <div class="bench-company">{_esc(co.get("name",""))}</div>
    <span class="bench-threat {threat}">{threat_label}</span>
  </div>
  <div class="bench-move">{_esc(co.get("recent_move","情報なし"))}</div>
  <div class="bench-actions-label">推奨アクション</div>
  <ul class="bench-action-list">{actions_li}</ul>
</div>'''

    return f'''<section id="benchmark" class="section-card" data-cat="benchmark">
  <div class="section-header">
    <div class="cat-icon">🏆</div>
    <div class="section-title-wrap">
      <div class="section-title">競合ベンチマーク</div>
      <div class="section-sub">EC運営代行・コンサル {n}社の動向</div>
    </div>
    <span class="section-badge">{n}</span>
  </div>
  <details open>
    <summary><span class="summary-label">競合各社の動向を見る</span><span class="toggle-icon">▼</span></summary>
    <div class="details-body">
      {summary_html}
      <div class="bench-grid">{cards_html}</div>
    </div>
  </details>
</section>'''


def build_html_shell(date_str: str, body_content: str) -> str:
    year, month, day = date_str.split("-")
    date_jp = f"{year}年{month}月{day}日"

    nav_links = "\n      ".join(
        f'<a href="#{cat["id"]}" class="nav-link" data-cat="{cat["id"]}" '
        f'style="--cc:{cat["color"]};--cb:{cat["bg"]}">'
        f'<span class="nav-dot"></span>{cat["icon"]} {cat["title"]}</a>'
        for cat in CATEGORIES
    )

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>EC業界ダッシュボード {date_jp} | サイバーレコード</title>
  <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700;800;900&display=swap" rel="stylesheet">
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
        <div class="header-sub">株式会社サイバーレコード EC事業部 · 毎日自動更新</div>
      </div>
    </div>
    <div class="header-right">
      <span class="header-label">Daily Report</span>
      <div class="header-date">
        <span class="live-dot"></span>{date_jp}
      </div>
    </div>
  </div>
</header>

<nav class="category-nav">
  <div class="category-nav-inner">
    <a href="#benchmark" class="nav-link" style="--cc:#7C3AED;--cb:#F5F3FF"><span class="nav-dot"></span>🏆 競合ベンチマーク</a>
    <a href="#summary" class="nav-link" style="--cc:#0EA5E9;--cb:#F0F9FF"><span class="nav-dot"></span>✨ ハイライト</a>
    {nav_links}
  </div>
</nav>

<main class="container">
{body_content}
</main>

<footer class="footer">
  <div class="footer-logo">📈</div>
  <div class="footer-brand">株式会社サイバーレコード EC事業部</div>
  <div class="footer-divider"></div>
  <div>本ダッシュボードはAIが自動生成しています。情報の正確性は保証しません。</div>
  <div>更新日時: {date_jp} ｜ Powered by Gemini AI + Google News RSS</div>
</footer>

<script>
  (function() {{
    var sections = document.querySelectorAll('.section-card[id]');
    var navLinks = document.querySelectorAll('.nav-link');
    if (!('IntersectionObserver' in window)) return;
    var io = new IntersectionObserver(function(entries) {{
      entries.forEach(function(e) {{
        if (e.isIntersecting) {{
          navLinks.forEach(function(l) {{ l.classList.remove('active'); }});
          var a = document.querySelector('.nav-link[href="#' + e.target.id + '"]');
          if (a) a.classList.add('active');
        }}
      }});
    }}, {{ threshold: 0.3 }});
    sections.forEach(function(s) {{ io.observe(s); }});
  }})();
</script>

</body>
</html>"""


def generate_html(date_str: str, news: dict) -> str:
    year, month, day = date_str.split("-")
    date_jp = f"{year}年{month}月{day}日"

    # Batch1: ハイライト + 前半6カテゴリ → JSON
    batch1_ids = ["breaking", "ir", "platform", "ads", "logistics", "consumer"]
    print("  🤖 Batch1: ハイライト〜消費者（JSON）...")
    data1 = summarize_json(news, date_jp, batch1_ids, include_highlights=True)
    time.sleep(15)

    # Batch2: 後半6カテゴリ → JSON
    batch2_ids = ["legal", "competitor", "cart", "tools", "marketing", "retail"]
    print("  🤖 Batch2: 法規制〜小売（JSON）...")
    data2 = summarize_json(news, date_jp, batch2_ids)

    all_data = {**data1, **data2}

    def extract(cat_id: str):
        """カテゴリデータからitemsとactionsを取得（新旧両形式対応）"""
        raw = all_data.get(cat_id, [])
        if isinstance(raw, dict) and "items" in raw:
            return raw.get("items", []), raw.get("actions", [])
        if isinstance(raw, list):
            return raw, []
        return [], []

    # Batch3: 競合ベンチマーク → JSON（失敗しても全体は続行）
    bench_news = []
    bench_data = {}
    try:
        print("  🤖 Batch3: 競合ベンチマーク（JSON）...")
        bench_news = collect_benchmark_news()
        time.sleep(15)
        bench_data = summarize_benchmark_json(bench_news, date_jp)
    except Exception as e:
        print(f"  [WARN] ベンチマーク失敗（スキップ）: {e}")
        bench_news = []
        bench_data = {}

    # KPI バー（収集統計）
    bench_count = len([c for c in bench_news if c["news"]])
    total_news = sum(len(v) for v in news.values())
    cats_covered = len([v for v in news.values() if v])
    kpi_bar = f'''<div class="kpi-bar">
  <div class="kpi-card"><div class="kpi-icon blue">📰</div><div class="kpi-body"><div class="kpi-value">{total_news}</div><div class="kpi-label">収集ニュース数</div></div></div>
  <div class="kpi-card"><div class="kpi-icon green">📂</div><div class="kpi-body"><div class="kpi-value">{cats_covered}</div><div class="kpi-label">カバー分野数</div></div></div>
  <div class="kpi-card"><div class="kpi-icon purple">🏆</div><div class="kpi-body"><div class="kpi-value">{bench_count}</div><div class="kpi-label">競合ベンチマーク社数</div></div></div>
  <div class="kpi-card"><div class="kpi-icon amber">🔄</div><div class="kpi-body"><div class="kpi-value">毎朝</div><div class="kpi-label">8:00 JST 自動更新</div></div></div>
</div>'''

    # PythonでHTML組み立て（絶対に欠けない）
    bench_html = render_benchmark_section(bench_data)
    sections = [kpi_bar]
    if bench_html:
        sections.append(bench_html)
    sections.append(render_summary(all_data.get("highlights", []), date_jp))
    for cat in CATEGORIES:
        if cat["id"] == "ir":
            ir_raw = all_data.get("ir", {})
            ir_actions = ir_raw.get("actions", []) if isinstance(ir_raw, dict) else []
            sections.append(render_ir(cat, ir_raw if isinstance(ir_raw, dict) else {}, ir_actions))
        else:
            items, actions = extract(cat["id"])
            sections.append(render_section(cat, items, actions))

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
    content_b64 = base64.b64encode(html.encode()).decode()
    url = f"https://api.github.com/repos/{GH_OWNER}/{GH_REPO}/contents/{GH_FILE}"
    for attempt in range(3):
        sha = get_file_sha()
        payload = {
            "message": f"Daily EC dashboard {date_str}",
            "content": content_b64,
            "branch": GH_BRANCH,
        }
        if sha:
            payload["sha"] = sha
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {GH_PAT}",
                "Accept": "application/vnd.github.v3+json",
                "Content-Type": "application/json",
            },
            method="PUT",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode())
            return data["commit"]["sha"]
        except urllib.error.HTTPError as e:
            if e.code == 409 and attempt < 2:
                print(f"  [WARN] GitHub Push 409競合 → SHA再取得してリトライ...")
                time.sleep(3)
            else:
                raise
    raise RuntimeError("GitHub Push: 全リトライ失敗")


# ── 6. Chatwork通知（承認後に有効化）────────────────────────────
def notify_chatwork(date_str: str, commit_sha: str):
    if not CHATWORK_ENABLED:
        print("  [SKIP] Chatwork通知は無効（CHATWORK_ENABLED=false）")
        return None
    if not CHATWORK_TOKEN or not CHATWORK_ROOM_ID:
        print("  [SKIP] CHATWORK_TOKEN または CHATWORK_ROOM_ID が未設定")
        return None
    url_report = f"https://{GH_OWNER.lower()}.github.io/{GH_REPO}/"
    year, month, day = date_str.split("-")
    msg = (
        f"[toall]\n"
        f"📊【EC業界ダッシュボード {year}年{month}月{day}日版】を公開しました！\n\n"
        f"🔥 本日のトピック\n"
        f"・重要ニュース・IR・プラットフォーム動向など12カテゴリを自動収集\n"
        f"・🏆 競合ベンチマーク（EC運営代行・コンサル20社の動向）\n"
        f"・⚡ サイバーレコードEC事業部 推奨アクション付き\n\n"
        f"▼ ダッシュボードはこちら\n{url_report}\n\n"
        f"🤖 Gemini AI + Google News RSS で毎朝8:00 JST 自動更新\n"
        f"株式会社サイバーレコード EC事業部"
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
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode())
        return result.get("message_id")
    except Exception as e:
        print(f"  [WARN] Chatwork通知失敗（レポートは正常完了）: {e}")
        return None


# ── メイン ────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("EC業界ダッシュボード 自動生成開始")
    print("=" * 60)

    print("\n[1/5] JST日付取得...")
    date_str = get_jst_date()
    print(f"  → {date_str}")

    print("\n[2/5] ニュース収集（12カテゴリ + 競合20社）...")
    news = collect_all_news(date_str)
    total = sum(len(v) for v in news.values())
    print(f"  → {total}件取得")

    print("\n[3/5] HTML生成（Gemini・JSON方式 + 競合ベンチマーク）...")
    html = generate_html(date_str, news)
    print(f"  → {len(html):,} bytes")

    print("\n[4/5] GitHub push...")
    try:
        commit_sha = push_to_github(html, date_str)
        print(f"  → commit: {commit_sha[:12]}")
    except Exception as e:
        print(f"  [ERROR] GitHub Push失敗: {e}")
        commit_sha = "000000"

    print("\n[5/5] Chatwork通知...")
    notify_chatwork(date_str, commit_sha)

    print("\n✅ 完了!")
    print(f"   ダッシュボードURL: https://m-hirasawa95.github.io/ec-report/")
    print(f"   commit SHA: {commit_sha[:12]}")


if __name__ == "__main__":
    main()
