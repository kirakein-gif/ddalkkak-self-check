DDALKKAK_CSS = r"""
<style>
:root {
  --dd-blue: #2563eb;
  --dd-blue-2: #1d4ed8;
  --dd-blue-soft: #eef5ff;
  --dd-ink: #17253a;
  --dd-text: #394b61;
  --dd-muted: #6b7c90;
  --dd-line: #dce6f2;
  --dd-soft: #f7f9fc;
  --dd-green: #15803d;
  --dd-green-soft: #edf9f0;
  --dd-red: #b42318;
  --dd-red-soft: #fff1f0;
  --dd-amber: #9a6700;
  --dd-amber-soft: #fff8e6;
}

html, body, [class*="css"] {
  font-family: "Pretendard", "Noto Sans KR", "Malgun Gothic", "맑은 고딕", Arial, sans-serif;
  color: var(--dd-ink);
}

.stApp { background: #f4f7fb; }
.block-container { max-width: 1120px; padding-top: 2rem; padding-bottom: 4rem; }

#MainMenu, footer { visibility: hidden; }
header[data-testid="stHeader"] { background: rgba(244,247,251,.82); }

.dd-hero {
  background: #fff;
  border: 1px solid var(--dd-line);
  border-radius: 20px;
  padding: 30px 32px 26px;
  box-shadow: 0 10px 28px rgba(23,37,58,.05);
  margin-bottom: 18px;
}
.dd-brand { color: var(--dd-blue); font-size: 13px; font-weight: 800; letter-spacing: 1.5px; margin-bottom: 7px; }
.dd-title { color: var(--dd-ink); font-size: 32px; line-height: 1.25; font-weight: 850; letter-spacing: -1px; margin-bottom: 8px; }
.dd-desc { color: var(--dd-muted); font-size: 15px; line-height: 1.75; max-width: 820px; }
.dd-chip-row { display:flex; flex-wrap:wrap; gap:8px; margin-top:16px; }
.dd-chip { background: var(--dd-blue-soft); color: var(--dd-blue-2); border:1px solid #d7e7ff; border-radius:999px; padding:6px 10px; font-size:12px; font-weight:700; }

.dd-step-title { display:flex; align-items:center; gap:10px; margin: 26px 0 10px; }
.dd-step-no { width:27px; height:27px; border-radius:8px; background:var(--dd-blue); color:#fff; display:inline-flex; align-items:center; justify-content:center; font-size:13px; font-weight:800; }
.dd-step-text { font-size:19px; font-weight:800; color:var(--dd-ink); letter-spacing:-.3px; }
.dd-step-help { color:var(--dd-muted); font-size:13px; margin: -4px 0 12px 38px; }

.dd-card { background:#fff; border:1px solid var(--dd-line); border-radius:16px; padding:18px 20px; box-shadow:0 4px 14px rgba(23,37,58,.035); }
.dd-info { background:#f8fbff; border:1px solid #d7e7ff; border-radius:12px; padding:12px 14px; color:var(--dd-text); font-size:13.5px; line-height:1.65; }

.dd-status { border:1px solid var(--dd-line); background:#fff; border-radius:14px; padding:14px 15px; min-height:96px; }
.dd-status-top { display:flex; align-items:center; justify-content:space-between; gap:8px; }
.dd-status-name { font-size:14px; font-weight:800; color:var(--dd-ink); }
.dd-status-badge { font-size:11px; font-weight:800; border-radius:999px; padding:4px 8px; white-space:nowrap; }
.dd-status-ok { background:var(--dd-green-soft); color:var(--dd-green); }
.dd-status-warn { background:var(--dd-amber-soft); color:var(--dd-amber); }
.dd-status-miss { background:#f1f4f8; color:#77869a; }
.dd-status-detail { margin-top:9px; color:var(--dd-muted); font-size:12.5px; line-height:1.5; word-break:break-all; }

.dd-result { background:#fff; border:1px solid var(--dd-line); border-radius:16px; padding:18px; }
.dd-result-ok { border-left:5px solid #22a447; }
.dd-result-bad { border-left:5px solid #d92d20; }
.dd-result-label { color:var(--dd-muted); font-size:12px; font-weight:700; margin-bottom:5px; }
.dd-result-value { font-size:22px; font-weight:850; color:var(--dd-ink); }
.dd-result-sub { color:var(--dd-muted); font-size:12px; margin-top:5px; }

[data-testid="stFileUploader"] { background:#fff; border:1.5px dashed #9fc3f7; border-radius:15px; padding:10px; }
[data-testid="stFileUploader"] section { padding-top: 14px; padding-bottom: 14px; }
[data-testid="stFileUploaderDropzoneInstructions"] span { font-size:14px; }

.stButton > button, .stDownloadButton > button {
  border-radius:10px !important;
  min-height:44px;
  font-weight:800 !important;
  font-size:14px !important;
}
.stButton > button[kind="primary"] { box-shadow:0 7px 18px rgba(37,99,235,.17); }

[data-testid="stMetric"] { background:#fff; border:1px solid var(--dd-line); padding:15px 16px; border-radius:14px; }
[data-testid="stMetricValue"] { font-size:22px; }

[data-testid="stExpander"] { background:#fff; border:1px solid var(--dd-line); border-radius:14px; overflow:hidden; }
[data-testid="stExpander"] summary { font-weight:800; }

label[data-testid="stWidgetLabel"] p { font-size:13px; font-weight:700; color:var(--dd-text); }
.stTextInput input, .stNumberInput input, [data-baseweb="input"] input { font-size:14px; }

.dd-footer { margin-top:28px; text-align:center; color:#8a98aa; font-size:12px; }
</style>
"""


def step_header(no: int, title: str, help_text: str = "") -> str:
    help_html = f'<div class="dd-step-help">{help_text}</div>' if help_text else ""
    return f'<div class="dd-step-title"><span class="dd-step-no">{no}</span><span class="dd-step-text">{title}</span></div>{help_html}'


def status_card(name: str, state: str, detail: str) -> str:
    css = {"ok":"dd-status-ok", "warn":"dd-status-warn", "miss":"dd-status-miss"}.get(state, "dd-status-miss")
    label = {"ok":"확인", "warn":"확인 필요", "miss":"미등록"}.get(state, "미등록")
    return (
        '<div class="dd-status">'
        '<div class="dd-status-top">'
        f'<div class="dd-status-name">{name}</div><span class="dd-status-badge {css}">{label}</span>'
        '</div>'
        f'<div class="dd-status-detail">{detail or "자료를 기다리고 있습니다."}</div>'
        '</div>'
    )
