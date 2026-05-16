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
    {
        "id": "retail", "icon": "🏬", "title": "小売・OMO動向",
        "type": "accordion", "color": "#0F766E", "bg": "#F0FDFA",
        "queries": [
            "小売 OMO オムニチャネル 実店舗 EC 連携 {yearmonth}",
            "小売業 DX デジタル化 店舗 オンライン 統合 {year}",
        ],
    },
]

# ── CSS（Python固定定義）────────────────────────────────────────
CSS = """
    /* ═══════════════════════════════════════════════════════════════
       EC Dashboard Design System
       Ref: Vercel · Linear · Stripe · Grafana · Amplitude · Looker
    ═══════════════════════════════════════════════════════════════ */
    *, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; }

    :root {
      --r-sm: 6px; --r: 10px; --r-lg: 14px; --r-xl: 20px;
      --sh-xs: 0 1px 2px rgba(0,0,0,0.05);
      --sh:    0 1px 4px rgba(0,0,0,0.06), 0 4px 16px rgba(0,0,0,0.05);
      --sh-md: 0 2px 8px rgba(0,0,0,0.07), 0 8px 28px rgba(0,0,0,0.06);
      --bg:       #F4F7FB;
      --surface:  #FFFFFF;
      --surface-2:#F8FAFD;
      --border:   #E4E9F0;
      --border-2: #EEF2F7;
      --txt-1: #0C1524;
      --txt-2: #445168;
      --txt-3: #8A9BB8;
    }

    body {
      font-family: 'Noto Sans JP', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      background: var(--bg); color: var(--txt-1);
      font-size: 14px; line-height: 1.65;
      -webkit-font-smoothing: antialiased;
      -moz-osx-font-smoothing: grayscale;
      scroll-behavior: smooth;
    }
    a { color: inherit; text-decoration: none; }

    /* ── カテゴリカラーマップ ── */
    [data-cat]              { --cc:#2563EB; --cb:#EFF6FF; --cg:rgba(37,99,235,0.09); }
    [data-cat="breaking"]   { --cc:#DC2626; --cb:#FEF2F2; --cg:rgba(220,38,38,0.09); }
    [data-cat="ir"]         { --cc:#1D4ED8; --cb:#EFF6FF; --cg:rgba(29,78,216,0.09); }
    [data-cat="platform"]   { --cc:#6D28D9; --cb:#F5F3FF; --cg:rgba(109,40,217,0.09); }
    [data-cat="ads"]        { --cc:#B45309; --cb:#FFFBEB; --cg:rgba(180,83,9,0.09); }
    [data-cat="logistics"]  { --cc:#047857; --cb:#ECFDF5; --cg:rgba(4,120,87,0.09); }
    [data-cat="consumer"]   { --cc:#BE185D; --cb:#FDF2F8; --cg:rgba(190,24,93,0.09); }
    [data-cat="legal"]      { --cc:#4338CA; --cb:#EEF2FF; --cg:rgba(67,56,202,0.09); }
    [data-cat="competitor"] { --cc:#0369A1; --cb:#F0F9FF; --cg:rgba(3,105,161,0.09); }
    [data-cat="cart"]       { --cc:#6D28D9; --cb:#F5F3FF; --cg:rgba(109,40,217,0.09); }
    [data-cat="tools"]      { --cc:#15803D; --cb:#F0FDF4; --cg:rgba(21,128,61,0.09); }
    [data-cat="marketing"]  { --cc:#C2410C; --cb:#FFF7ED; --cg:rgba(194,65,12,0.09); }
    [data-cat="retail"]     { --cc:#0F766E; --cb:#F0FDFA; --cg:rgba(15,118,110,0.09); }

    /* ════════════════════════════════════════════
       HEADER
    ════════════════════════════════════════════ */
    .header {
      background: linear-gradient(150deg, #060D1E 0%, #0B1A3E 55%, #0A1830 100%);
      color: white; position: sticky; top: 0; z-index: 100;
      border-bottom: 1px solid rgba(255,255,255,0.05);
    }
    .header::after {
      content: ''; position: absolute; bottom: 0; left: 0; right: 0; height: 1px;
      background: linear-gradient(90deg, transparent, rgba(99,179,237,0.35), transparent);
    }
    .header-inner {
      max-width: 1280px; margin: 0 auto; padding: 13px 32px;
      display: flex; align-items: center; justify-content: space-between; gap: 20px;
    }
    .header-left { display: flex; align-items: center; gap: 14px; }
    .header-logo {
      width: 40px; height: 40px; border-radius: 11px;
      background: linear-gradient(135deg, #3B82F6, #1E40AF);
      display: flex; align-items: center; justify-content: center; font-size: 20px;
      box-shadow: 0 4px 14px rgba(59,130,246,0.45), inset 0 1px 0 rgba(255,255,255,0.18);
      flex-shrink: 0;
    }
    .header h1 { font-size: 16px; font-weight: 900; letter-spacing: -0.4px; line-height: 1.25; }
    .header-sub { font-size: 10.5px; color: rgba(255,255,255,0.38); margin-top: 2px; }
    .header-right { display: flex; align-items: center; gap: 10px; }
    .header-label {
      background: rgba(59,130,246,0.18); border: 1px solid rgba(59,130,246,0.32);
      color: #93C5FD; padding: 4px 12px; border-radius: 20px;
      font-size: 9.5px; font-weight: 800; letter-spacing: 1.2px; text-transform: uppercase;
    }
    .header-date {
      display: flex; align-items: center; gap: 8px;
      background: rgba(255,255,255,0.07); border: 1px solid rgba(255,255,255,0.11);
      padding: 7px 16px; border-radius: 22px;
      font-size: 13px; font-weight: 700;
    }
    .live-dot {
      width: 7px; height: 7px; border-radius: 50%;
      background: #4ADE80; box-shadow: 0 0 8px #4ADE80;
      animation: pulse-dot 2.5s ease infinite; flex-shrink: 0;
    }
    @keyframes pulse-dot {
      0%, 100% { opacity: 1; box-shadow: 0 0 8px #4ADE80; }
      50%       { opacity: 0.55; box-shadow: 0 0 3px #4ADE80; }
    }

    /* ════════════════════════════════════════════
       NAVIGATION — frosted glass
    ════════════════════════════════════════════ */
    .category-nav {
      background: rgba(255,255,255,0.85);
      backdrop-filter: blur(20px) saturate(180%);
      -webkit-backdrop-filter: blur(20px) saturate(180%);
      border-bottom: 1px solid var(--border);
      position: sticky; top: 66px; z-index: 99;
    }
    .category-nav-inner {
      max-width: 1280px; margin: 0 auto; padding: 9px 32px;
      display: flex; gap: 3px;
      overflow-x: auto; white-space: nowrap; scrollbar-width: none;
    }
    .category-nav-inner::-webkit-scrollbar { display: none; }
    .nav-link {
      display: inline-flex; align-items: center; gap: 5px;
      padding: 6px 13px; border-radius: 8px;
      font-size: 11.5px; font-weight: 600; color: var(--txt-2);
      transition: background 0.15s, color 0.15s; white-space: nowrap;
    }
    .nav-link:hover, .nav-link.active {
      background: var(--cb, #EFF6FF); color: var(--cc, #2563EB); opacity: 1;
    }
    .nav-dot {
      width: 5px; height: 5px; border-radius: 50%;
      background: var(--cc, #2563EB); opacity: 0; transition: opacity 0.15s; flex-shrink: 0;
    }
    .nav-link:hover .nav-dot, .nav-link.active .nav-dot { opacity: 1; }

    /* ════════════════════════════════════════════
       KPI BAR
    ════════════════════════════════════════════ */
    .kpi-bar {
      display: grid; grid-template-columns: repeat(4, 1fr);
      gap: 14px; margin-bottom: 26px;
    }
    .kpi-card {
      background: var(--surface); border: 1px solid var(--border);
      border-radius: var(--r-lg); padding: 18px 20px;
      box-shadow: var(--sh-xs); display: flex; align-items: center; gap: 14px;
      transition: box-shadow 0.2s, transform 0.2s;
    }
    .kpi-card:hover { box-shadow: var(--sh); transform: translateY(-2px); }
    .kpi-icon {
      width: 44px; height: 44px; border-radius: var(--r);
      display: flex; align-items: center; justify-content: center;
      font-size: 22px; flex-shrink: 0;
    }
    .kpi-icon.blue   { background: #EFF6FF; }
    .kpi-icon.green  { background: #F0FDF4; }
    .kpi-icon.purple { background: #F5F3FF; }
    .kpi-icon.amber  { background: #FFFBEB; }
    .kpi-value { font-size: 28px; font-weight: 900; color: var(--txt-1); line-height: 1.1; letter-spacing: -0.5px; }
    .kpi-label { font-size: 11px; color: var(--txt-3); margin-top: 3px; font-weight: 500; }

    /* ════════════════════════════════════════════
       LAYOUT & CARDS
    ════════════════════════════════════════════ */
    .container { max-width: 1280px; margin: 0 auto; padding: 28px 32px; }

    .section-card {
      background: var(--surface);
      border-radius: var(--r-lg);
      box-shadow: var(--sh);
      margin-bottom: 18px;
      border: 1px solid var(--border);
      border-top: 3px solid var(--cc, #2563EB);
      overflow: hidden;
      transition: box-shadow 0.2s ease;
    }
    .section-card:hover { box-shadow: var(--sh-md); }

    .section-header {
      padding: 17px 24px 15px;
      display: flex; align-items: center; gap: 13px;
      border-bottom: 1px solid var(--border-2);
      background: linear-gradient(135deg, var(--cg, rgba(37,99,235,0.06)) 0%, transparent 70%);
    }
    .cat-icon {
      width: 42px; height: 42px; border-radius: 11px;
      background: linear-gradient(135deg, var(--cc), color-mix(in srgb, var(--cc) 70%, #000));
      display: flex; align-items: center; justify-content: center;
      font-size: 20px; flex-shrink: 0;
      box-shadow: 0 4px 12px var(--cg, rgba(37,99,235,0.2));
    }
    .section-title-wrap { flex: 1; }
    .section-title { font-size: 15px; font-weight: 800; color: var(--txt-1); letter-spacing: -0.2px; }
    .section-sub { font-size: 11px; color: var(--txt-3); margin-top: 2px; }
    .section-badge {
      background: var(--cb, #EFF6FF); color: var(--cc, #2563EB);
      border: 1px solid color-mix(in srgb, var(--cc) 18%, transparent);
      padding: 3px 12px; border-radius: 20px;
      font-size: 12px; font-weight: 700; flex-shrink: 0;
    }
    .section-body { padding: 20px 24px; }

    /* ════════════════════════════════════════════
       NEWS ITEMS — editorial style
    ════════════════════════════════════════════ */
    .news-list { list-style: none; }
    .news-item {
      display: flex; gap: 13px;
      padding: 13px 0; border-bottom: 1px solid var(--border-2);
      align-items: flex-start;
    }
    .news-item:first-child { padding-top: 2px; }
    .news-item:last-child { border-bottom: none; padding-bottom: 0; }
    .news-num {
      min-width: 26px; height: 26px; border-radius: 7px;
      background: var(--cg, rgba(37,99,235,0.08));
      color: var(--cc, #2563EB);
      border: 1px solid color-mix(in srgb, var(--cc) 14%, transparent);
      font-size: 10.5px; font-weight: 800;
      display: flex; align-items: center; justify-content: center;
      flex-shrink: 0; margin-top: 2px;
    }
    .news-content { flex: 1; min-width: 0; }
    .news-title {
      font-weight: 700; color: var(--txt-1);
      font-size: 13.5px; line-height: 1.5; margin-bottom: 5px;
    }
    .news-title a { color: inherit; transition: color 0.15s; }
    .news-title a:hover { color: var(--cc, #2563EB); }
    .news-snippet { color: var(--txt-2); font-size: 12px; line-height: 1.7; margin-bottom: 8px; }
    .news-meta { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
    .news-source {
      background: var(--surface-2); border: 1px solid var(--border);
      color: var(--txt-3); padding: 2px 9px; border-radius: 5px;
      font-size: 10px; font-weight: 600;
    }

    /* ════════════════════════════════════════════
       ACTION BLOCK — amber accent
    ════════════════════════════════════════════ */
    .action-block {
      margin-top: 18px;
      background: linear-gradient(135deg, #FFFDF5, #FFFBEB 60%, #FFF8E1);
      border: 1px solid #FCD34D; border-left: 4px solid #F59E0B;
      border-radius: var(--r); padding: 16px 20px;
    }
    .action-title {
      font-size: 10px; font-weight: 800; letter-spacing: 1.3px;
      color: #92400E; margin-bottom: 11px;
      display: flex; align-items: center; gap: 6px; text-transform: uppercase;
    }
    .action-list { list-style: none; }
    .action-item {
      display: flex; gap: 10px; align-items: flex-start;
      padding: 7px 0; font-size: 12.5px; color: #78350F; line-height: 1.55;
    }
    .action-item + .action-item { border-top: 1px solid rgba(245,158,11,0.18); }
    .action-bullet {
      min-width: 22px; height: 22px; border-radius: 6px;
      background: linear-gradient(135deg, #FBBF24, #F59E0B);
      color: white; font-size: 10px; font-weight: 800;
      display: flex; align-items: center; justify-content: center;
      flex-shrink: 0; box-shadow: 0 2px 6px rgba(245,158,11,0.3);
    }

    /* ════════════════════════════════════════════
       ACCORDION
    ════════════════════════════════════════════ */
    details summary {
      list-style: none; cursor: pointer;
      padding: 12px 24px;
      display: flex; align-items: center; justify-content: space-between;
      border-bottom: 1px solid var(--border-2);
      background: var(--surface-2); user-select: none;
      transition: background 0.15s;
    }
    details summary:hover { background: var(--cb, #EFF6FF); }
    details summary::-webkit-details-marker { display: none; }
    details[open] summary { border-bottom-color: var(--border); }
    .summary-label { color: var(--txt-3); font-size: 12px; font-weight: 500; }
    .toggle-icon { color: var(--txt-3); transition: transform 0.25s ease; font-size: 12px; }
    details[open] .toggle-icon { transform: rotate(180deg); }
    .details-body { padding: 20px 24px; }

    /* ════════════════════════════════════════════
       HIGHLIGHTS
    ════════════════════════════════════════════ */
    .highlight-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 9px; }
    .highlight-item {
      background: var(--surface); border: 1px solid #BAE6FD;
      border-left: 3px solid #0EA5E9; border-radius: var(--r-sm);
      padding: 11px 14px; font-size: 12.5px; color: var(--txt-1);
      line-height: 1.55; font-weight: 500;
      transition: box-shadow 0.15s, transform 0.15s;
    }
    .highlight-item:hover { box-shadow: var(--sh-xs); transform: translateY(-1px); }

    /* ════════════════════════════════════════════
       BREAKING NEWS
    ════════════════════════════════════════════ */
    .breaking-banner {
      background: linear-gradient(90deg, #991B1B, #DC2626 50%, #991B1B);
      color: white; padding: 7px 24px;
      font-size: 9.5px; font-weight: 800;
      letter-spacing: 2.5px; text-transform: uppercase;
      display: flex; align-items: center; gap: 10px;
    }
    .breaking-dot {
      width: 7px; height: 7px; border-radius: 50%; background: white;
      animation: pulse-dot 1.5s ease infinite; flex-shrink: 0;
    }

    /* ════════════════════════════════════════════
       IR / METRICS
    ════════════════════════════════════════════ */
    .metric-grid {
      display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
      gap: 12px; margin-bottom: 20px;
    }
    .metric-card {
      background: linear-gradient(135deg, #F0F7FF, white);
      border: 1px solid #DBEAFE; border-radius: var(--r);
      padding: 17px; text-align: center;
      transition: box-shadow 0.15s, transform 0.15s;
    }
    .metric-card:hover { box-shadow: var(--sh); transform: translateY(-2px); }
    .metric-value { font-size: 22px; font-weight: 900; color: #1D4ED8; line-height: 1.1; letter-spacing: -0.5px; }
    .metric-label { font-size: 10px; color: var(--txt-3); margin-top: 5px; font-weight: 500; }
    .metric-trend { font-size: 11.5px; font-weight: 700; margin-top: 6px; }
    .trend-up   { color: #059669; }
    .trend-down { color: #DC2626; }
    .ir-charts { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 20px; }
    .chart-box {
      position: relative; height: 200px; padding: 14px;
      border: 1px solid var(--border); border-radius: var(--r); background: var(--surface-2);
    }
    .ir-table { width: 100%; border-collapse: collapse; font-size: 12px; margin-top: 16px; }
    .ir-table th {
      background: var(--surface-2); padding: 10px 14px; text-align: left;
      font-weight: 700; border-bottom: 2px solid var(--border);
      color: var(--txt-2); font-size: 11px; white-space: nowrap;
    }
    .ir-table td { padding: 10px 14px; border-bottom: 1px solid var(--border-2); vertical-align: top; }
    .ir-table tbody tr:hover td { background: var(--surface-2); }
    .ir-table tbody tr:last-child td { border-bottom: none; }
    .tag-up   { color: #059669; font-weight: 700; }
    .tag-down { color: #DC2626; font-weight: 700; }

    /* ════════════════════════════════════════════
       FOOTER
    ════════════════════════════════════════════ */
    .footer {
      background: #080F22; color: #475569;
      text-align: center; padding: 36px 32px;
      font-size: 12px; margin-top: 40px; line-height: 2.4;
      border-top: 1px solid rgba(255,255,255,0.03);
    }
    .footer-logo { font-size: 28px; margin-bottom: 6px; opacity: 0.7; }
    .footer-brand { color: rgba(255,255,255,0.25); font-weight: 700; font-size: 13px; margin-bottom: 4px; }
    .footer-divider { width: 40px; height: 1px; background: rgba(255,255,255,0.08); margin: 10px auto; }

    /* ════════════════════════════════════════════
       RESPONSIVE
    ════════════════════════════════════════════ */
    @media (max-width: 900px) { .kpi-bar { grid-template-columns: repeat(2, 1fr); } }
    @media (max-width: 768px) {
      .container { padding: 16px; }
      .header-inner { padding: 12px 16px; flex-wrap: wrap; }
      .header h1 { font-size: 15px; }
      .category-nav-inner { padding: 8px 16px; }
      .category-nav { position: relative; top: auto; }
      .ir-charts, .highlight-grid { grid-template-columns: 1fr; }
      .metric-grid { grid-template-columns: repeat(2, 1fr); }
      .kpi-bar { grid-template-columns: repeat(2, 1fr); gap: 10px; }
      .section-header { padding: 14px 18px 12px; }
      .section-body, .details-body { padding: 16px 18px; }
    }
    @media (max-width: 480px) {
      .highlight-grid { grid-template-columns: 1fr; }
      .kpi-bar { grid-template-columns: 1fr 1fr; }
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
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
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
    "news": [{"title":"...","snippet":"...","url":"..."}],
    "metrics": [{"company":"楽天","value":"X.X兆円","growth":"+X.X%"}],
    "chart": {"labels":["楽天","メルカリ","ZOZO","BASE","Amazon"],"revenue":[1000,200,300,50,5000],"growth_pct":[5,10,3,2,8]},
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
- データがない場合はitemsを空配列[]、actionsも空配列[]
- urlはニュースデータのURLをそのまま使用
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
        source_url = item.get("source_url", "")
        href = f"https://{url}" if url and not url.startswith("http") else url
        display_url = source_url if source_url else url
        if display_url.startswith("http"):
            domain = re.sub(r"^https?://(www\.)?", "", display_url).split("/")[0]
        else:
            domain = display_url.split("/")[0] if display_url else "出典"
        title_html = (f'<a href="{href}" target="_blank" rel="noopener">{_esc(item.get("title",""))}</a>'
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
    time.sleep(20)

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

    # KPI バー（収集統計）
    total_news = sum(len(v) for v in news.values())
    cats_covered = len([v for v in news.values() if v])
    kpi_bar = f'''<div class="kpi-bar">
  <div class="kpi-card"><div class="kpi-icon blue">📰</div><div class="kpi-body"><div class="kpi-value">{total_news}</div><div class="kpi-label">収集ニュース数</div></div></div>
  <div class="kpi-card"><div class="kpi-icon green">📂</div><div class="kpi-body"><div class="kpi-value">{cats_covered}</div><div class="kpi-label">カバー分野数</div></div></div>
  <div class="kpi-card"><div class="kpi-icon purple">🤖</div><div class="kpi-body"><div class="kpi-value">AI</div><div class="kpi-label">Gemini自動分析</div></div></div>
  <div class="kpi-card"><div class="kpi-icon amber">🔄</div><div class="kpi-body"><div class="kpi-value">毎朝</div><div class="kpi-label">8:00 JST 自動更新</div></div></div>
</div>'''

    # PythonでHTML組み立て（絶対に欠けない）
    sections = [kpi_bar, render_summary(all_data.get("highlights", []), date_jp)]
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

    print("\n[2/5] ニュース収集（12カテゴリ）...")
    news = collect_all_news(date_str)
    total = sum(len(v) for v in news.values())
    print(f"  → {total}件取得")

    print("\n[3/5] HTML生成（Gemini・JSON方式）...")
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
