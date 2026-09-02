/**
 * 案件管理表（新ワークフロー） → マイチャット(Chatwork)リアルタイム通知
 *
 * 「新ワークフロー」シートが以下のタイミングで更新されたら、
 * Gemini APIに「考察」と「承認にあたっての検討事項」を生成させ、
 * Chatworkの自分のマイチャットへ自動投稿する。
 *
 *   (A) 新規申請行の追加（会社名・申請内容が入力された時点）
 *   (B) 2次承認が完了し、最終承認待ちの状態になった時点
 *       （＝最終承認者がこれから承認判断をする直前のタイミング）
 *
 * セットアップ手順は README.md を参照。
 * シークレット（APIキー・トークン）はコードに書かず、
 * 「プロジェクトの設定 > スクリプト プロパティ」に保存すること。
 */

// ── 設定 ──────────────────────────────────────────────
const WORKFLOW_SHEET_NAME = '新ワークフロー';
const HEADER_ROW = 2;          // 1行目はルール文、2行目が列見出し
const RULE_TEXT_CELL = 'A1';   // ワークフロールール／受注ルールが書かれているセル
const GEMINI_MODEL = 'gemini-3.6-flash';

// 記入例・テンプレートとして残っている行の会社名（誤って編集されても通知しない）
const PLACEHOLDER_COMPANY_NAMES = ['株式会社サンプル商事'];

/**
 * 列は固定番号ではなく、見出し行（HEADER_ROW）のテキストから毎回自動で解決する。
 * このシートは列の追加・並び替えが頻繁に起きるため、位置決め打ちにすると
 * すぐに壊れる（実際に何度も壊れた）。見出しの文言さえ変わらなければ動く方式にしている。
 * 見出し文言自体が変わった場合はここを直す。
 */
function resolveColumns_(sheet) {
  const lastCol = sheet.getLastColumn();
  const headers = sheet.getRange(HEADER_ROW, 1, 1, lastCol).getValues()[0]
    .map(function (h) { return String(h).trim(); });

  const indexOf = function (name) {
    const idx = headers.indexOf(name);
    return idx === -1 ? null : idx + 1; // 1始まりの列番号
  };
  // 「承認理由」列は同じ見出しが複数回登場するため、各承認チェック列の
  // 直後にあるものをその承認理由として拾う（無ければnull）。
  const reasonAfter = function (checkColIndex) {
    if (!checkColIndex) return null;
    return headers[checkColIndex] === '承認理由' ? checkColIndex + 1 : null;
  };

  const appr1Check = indexOf('1次 承認');
  const appr2Check = indexOf('2次 承認');
  const finalCheck = indexOf('最終 承認');

  return {
    lastCol: lastCol,
    company: indexOf('会社名'),
    staff: indexOf('弊社担当者'),
    plan: indexOf('商材プラン1'),
    stage: indexOf('ステージ'),
    firstMeetingDate: indexOf('一次商談日'),
    frontPage: indexOf('フロントページ'),
    minutes: indexOf('議事録起票'),
    partnerReg: indexOf('取引先登録申請書'),
    antisocialCheck: indexOf('反社チェック'),
    nda: indexOf('NDA'),
    proposalDate: indexOf('本提案_日付'),
    contractCollect: indexOf('契約書回収'),
    content: indexOf('申請内容'),
    salesApproval: indexOf('セールス 承認'),
    appr1Name: indexOf('1次 承認者'),
    appr1Check: appr1Check,
    appr1Reason: reasonAfter(appr1Check),
    appr2Name: indexOf('2次 承認者'),
    appr2Check: appr2Check,
    appr2Reason: reasonAfter(appr2Check),
    finalName: indexOf('最終 承認者'),
    finalCheck: finalCheck,
  };
}

/**
 * セットアップ用：インストール型 onEdit トリガーを作成する。
 * スクリプトエディタでこの関数を一度だけ手動実行すること。
 */
function setupTrigger() {
  // 既存の同名トリガーを削除してから再作成（二重登録防止）
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'onEditInstallable') {
      ScriptApp.deleteTrigger(t);
    }
  });
  ScriptApp.newTrigger('onEditInstallable')
    .forSpreadsheet(SpreadsheetApp.getActive())
    .onEdit()
    .create();
  Logger.log('インストール型トリガーを作成しました。');
}

/**
 * インストール型 onEdit トリガーのハンドラ本体。
 */
function onEditInstallable(e) {
  try {
    if (!e || !e.range) return;
    const sheet = e.range.getSheet();
    if (sheet.getName() !== WORKFLOW_SHEET_NAME) return;

    const cols = resolveColumns_(sheet);
    const editedFirstRow = e.range.getRow();
    const editedLastRow = e.range.getLastRow();
    const editedFirstCol = e.range.getColumn();
    const editedLastCol = e.range.getLastColumn();

    // ルール文(1行目)・見出し(2行目)は無視。貼り付け等で複数行にまたがる編集にも対応する。
    for (let row = Math.max(editedFirstRow, HEADER_ROW + 1); row <= editedLastRow; row++) {
      processRow_(sheet, row, editedFirstCol, editedLastCol, cols);
    }
  } catch (err) {
    Logger.log('onEditInstallable エラー: ' + err);
  }
}

function processRow_(sheet, row, editedFirstCol, editedLastCol, cols) {
  const props = PropertiesService.getScriptProperties();
  const data = sheet.getRange(row, 1, 1, cols.lastCol).getValues()[0];
  const record = rowToRecord_(data, cols);

  if (PLACEHOLDER_COMPANY_NAMES.indexOf(record.company) !== -1) {
    Logger.log('[SKIP] 記入例/テンプレート行のため通知をスキップ: ' + record.company);
    return;
  }

  const editedCols = [];
  for (let c = editedFirstCol; c <= editedLastCol; c++) editedCols.push(c);

  // (A) 新規申請行の追加：会社名・申請内容が揃った時点で1回だけ通知
  const newTriggerCols = [cols.company, cols.content].filter(function (c) { return !!c; });
  const newKey = 'notified_new_row' + row;
  const isCoreFieldEdited = editedCols.some(function (c) {
    return newTriggerCols.indexOf(c) !== -1;
  });
  if (isCoreFieldEdited && record.company && record.content && !props.getProperty(newKey)) {
    sendWorkflowNotification_(sheet, row, record, 'new');
    props.setProperty(newKey, 'sent:' + new Date().toISOString());
  }

  // (B) 最終承認待ちになった時点：2次承認がTRUEになったタイミングで1回だけ通知
  const finalPendingKey = 'notified_final_pending_row' + row;
  const isAppr2CheckEdited = !!cols.appr2Check && editedCols.indexOf(cols.appr2Check) !== -1;
  if (isAppr2CheckEdited && record.appr2Check === true && !props.getProperty(finalPendingKey)) {
    sendWorkflowNotification_(sheet, row, record, 'final_pending');
    props.setProperty(finalPendingKey, 'sent:' + new Date().toISOString());
  }
}

function rowToRecord_(data, cols) {
  const get = function (idx) { return idx ? data[idx - 1] : ''; };
  const getBool = function (idx) { return idx ? data[idx - 1] === true : false; };

  return {
    company: get(cols.company),
    staff: get(cols.staff),
    plan: get(cols.plan),
    stage: get(cols.stage),
    firstMeetingDate: get(cols.firstMeetingDate),
    frontPage: get(cols.frontPage),
    minutes: get(cols.minutes),
    partnerReg: get(cols.partnerReg),
    antisocialCheck: get(cols.antisocialCheck),
    nda: get(cols.nda),
    proposalDate: get(cols.proposalDate),
    contractCollect: get(cols.contractCollect),
    content: get(cols.content),
    salesApproval: getBool(cols.salesApproval),
    appr1Name: get(cols.appr1Name),
    appr1Check: getBool(cols.appr1Check),
    appr1Reason: get(cols.appr1Reason),
    appr2Name: get(cols.appr2Name),
    appr2Check: getBool(cols.appr2Check),
    appr2Reason: get(cols.appr2Reason),
    finalName: get(cols.finalName),
    finalCheck: getBool(cols.finalCheck),
  };
}

/**
 * シート1行目に書かれたワークフロールール／受注ルールのテキストを取得する（Geminiへの参考情報）。
 */
function getWorkflowRuleText_(sheet) {
  try {
    return String(sheet.getRange(RULE_TEXT_CELL).getValue() || '').trim();
  } catch (err) {
    return '';
  }
}

function sendWorkflowNotification_(sheet, row, record, stage) {
  const rulesText = getWorkflowRuleText_(sheet);
  const linkedTexts = fetchLinkedContents_(record);
  const analysis = generateAnalysisWithGemini_(record, stage, rulesText, linkedTexts);
  const body = buildNotificationBody_(record, stage, analysis, sheet, row);
  postToMyChat_(buildChatworkMessage_(body));
  postTaskToMyChat_(buildTaskBody_(body));
}

/**
 * URLを開いて中身をテキスト化する。取得できない場合（ログイン必須ページ等）はok:falseを返す。
 * NotionのURLは、Notion公式APIが使える場合はそちらを優先する
 * （Notionは画面をJavaScriptで描画するため、単純なHTML取得では中身が読めないため）。
 */
function fetchUrlText_(url) {
  if (!url || typeof url !== 'string' || !/^https?:\/\//i.test(url.trim())) return null;
  const trimmed = url.trim();

  if (isNotionUrl_(trimmed)) {
    const notionToken = PropertiesService.getScriptProperties().getProperty('NOTION_TOKEN');
    if (!notionToken) {
      return { ok: false, note: 'Notionページですが NOTION_TOKEN が未設定のため取得していません' };
    }
    return fetchNotionPageText_(trimmed, notionToken);
  }

  try {
    const resp = UrlFetchApp.fetch(url.trim(), {
      muteHttpExceptions: true,
      followRedirects: true,
    });
    const code = resp.getResponseCode();
    if (code < 200 || code >= 300) {
      return { ok: false, note: 'HTTP ' + code + '（ログインが必要なページの可能性があります）' };
    }

    let raw = resp.getContentText();
    if (raw.length > 200000) raw = raw.slice(0, 200000);

    const stripped = raw
      .replace(/<script[\s\S]*?<\/script>/gi, ' ')
      .replace(/<style[\s\S]*?<\/style>/gi, ' ')
      .replace(/<[^>]+>/g, ' ')
      .replace(/&nbsp;/gi, ' ')
      .replace(/\s+/g, ' ')
      .trim();

    // ログイン画面が200 OKで返るケース（Notion等）を簡易検知
    const loginWallPattern = /(sign in to continue|log in to notion|please log in|please sign in|ログインが必要|ログインしてください)/i;
    if (stripped.length < 200 || loginWallPattern.test(stripped)) {
      return { ok: false, note: 'ログインが必要なページのため内容を取得できませんでした' };
    }

    const truncated = stripped.length > 3000 ? stripped.slice(0, 3000) + '…' : stripped;
    return { ok: true, text: truncated };
  } catch (err) {
    return { ok: false, note: '取得エラー: ' + err };
  }
}

function isNotionUrl_(url) {
  return /notion\.(so|site|com)/i.test(url);
}

/**
 * NotionのURLからページID（32桁のUUID）を抜き出す。
 * 例: https://app.notion.com/p/cyhd/HOME-33a41150c2ab800a8f7dc45805d74345 → 33a41150-c2ab-800a-8f7d-c45805d74345
 */
function extractNotionPageId_(url) {
  const m = url.match(/[0-9a-f]{32}/i);
  if (!m) return null;
  return m[0].replace(/(.{8})(.{4})(.{4})(.{4})(.{12})/, '$1-$2-$3-$4-$5');
}

/**
 * Notion公式APIでページの本文テキストを取得する。
 * 対象ページ（または親ページ）が、あらかじめNotionのインテグレーションに共有されている必要がある。
 */
function fetchNotionPageText_(url, token) {
  const pageId = extractNotionPageId_(url);
  if (!pageId) {
    return { ok: false, note: 'URLからNotionページIDを特定できませんでした' };
  }
  try {
    const texts = [];
    collectNotionBlockText_(pageId, token, texts, 0);
    const joined = texts.join('\n').replace(/[ \t]+/g, ' ').trim();
    if (!joined) {
      return { ok: false, note: 'Notionページの内容が空、またはインテグレーションに共有されていません' };
    }
    const truncated = joined.length > 3000 ? joined.slice(0, 3000) + '…' : joined;
    return { ok: true, text: truncated };
  } catch (err) {
    return { ok: false, note: 'Notion API呼び出しエラー: ' + err };
  }
}

function collectNotionBlockText_(blockId, token, texts, depth) {
  if (depth > 2 || texts.length > 200) return; // 深さ・件数の上限（無限ループ・過大取得防止）
  const url = 'https://api.notion.com/v1/blocks/' + blockId + '/children?page_size=100';
  const resp = UrlFetchApp.fetch(url, {
    method: 'get',
    headers: {
      Authorization: 'Bearer ' + token,
      'Notion-Version': '2022-06-28',
    },
    muteHttpExceptions: true,
  });
  const code = resp.getResponseCode();
  if (code < 200 || code >= 300) {
    throw new Error('HTTP ' + code + ': ' + resp.getContentText());
  }
  const data = JSON.parse(resp.getContentText());
  const results = data.results || [];
  results.forEach(function (block) {
    const richText = block[block.type] && block[block.type].rich_text;
    if (richText && richText.length) {
      texts.push(richText.map(function (t) { return t.plain_text; }).join(''));
    }
    if (block.has_children) {
      collectNotionBlockText_(block.id, token, texts, depth + 1);
    }
  });
}

/**
 * 「フロントページ」「議事録起票」列にURLが入っていれば中身を取得する。
 */
function fetchLinkedContents_(record) {
  return {
    frontPage: fetchUrlText_(record.frontPage),
    minutes: fetchUrlText_(record.minutes),
  };
}

function buildLinkedContentSection_(linkedTexts) {
  const parts = [];
  if (linkedTexts.frontPage) {
    parts.push(
      '【フロントページの内容（自動取得）】\n' +
      (linkedTexts.frontPage.ok ? linkedTexts.frontPage.text : '取得できませんでした（' + linkedTexts.frontPage.note + '）')
    );
  }
  if (linkedTexts.minutes) {
    parts.push(
      '【議事録リンクの内容（自動取得）】\n' +
      (linkedTexts.minutes.ok ? linkedTexts.minutes.text : '取得できませんでした（' + linkedTexts.minutes.note + '）')
    );
  }
  return parts.length ? parts.join('\n\n') + '\n\n' : '';
}

/**
 * Gemini APIで「考察」と「承認にあたっての検討事項」を生成する。
 * 失敗時はルールベースの簡易メッセージにフォールバックする。
 */
function generateAnalysisWithGemini_(record, stage, rulesText, linkedTexts) {
  const apiKey = PropertiesService.getScriptProperties().getProperty('GEMINI_API_KEY');
  const stageLabel = stage === 'new' ? '新規申請' : '2次承認完了・最終承認待ち';

  const prompt =
    'あなたは株式会社サイバーレコードの営業管理部門を支援するアシスタントです。\n' +
    '以下の社内ワークフロー案件1件について、承認者が読む想定で「考察」と「承認にあたっての検討事項」を' +
    '簡潔な日本語で作成してください。\n\n' +
    '【現在のステータス】' + stageLabel + '\n\n' +
    '【案件情報】\n' +
    '会社名: ' + (record.company || '(未記入)') + '\n' +
    '弊社担当者: ' + (record.staff || '(未記入)') + '\n' +
    '商材プラン: ' + (record.plan || '(未記入)') + '\n' +
    'ステージ: ' + (record.stage || '(未記入)') + '\n' +
    '一次商談日: ' + (record.firstMeetingDate || '(未記入)') + '\n' +
    '申請内容: ' + (record.content || '(未記入)') + '\n\n' +
    '【コンプライアンス関連の進捗】\n' +
    '取引先登録申請書: ' + (record.partnerReg || '未対応') + '\n' +
    '反社チェック: ' + (record.antisocialCheck || '未対応') + '\n' +
    'NDA: ' + (record.nda || '未対応') + '\n' +
    '契約書回収: ' + (record.contractCollect || '未対応') + '\n\n' +
    '【承認状況】\n' +
    'セールス承認: ' + (record.salesApproval ? '済' : '未') + '\n' +
    '1次承認: ' + (record.appr1Name || '-') + ' / ' + (record.appr1Check ? '済' : '未') +
      (record.appr1Reason ? '（理由: ' + record.appr1Reason + '）' : '') + '\n' +
    '2次承認: ' + (record.appr2Name || '-') + ' / ' + (record.appr2Check ? '済' : '未') +
      (record.appr2Reason ? '（理由: ' + record.appr2Reason + '）' : '') + '\n' +
    '最終承認: ' + (record.finalName || '-') + ' / ' + (record.finalCheck ? '済' : '未') + '\n\n' +
    (rulesText ? '【社内ルール（参考）】\n' + rulesText + '\n\n' : '') +
    buildLinkedContentSection_(linkedTexts || {}) +
    '【出力ルール】\n' +
    '- 「【考察】」と「【承認にあたっての検討事項】」の2見出しで出力する\n' +
    '- 考察は3〜4行程度：商談・申請内容の背景やリスク、社内ルール上の期限との整合性を中心に書く\n' +
    '- 「フロントページ」「議事録リンク」の内容が取得できている場合は、それも踏まえて考察すること\n' +
    '- リンク内容が「取得できませんでした」となっている場合は、その旨を無視して憶測で補わないこと\n' +
    '- 検討事項は箇条書き2〜4件：承認者が判断前に確認すべき点\n' +
    '  （例：反社チェック／NDA／契約書回収などコンプライアンス項目が未完了でないか、申請内容と条件に矛盾がないか、期限に間に合うか）\n' +
    '- Chatworkにそのまま貼れるプレーンテキストのみ返す（Markdown記号は使わない）\n' +
    '- 憶測で数値や事実を作らない。情報が不足する場合は「情報不足のため要確認」と明記する';

  if (!apiKey) {
    Logger.log('[WARN] GEMINI_API_KEY 未設定のためフォールバックメッセージを使用します。');
    return fallbackAnalysis_(record, stage);
  }

  const url =
    'https://generativelanguage.googleapis.com/v1beta/models/' +
    GEMINI_MODEL + ':generateContent?key=' + apiKey;
  const payload = {
    contents: [{ parts: [{ text: prompt }] }],
    generationConfig: { maxOutputTokens: 4096, temperature: 0.4 },
  };

  try {
    const resp = UrlFetchApp.fetch(url, {
      method: 'post',
      contentType: 'application/json',
      payload: JSON.stringify(payload),
      muteHttpExceptions: true,
    });
    const code = resp.getResponseCode();
    if (code < 200 || code >= 300) {
      Logger.log('[WARN] Gemini API HTTP ' + code + ': ' + resp.getContentText());
      return fallbackAnalysis_(record, stage);
    }
    const data = JSON.parse(resp.getContentText());
    const text = data.candidates && data.candidates[0] &&
      data.candidates[0].content && data.candidates[0].content.parts &&
      data.candidates[0].content.parts[0] && data.candidates[0].content.parts[0].text;
    if (!text) {
      Logger.log('[WARN] Gemini応答にテキストなし: ' + resp.getContentText());
      return fallbackAnalysis_(record, stage);
    }
    return text.trim();
  } catch (err) {
    Logger.log('[WARN] Gemini API呼び出し失敗: ' + err);
    return fallbackAnalysis_(record, stage);
  }
}

function fallbackAnalysis_(record, stage) {
  const stageLabel = stage === 'new' ? '新規申請が起票されました。' : '2次承認が完了し、最終承認待ちです。';
  return (
    '【考察】\n' +
    stageLabel + '（Gemini API未設定または呼び出し失敗のため自動考察は生成されていません）\n\n' +
    '【承認にあたっての検討事項】\n' +
    '・反社チェック／NDA／契約書回収などコンプライアンス項目が完了しているか確認してください\n' +
    '・申請内容と社内ルール（承認権限・期限）との整合性を確認してください'
  );
}

/**
 * 通知本文（タイトルと本文）を組み立てる。メッセージ用・タスク用で共通利用する。
 */
function buildNotificationBody_(record, stage, analysis, sheet, row) {
  const stageTitle = stage === 'new' ? '📝 新規ワークフロー申請' : '🔔 最終承認待ち';
  const ss = SpreadsheetApp.getActive();
  const sheetUrl = ss.getUrl() + '#gid=' + sheet.getSheetId() + '&range=A' + row;
  const approverLine = stage === 'final_pending' && record.finalName
    ? '最終承認者: ' + record.finalName + '\n'
    : '';

  return {
    title: stageTitle + '（' + (record.company || '会社名未記入') + '）',
    lines:
      approverLine +
      '弊社担当者: ' + (record.staff || '-') + '\n' +
      '商材プラン: ' + (record.plan || '-') + '\n' +
      '申請内容: ' + truncate_(record.content || '', 200) + '\n\n' +
      analysis + '\n\n' +
      '▼ 該当行を開く\n' + sheetUrl,
  };
}

function buildChatworkMessage_(body) {
  return '[info][title]' + body.title + '[/title]' + body.lines + '[/info]';
}

function buildTaskBody_(body) {
  return body.title + '\n' + body.lines;
}

function truncate_(text, maxLen) {
  if (!text) return '';
  return text.length > maxLen ? text.slice(0, maxLen) + '…' : text;
}

/**
 * Chatworkの自分のマイチャットへメッセージを投稿する。
 * 必要なスクリプトプロパティ: CHATWORK_TOKEN, MYCHAT_ROOM_ID
 */
function postToMyChat_(message) {
  const props = PropertiesService.getScriptProperties();
  const token = props.getProperty('CHATWORK_TOKEN');
  const roomId = props.getProperty('MYCHAT_ROOM_ID');

  if (!token || !roomId) {
    Logger.log('[SKIP] CHATWORK_TOKEN または MYCHAT_ROOM_ID が未設定のため送信をスキップしました。');
    return;
  }

  const url = 'https://api.chatwork.com/v2/rooms/' + roomId + '/messages';
  try {
    const resp = UrlFetchApp.fetch(url, {
      method: 'post',
      headers: { 'X-ChatWorkToken': token },
      payload: { body: message },
      muteHttpExceptions: true,
    });
    const code = resp.getResponseCode();
    if (code < 200 || code >= 300) {
      Logger.log('[WARN] マイチャット通知失敗 HTTP ' + code + ': ' + resp.getContentText());
    } else {
      Logger.log('[OK] マイチャット通知送信完了');
    }
  } catch (err) {
    Logger.log('[WARN] マイチャット通知失敗: ' + err);
  }
}

/**
 * Chatworkの自分のアカウントIDを取得する（/me、初回のみ呼び出しスクリプトプロパティにキャッシュ）。
 */
function getMyChatworkAccountId_(token) {
  const props = PropertiesService.getScriptProperties();
  const cached = props.getProperty('CHATWORK_ACCOUNT_ID');
  if (cached) return cached;

  try {
    const resp = UrlFetchApp.fetch('https://api.chatwork.com/v2/me', {
      headers: { 'X-ChatWorkToken': token },
      muteHttpExceptions: true,
    });
    if (resp.getResponseCode() < 200 || resp.getResponseCode() >= 300) {
      Logger.log('[WARN] Chatworkアカウント取得失敗 HTTP ' + resp.getResponseCode() + ': ' + resp.getContentText());
      return null;
    }
    const data = JSON.parse(resp.getContentText());
    if (!data.account_id) return null;
    const accountId = String(data.account_id);
    props.setProperty('CHATWORK_ACCOUNT_ID', accountId);
    return accountId;
  } catch (err) {
    Logger.log('[WARN] Chatworkアカウント取得エラー: ' + err);
    return null;
  }
}

/**
 * マイチャットに自分宛てのタスクとして登録する（メッセージ通知と併用）。
 * タスク一覧・バッジに残るため、メッセージだけより見落としにくい。
 * 必要なスクリプトプロパティ: CHATWORK_TOKEN, MYCHAT_ROOM_ID
 */
function postTaskToMyChat_(taskBody) {
  const props = PropertiesService.getScriptProperties();
  const token = props.getProperty('CHATWORK_TOKEN');
  const roomId = props.getProperty('MYCHAT_ROOM_ID');

  if (!token || !roomId) {
    Logger.log('[SKIP] CHATWORK_TOKEN または MYCHAT_ROOM_ID が未設定のためタスク登録をスキップしました。');
    return;
  }

  const accountId = getMyChatworkAccountId_(token);
  if (!accountId) {
    Logger.log('[SKIP] Chatworkアカウント特定に失敗したためタスク登録をスキップしました。');
    return;
  }

  const url = 'https://api.chatwork.com/v2/rooms/' + roomId + '/tasks';
  try {
    const resp = UrlFetchApp.fetch(url, {
      method: 'post',
      headers: { 'X-ChatWorkToken': token },
      payload: { body: taskBody, to_ids: accountId },
      muteHttpExceptions: true,
    });
    const code = resp.getResponseCode();
    if (code < 200 || code >= 300) {
      Logger.log('[WARN] マイチャットタスク登録失敗 HTTP ' + code + ': ' + resp.getContentText());
    } else {
      Logger.log('[OK] マイチャットタスク登録完了');
    }
  } catch (err) {
    Logger.log('[WARN] マイチャットタスク登録失敗: ' + err);
  }
}

/**
 * 動作確認用：指定した行番号・ステージで通知を手動実行する。
 * スクリプトエディタから testNotifyRow(42, 'final_pending') のように直接実行して使う。
 * stage は 'new' または 'final_pending'。
 */
/**
 * 動作確認用：通知を送らず、指定した行の列マッピング結果だけをログに出す。
 * スクリプトエディタから testReadRow(5) のように直接実行して使う。
 */
function testReadRow(row) {
  const sheet = SpreadsheetApp.getActive().getSheetByName(WORKFLOW_SHEET_NAME);
  if (!sheet) {
    Logger.log('[ERROR] シート「' + WORKFLOW_SHEET_NAME + '」が見つかりません。');
    return;
  }
  const cols = resolveColumns_(sheet);
  Logger.log('[DEBUG] 解決した列: ' + JSON.stringify(cols));
  const data = sheet.getRange(row, 1, 1, cols.lastCol).getValues()[0];
  const record = rowToRecord_(data, cols);
  Logger.log(JSON.stringify(record, null, 2));
}

function testNotifyRow(row, stage) {
  const sheet = SpreadsheetApp.getActive().getSheetByName(WORKFLOW_SHEET_NAME);
  const cols = resolveColumns_(sheet);
  const data = sheet.getRange(row, 1, 1, cols.lastCol).getValues()[0];
  const record = rowToRecord_(data, cols);
  sendWorkflowNotification_(sheet, row, record, stage || 'new');
}
