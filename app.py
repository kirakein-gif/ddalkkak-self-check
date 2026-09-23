from __future__ import annotations

from datetime import date, datetime
from io import BytesIO
import html

import streamlit as st

from core.detector import BANK, OUTSIDE_LEDGER, OUTSIDE_STATEMENT, SCHOOL_LEDGER, UNKNOWN, detect_type
from core.models import FileResult, ReportSettings
from core.parsers import parse_bank_statement, parse_outside_ledger, parse_outside_statement, parse_school_ledger
from core.pdf_parsers import parse_kedufine_pdf
from core.reconcile import reconcile
from core.workbook_reader import read_workbook
from outputs.bank_report import build_bank_copy_pdf
from outputs.bundle import build_zip
from outputs.excel_report import build_balance_report_xlsx
from outputs.internal_report import build_internal_check_pdf
from ui.styles import DDALKKAK_CSS, status_card, step_header


st.set_page_config(page_title="자율적 내부점검 딸깍", page_icon="✅", layout="wide")
st.markdown(DDALKKAK_CSS, unsafe_allow_html=True)

st.markdown(
    """
<div class="dd-hero">
  <div class="dd-brand">DDALKKAK · SELF CHECK</div>
  <div class="dd-title">자율적 내부점검 딸깍</div>
  <div class="dd-desc">농협 통장거래내역과 K-에듀파인 자료를 한꺼번에 넣으면 파일 종류를 자동으로 구분하고, 기준일 잔액을 대조해 내부점검 결과 3종을 만듭니다.</div>
  <div class="dd-chip-row">
    <span class="dd-chip">파일명 변경 불필요</span>
    <span class="dd-chip">Excel 권장 · K-에듀파인 PDF 지원</span>
    <span class="dd-chip">기준일 거래후잔액 자동 대조</span>
    <span class="dd-chip">결과 3종 일괄 생성</span>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

st.markdown(step_header(1, "점검자료 넣기", "파일 이름을 맞출 필요 없이 내려받은 자료를 그대로 한꺼번에 선택하세요."), unsafe_allow_html=True)
st.markdown(
    """
<div class="dd-info">
<b>권장 준비자료</b> · 농협 학교회계 통장 1개 · 세입세출외현금 통장 1개 · 법인카드 통장 월 전체내역 1개 · 학교회계 현금출납부 · 세입세출외현금 현금출납부 · 세입세출외현금 출납계산서<br>
K-에듀파인 자료는 <b>Excel이 가장 안정적</b>이며, 제공된 형식의 PDF도 읽을 수 있습니다. 법인카드는 기존처럼 12일/27일을 따로 넣어도 되고 월 전체내역 1개를 넣어도 됩니다.
</div>
""",
    unsafe_allow_html=True,
)

uploads = st.file_uploader(
    "점검자료 선택",
    type=["xls", "xlsx", "pdf"],
    accept_multiple_files=True,
    label_visibility="collapsed",
)

if not uploads:
    st.info("자료를 선택하면 6개 항목의 준비 상태를 자동으로 확인합니다.")
    st.markdown('<div class="dd-footer">복잡한 월말 내부점검을 한 번의 흐름으로 · Ddalkkak</div>', unsafe_allow_html=True)
    st.stop()

file_results: list[FileResult] = []
banks = []
candidates: dict[str, list[tuple[object, str, str]]] = {SCHOOL_LEDGER: [], OUTSIDE_LEDGER: [], OUTSIDE_STATEMENT: []}

for uploaded in uploads:
    filename = uploaded.name
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    try:
        if ext == "pdf":
            kind, parsed = parse_kedufine_pdf(uploaded.getvalue(), filename)
            if kind == UNKNOWN or parsed is None:
                file_results.append(FileResult(filename, UNKNOWN, error="지원되는 K-에듀파인 PDF 형식을 확인하지 못했습니다.", source_format="pdf"))
            else:
                detail = f"잔액 {parsed.balance:,}원" if hasattr(parsed, "balance") else f"잔액 {parsed.total_balance:,}원"
                candidates[kind].append((parsed, "pdf", filename))
                file_results.append(FileResult(filename, kind, detail=detail, source_format="pdf"))
        else:
            book = read_workbook(uploaded)
            kind = detect_type(book)
            if kind == BANK:
                parsed = parse_bank_statement(book)
                banks.append(parsed)
                detail = f"계좌 {parsed.account_number or '확인 중'} · 거래 {len(parsed.transactions)}건"
                file_results.append(FileResult(filename, kind, detail=detail, source_format="excel"))
            elif kind == SCHOOL_LEDGER:
                parsed = parse_school_ledger(book)
                candidates[kind].append((parsed, "excel", filename))
                file_results.append(FileResult(filename, kind, detail=f"누계잔액 {parsed.balance:,}원", source_format="excel"))
            elif kind == OUTSIDE_LEDGER:
                parsed = parse_outside_ledger(book)
                candidates[kind].append((parsed, "excel", filename))
                file_results.append(FileResult(filename, kind, detail=f"총누계잔액 {parsed.balance:,}원", source_format="excel"))
            elif kind == OUTSIDE_STATEMENT:
                parsed = parse_outside_statement(book)
                candidates[kind].append((parsed, "excel", filename))
                file_results.append(FileResult(filename, kind, detail=f"출납계산서잔액 {parsed.total_balance:,}원", source_format="excel"))
            else:
                file_results.append(FileResult(filename, UNKNOWN, error="지원되는 자료 형식을 자동 판별하지 못했습니다.", source_format="excel"))
    except Exception as exc:
        msg = str(exc)
        if "xlrd" in msg.lower():
            msg = "구형 농협 .xls 읽기 모듈(xlrd)이 설치되지 않았습니다. 배포환경의 requirements.txt 설치 상태를 확인해 주세요."
        file_results.append(FileResult(filename, UNKNOWN, error=msg, source_format="pdf" if ext == "pdf" else "excel"))

# Prefer Excel over PDF when both are uploaded for the same K-에듀파인 document.
def choose(kind: str):
    items = candidates[kind]
    if not items:
        return None
    items = sorted(items, key=lambda x: 0 if x[1] == "excel" else 1)
    chosen = items[0]
    chosen_name = chosen[2]
    for fr in file_results:
        if fr.detected_type == kind:
            fr.preferred = fr.filename == chosen_name
    return chosen[0]

school = choose(SCHOOL_LEDGER)
outside = choose(OUTSIDE_LEDGER)
outside_statement = choose(OUTSIDE_STATEMENT)

# Early reconciliation is also used to identify the bank roles.
rec = reconcile(banks, school, outside, outside_statement, fixed_deposit=0)

st.markdown(step_header(2, "자료 자동 확인", "학교회계/세외 현금출납부는 파일명이 아니라 표 구조로 구분합니다."), unsafe_allow_html=True)

# Status cards
status_items = [
    ("학교회계 현금출납부", school, getattr(school, "filename", "")),
    ("세입세출외현금 현금출납부", outside, getattr(outside, "filename", "")),
    ("세입세출외현금 출납계산서", outside_statement, getattr(outside_statement, "filename", "")),
    ("학교회계 통장", rec.school_bank, getattr(rec.school_bank, "filename", "")),
    ("세입세출외현금 통장", rec.outside_bank, getattr(rec.outside_bank, "filename", "")),
    ("법인카드 통장", rec.card_banks[0] if rec.card_banks else None, f"{len(rec.card_banks)}개 파일 · 결제거래 {len(rec.card_checks)}건" if rec.card_banks else ""),
]
cols = st.columns(3)
for i, (name, obj, detail) in enumerate(status_items):
    with cols[i % 3]:
        st.markdown(status_card(name, "ok" if obj else "miss", html.escape(detail) if detail else ""), unsafe_allow_html=True)

with st.expander("업로드 파일 판별 내역", expanded=False):
    for item in file_results:
        if item.error:
            st.error(f"{item.filename} · {item.error}")
        else:
            extra = " · 사용" if item.preferred else " · 중복자료(Excel 우선)"
            st.write(f"✓ {item.detected_type} · {item.filename} · {item.source_format.upper()}{extra} · {item.detail}")

missing = []
if school is None: missing.append("학교회계 현금출납부")
if outside is None: missing.append("세입세출외현금 현금출납부")
if outside_statement is None: missing.append("세입세출외현금 출납계산서")
if rec.school_bank is None: missing.append("학교회계 통장")
if rec.outside_bank is None: missing.append("세입세출외현금 통장")
if not rec.card_banks: missing.append("법인카드 통장")

if missing:
    st.warning("아직 자동점검을 시작할 수 없습니다. 필요한 자료: " + ", ".join(missing))
    st.caption("통장은 금액 규모로 억지 추정하지 않고 기준일의 장부잔액과 정확히 일치할 때만 자동 매칭합니다.")
    st.stop()

# Infer report dates.
ref_dt = rec.reference_date or school.as_of or outside.as_of or datetime.now()
generated_dates = [b.generated_at.date() for b in banks if b.generated_at]
inferred_check_date = max(generated_dates) if generated_dates else date.today()

st.markdown(step_header(3, "보고서 설정", "자동점검 항목은 프로그램이 채우고, 사람이 확인해야 하는 항목만 필요하면 입력합니다."), unsafe_allow_html=True)

with st.expander("내부점검표 수기 항목 · 필요할 때만 입력", expanded=False):
    c1, c2, c3 = st.columns(3)
    with c1:
        check_date = st.date_input("점검일자", value=inferred_check_date, key="check_date")
        inspector_title = st.text_input("점검자 직", value="", placeholder="예: 주무관")
        inspector_name = st.text_input("점검자 성명", value="")
        co_manager_name = st.text_input("공동 업무담당자", value="", help="현금출납부 점검 등에 함께 표시할 담당자가 있을 때 입력합니다.")
    with c2:
        confirmer_title = st.text_input("확인자 직", value="", placeholder="예: 행정실장")
        confirmer_name = st.text_input("확인자 성명", value="")
        system_check_count = st.text_input("에듀파인/클린재정 점검 건수", value="")
        evidence_binders = st.text_input("증빙서 편철 권수", value="")
    with c3:
        promotion_count = st.text_input("업무추진비 공개 건수", value="")
        promotion_public_date = st.date_input("업무추진비 공개일", value=None, key="promotion_public_date")
        training_date = st.date_input("업무연찬 일자", value=None, key="training_date")
        training_target = st.text_input("업무연찬 대상", value="전교직원")
        training_content = st.text_input("업무연찬 주요내용", value="감사지적 사례 공유")

with st.expander("학교회계 정기예금", expanded=False):
    fixed_deposit = st.number_input("정기예금 금액", min_value=0, step=1000, value=0, format="%d")
    st.caption("학교회계 잔액에 정기예금이 포함되어 있다면 금액을 입력하세요. 없으면 0원입니다.")

# Re-run matching with fixed deposit.
rec = reconcile(banks, school, outside, outside_statement, fixed_deposit=int(fixed_deposit))
if rec.school_bank is None or rec.outside_bank is None:
    st.error("정기예금 반영 후 통장 자동매칭이 되지 않습니다. 정기예금 금액과 입력자료를 확인해 주세요.")
    st.stop()

st.markdown(step_header(4, "자율적 내부점검 실행", "준비가 끝났습니다. 아래 버튼 한 번으로 잔액대조와 결과 3종을 생성합니다."), unsafe_allow_html=True)

if st.button("자율적 내부점검 실행", type="primary", use_container_width=True):
    settings = ReportSettings(
        check_date=check_date,
        inspector_title=inspector_title.strip(), inspector_name=inspector_name.strip(),
        confirmer_title=confirmer_title.strip(), confirmer_name=confirmer_name.strip(),
        co_manager_name=co_manager_name.strip(), system_check_count=system_check_count.strip(),
        promotion_count=promotion_count.strip(), promotion_public_date=promotion_public_date,
        evidence_binders=evidence_binders.strip(), training_date=training_date,
        training_target=training_target.strip(), training_content=training_content.strip(),
    )
    with st.spinner("자료를 대조하고 결과물을 만드는 중입니다..."):
        internal_pdf = build_internal_check_pdf(rec, settings)
        balance_xlsx = build_balance_report_xlsx(rec, school, outside, outside_statement, int(fixed_deposit))
        bank_pdf = build_bank_copy_pdf(rec)

        month_label = f"{ref_dt.year}년 {ref_dt.month}월"
        date_label = f"{ref_dt.year}.{ref_dt.month}.{ref_dt.day}."
        files = {
            f"자율적 내부점검표({month_label}).pdf": internal_pdf,
            f"회계통장 잔액 현황({date_label} 기준).xlsx": balance_xlsx,
            f"통장잔액({date_label}).pdf": bank_pdf,
        }
        st.session_state["generated_files"] = files
        st.session_state["generated_zip"] = build_zip(files)
        st.session_state["last_rec"] = rec

if "generated_files" in st.session_state:
    rec_view = st.session_state.get("last_rec", rec)
    st.success("점검이 완료되었습니다. 아래 결과를 확인하고 파일을 받으세요.")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(
            f'<div class="dd-result {"dd-result-ok" if rec_view.cashbook_ok else "dd-result-bad"}"><div class="dd-result-label">현금출납부 ↔ 통장잔액</div><div class="dd-result-value">{"일치" if rec_view.cashbook_ok else "확인 필요"}</div><div class="dd-result-sub">학교회계 · 세입세출외현금</div></div>',
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f'<div class="dd-result {"dd-result-ok" if rec_view.card_ok else "dd-result-bad"}"><div class="dd-result-label">법인카드 결제 후 잔액</div><div class="dd-result-value">{"0원 확인" if rec_view.card_ok else "확인 필요"}</div><div class="dd-result-sub">결제거래 {len(rec_view.card_checks)}건</div></div>',
            unsafe_allow_html=True,
        )
    with c3:
        ref_txt = rec_view.reference_date.strftime("%Y-%m-%d") if rec_view.reference_date else "-"
        st.markdown(
            f'<div class="dd-result dd-result-ok"><div class="dd-result-label">점검 기준일</div><div class="dd-result-value">{ref_txt}</div><div class="dd-result-sub">현재통화잔액이 아닌 기준일 거래후잔액 사용</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown("##### 잔액 대조 상세")
    for check in rec_view.checks:
        icon = "✅" if check.ok else "⚠️"
        st.write(f"{icon} **{check.item}** · 장부 {check.ledger or 0:,}원 · 통장 {check.bank or 0:,}원 · 차이 {check.difference or 0:,}원")
    for card in rec_view.card_checks:
        icon = "✅" if card.ok else "⚠️"
        st.write(f"{icon} **법인카드 {card.date}** · 결제 {card.payment:,}원 · 결제 후 잔액 {card.balance_after:,}원")

    st.markdown(step_header(5, "결과 받기", "내부점검보고서 · 잔액현황 Excel · 통장사본 정리본을 각각 또는 한 번에 받을 수 있습니다."), unsafe_allow_html=True)
    files = st.session_state["generated_files"]
    download_cols = st.columns(3)
    for col, (name, data) in zip(download_cols, files.items()):
        mime = "application/pdf" if name.endswith(".pdf") else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        with col:
            st.download_button(name.replace(".pdf", "").replace(".xlsx", "") + " 받기", data=data, file_name=name, mime=mime, use_container_width=True)
    st.download_button(
        "결과 3종 한꺼번에 받기 (ZIP)", data=st.session_state["generated_zip"],
        file_name=f"자율적_내부점검_결과_{ref_dt.year}_{ref_dt.month:02d}.zip",
        mime="application/zip", type="primary", use_container_width=True,
    )

st.markdown('<div class="dd-footer">Ddalkkak · 자율적 내부점검 업무를 준비부터 결과물까지 한 흐름으로</div>', unsafe_allow_html=True)
