/**
 * ワークフロー承認シート → マイチャット(Chatwork)リアルタイム通知
 *
 * 「ワークフロー申請ログ」シートが更新されたタイミング（
 *   (A) 新規申請行の追加
 *   (B) 最終承認(3次承認)が完了したとき
 * ）で、Gemini APIに「考察」と「承認にあたっての検討事項」を生成させ、
 * Chatworkの自分のマイチャットへ自動投稿する。
 *
 * セットアップ手順は README.md を参照。
 * シークレット（APIキー・トークン）はコードに書かず、
 * 「プロジェクトの設定 > スクリプト プロパティ」に保存すること。
 */

// ── 設定（シート名・列番号は実際のスプレッドシートに合わせて調整すること）──
const WORKFLOW_SHEET_NAME = 'ワークフロー申請ログ';
const APPROVAL_MATRIX_SHEET_NAME = '承認権限マトリクス';
const GEMINI_MODEL = 'gemini-2.5-flash-lite';

// 「ワークフロー申請ログ」の列番号（1始まり）
const COL = {
  NO: 1,
  APPLY_DATE: 2,
  APPLICANT: 3,
  COMPANY: 4,
  APPROVAL_TYPE: 5,
  CONTENT: 6,
  MEMO: 7,
  ORDER_MONTH: 8,
  DUE_DATE: 9,
  APPR1_NAME: 10,
  APPR1_CHECK: 11,
  APPR1_TS: 12,
  APPR2_NAME: 13,
  APPR2_CHECK: 14,
  APPR2_TS: 15,
  APPR3_NAME: 16,
  APPR3_CHECK: 17,
  APPR3_TS: 18,
};
const LAST_COL = COL.APPR3_TS;

// 新規申請の完了判定に使う列（このいずれかが編集されたときに判定する）
const NEW_APPLICATION_TRIGGER_COLS = [COL.COMPANY, COL.APPROVAL_TYPE, COL.CONTENT];

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

    const editedFirstRow = e.range.getRow();
    const editedLastRow = e.range.getLastRow();
    const editedFirstCol = e.range.getColumn();
    const editedLastCol = e.range.getLastColumn();

    // ヘッダー行(1行目)は無視。貼り付け等で複数行にまたがる編集にも対応する。
    for (let row = Math.max(editedFirstRow, 2); row <= editedLastRow; row++) {
      processRow_(sheet, row, editedFirstCol, editedLastCol);
    }
  } catch (err) {
    Logger.log('onEditInstallable エラー: ' + err);
  }
}

function processRow_(sheet, row, editedFirstCol, editedLastCol) {
  const props = PropertiesService.getScriptProperties();
  const data = sheet.getRange(row, 1, 1, LAST_COL).getValues()[0];
  const record = rowToRecord_(data);

  const editedCols = [];
  for (let c = editedFirstCol; c <= editedLastCol; c++) editedCols.push(c);

  // (A) 新規申請行の追加：会社名・承認内容・申請内容が揃った時点で1回だけ通知
  const newKey = 'notified_new_row' + row;
  const isCoreFieldEdited = editedCols.some(function (c) {
    return NEW_APPLICATION_TRIGGER_COLS.indexOf(c) !== -1;
  });
  if (
    isCoreFieldEdited &&
    record.company &&
    record.approvalType &&
    record.content &&
    !props.getProperty(newKey)
  ) {
    sendWorkflowNotification_(sheet, row, record, 'new');
    props.setProperty(newKey, 'sent:' + new Date().toISOString());
  }

  // (B) 最終承認(3次承認)完了：3次承認チェックがTRUEになった時点で1回だけ通知
  const finalKey = 'notified_final_row' + row;
  const isFinalCheckEdited = editedCols.indexOf(COL.APPR3_CHECK) !== -1;
  if (isFinalCheckEdited && record.appr3Check === true && !props.getProperty(finalKey)) {
    sendWorkflowNotification_(sheet, row, record, 'final');
    props.setProperty(finalKey, 'sent:' + new Date().toISOString());
  }
}

function rowToRecord_(data) {
  return {
    no: data[COL.NO - 1],
    applyDate: data[COL.APPLY_DATE - 1],
    applicant: data[COL.APPLICANT - 1],
    company: data[COL.COMPANY - 1],
    approvalType: data[COL.APPROVAL_TYPE - 1],
    content: data[COL.CONTENT - 1],
    memo: data[COL.MEMO - 1],
    orderMonth: data[COL.ORDER_MONTH - 1],
    dueDate: data[COL.DUE_DATE - 1],
    appr1Name: data[COL.APPR1_NAME - 1],
    appr1Check: data[COL.APPR1_CHECK - 1] === true,
    appr1Ts: data[COL.APPR1_TS - 1],
    appr2Name: data[COL.APPR2_NAME - 1],
    appr2Check: data[COL.APPR2_CHECK - 1] === true,
    appr2Ts: data[COL.APPR2_TS - 1],
    appr3Name: data[COL.APPR3_NAME - 1],
    appr3Check: data[COL.APPR3_CHECK - 1] === true,
    appr3Ts: data[COL.APPR3_TS - 1],
  };
}

/**
 * 承認権限マトリクスのシート内容をテキスト化して返す（Geminiへの参考情報）。
 * シートが見つからない場合は空文字を返す（通知自体は続行する）。
 */
function getApprovalRulesText_() {
  const ss = SpreadsheetApp.getActive();
  const matrixSheet = ss.getSheetByName(APPROVAL_MATRIX_SHEET_NAME);
  if (!matrixSheet) return '';
  const values = matrixSheet.getDataRange().getValues();
  return values
    .map(function (r) {
      return r.filter(function (v) { return v !== ''; }).join(' | ');
    })
    .filter(function (line) { return line; })
    .join('\n');
}

function sendWorkflowNotification_(sheet, row, record, stage) {
  const rulesText = getApprovalRulesText_();
  const analysis = generateAnalysisWithGemini_(record, stage, rulesText);
  const message = buildChatworkMessage_(record, stage, analysis, sheet, row);
  postToMyChat_(message);
}

/**
 * Gemini APIで「考察」と「承認にあたっての検討事項」を生成する。
 * 失敗時はルールベースの簡易メッセージにフォールバックする。
 */
function generateAnalysisWithGemini_(record, stage, rulesText) {
  const apiKey = PropertiesService.getScriptProperties().getProperty('GEMINI_API_KEY');
  const stageLabel = stage === 'new' ? '新規申請' : '最終承認(3次承認)完了';

  const prompt =
    'あなたは株式会社サイバーレコードの営業管理部門を支援するアシスタントです。\n' +
    '以下の社内ワークフロー申請1件について、担当役員が読む想定で「考察」と「承認にあたっての検討事項」を' +
    '簡潔な日本語で作成してください。\n\n' +
    '【現在のステータス】' + stageLabel + '\n\n' +
    '【申請内容】\n' +
    '会社名: ' + (record.company || '(未記入)') + '\n' +
    '申請者: ' + (record.applicant || '(未記入)') + '\n' +
    '承認内容: ' + (record.approvalType || '(未記入)') + '\n' +
    '申請詳細: ' + (record.content || '(未記入)') + '\n' +
    '受注予定月: ' + (record.orderMonth || '(未記入)') + '\n' +
    '希望納期: ' + (record.dueDate || '(未記入)') + '\n' +
    '1次承認: ' + (record.appr1Name || '-') + ' / ' + (record.appr1Check ? '承認済み' : '未承認') + '\n' +
    '2次承認: ' + (record.appr2Name || '-') + ' / ' + (record.appr2Check ? '承認済み' : '未承認') + '\n' +
    '3次承認: ' + (record.appr3Name || '-') + ' / ' + (record.appr3Check ? '承認済み' : '未承認') + '\n\n' +
    (rulesText
      ? '【社内の承認権限マトリクス（参考）】\n' + rulesText + '\n\n'
      : '') +
    '【出力ルール】\n' +
    '- 「【考察】」と「【承認にあたっての検討事項】」の2見出しで出力する\n' +
    '- 考察は3〜4行程度：値引き率や条件が承認権限マトリクスの基準内か、商談の背景・リスクは何か\n' +
    '- 検討事項は箇条書き2〜4件：承認者が判断前に確認すべき点（例：権限範囲内か、次の承認者は誰か、期限との整合性など）\n' +
    '- Chatworkにそのまま貼れるプレーンテキストのみ返す（Markdown記号は使わない）\n' +
    '- 憶測で数値を作らない。情報が不足する場合は「情報不足のため要確認」と明記する';

  if (!apiKey) {
    Logger.log('[WARN] GEMINI_API_KEY 未設定のためフォールバックメッセージを使用します。');
    return fallbackAnalysis_(record, stage);
  }

  const url =
    'https://generativelanguage.googleapis.com/v1beta/models/' +
    GEMINI_MODEL + ':generateContent?key=' + apiKey;
  const payload = {
    contents: [{ parts: [{ text: prompt }] }],
    generationConfig: { maxOutputTokens: 1024, temperature: 0.4 },
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
  const stageLabel = stage === 'new' ? '新規申請が起票されました。' : '3次承認まで完了しました。';
  return (
    '【考察】\n' +
    stageLabel + '（Gemini API未設定または呼び出し失敗のため自動考察は生成されていません）\n\n' +
    '【承認にあたっての検討事項】\n' +
    '・承認権限マトリクスの範囲内かを個別に確認してください\n' +
    '・次の承認者・期限との整合性を確認してください'
  );
}

function buildChatworkMessage_(record, stage, analysis, sheet, row) {
  const stageTitle = stage === 'new' ? '📝 新規ワークフロー申請' : '✅ 最終承認 完了';
  const ss = SpreadsheetApp.getActive();
  const sheetUrl = ss.getUrl() + '#gid=' + sheet.getSheetId() + '&range=A' + row;

  return (
    '[info][title]' + stageTitle + '（' + (record.company || '会社名未記入') + '）[/title]' +
    '申請者: ' + (record.applicant || '-') + '\n' +
    '承認内容: ' + (record.approvalType || '-') + '\n' +
    '申請詳細: ' + truncate_(record.content || '', 200) + '\n\n' +
    analysis + '\n\n' +
    '▼ 該当行を開く\n' + sheetUrl +
    '[/info]'
  );
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
 * 動作確認用：指定した行番号・ステージで通知を手動実行する。
 * スクリプトエディタから testNotifyRow(36, 'final') のように直接実行して使う。
 */
function testNotifyRow(row, stage) {
  const sheet = SpreadsheetApp.getActive().getSheetByName(WORKFLOW_SHEET_NAME);
  const data = sheet.getRange(row, 1, 1, LAST_COL).getValues()[0];
  const record = rowToRecord_(data);
  sendWorkflowNotification_(sheet, row, record, stage || 'new');
}
