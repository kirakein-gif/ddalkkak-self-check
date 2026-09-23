from __future__ import annotations

import streamlit as st

from core.detector import (
    BANK,
    OUTSIDE_LEDGER,
    OUTSIDE_STATEMENT,
    SCHOOL_LEDGER,
    UNKNOWN,
    detect_type,
)
from core.models import FileResult
from core.parsers import (
    parse_bank_statement,
    parse_outside_ledger,
    parse_outside_statement,
    parse_school_ledger,
)
from core.reconcile import reconcile
from core.workbook_reader import read_workbook
from outputs.excel_report import build_reconciliation_xlsx

st.set_page_config(page_title="자율적 내부점검 딸깍", page_icon="✅", layout="wide")

st.markdown(
    """
<style>
.block-container {max-width: 1120px; padding-top: 2rem; padding-bottom: 4rem;}
.dd-hero {border:1px solid #d8e7fb; border-radius:18px; padding:28px 30px; background:#fff; margin-bottom:22px;}
.dd-brand {font-size:13px; font-weight:800; letter-spacing:1.2px; color:#2563eb; margin-bottom:7px;}
.dd-title {font-size:32px; font-weight:850; color:#17253a; margin:0 0 8px;}
.dd-desc {font-size:15px; color:#536579; margin:0; line-height:1.7;}
.dd-note {border-radius:12px; padding:14px 16px; background:#f7fafc; color:#3b4b5f; font-size:14px;}
[data-testid="stFileUploader"] {border:1px dashed #9abce9; border-radius:14px; padding:8px;}
</style>
<div class="dd-hero">
  <div class="dd-brand">DDALKKAK · SELF CHECK</div>
  <div class="dd-title">자율적 내부점검 딸깍</div>
  <p class="dd-desc">농협 통장거래내역과 K-에듀파인 자료를 한꺼번에 넣으면 파일명을 바꾸지 않아도 문서 구조를 읽어 자동으로 구분하고 장부와 통장 잔액을 대조합니다.</p>
</div>
""",
    unsafe_allow_html=True,
)

with st.expander("기본 설정", expanded=False):
    fixed_deposit = st.number_input(
        "학교회계 정기예금 금액",
        min_value=0,
        step=1000,
        value=0,
        format="%d",
    )
    st.caption("정기예금이 없으면 0원으로 두세요. 계좌번호는 입력하지 않아도 됩니다.")

st.subheader("1. 점검자료 넣기")
st.markdown(
    '<div class="dd-note">농협과 K-에듀파인에서 내려받은 <b>.xls / .xlsx 파일을 수정하지 말고 그대로</b> 한꺼번에 선택하세요. 파일명은 사용하지 않고 내부 열 구조와 기준일 잔액으로 구분합니다. 법인카드는 월 전체 거래내역 1개를 권장합니다.</div>',
    unsafe_allow_html=True,
)

uploads = st.file_uploader(
    "점검자료 선택",
    type=["xls", "xlsx"],
    accept_multiple_files=True,
    label_visibility="collapsed",
)

if not uploads:
    st.info("자료를 선택하면 파일 종류를 자동으로 확인합니다.")
    st.stop()

file_results: list[FileResult] = []
banks = []
school = None
outside = None
outside_statement = None

for uploaded in uploads:
    try:
        book = read_workbook(uploaded)
        kind = detect_type(book)
        detail = ""

        if kind == BANK:
            parsed = parse_bank_statement(book)
            banks.append(parsed)
            detail = (
                f"계좌 {parsed.account_number or '확인 중'} · "
                f"파일 내 마지막 거래잔액 {parsed.closing_balance or 0:,}원"
            )
        elif kind == SCHOOL_LEDGER:
            school = parse_school_ledger(book)
            detail = f"누계잔액 {school.balance:,}원"
        elif kind == OUTSIDE_LEDGER:
            outside = parse_outside_ledger(book)
            detail = f"총누계잔액 {outside.balance:,}원"
        elif kind == OUTSIDE_STATEMENT:
            outside_statement = parse_outside_statement(book)
            detail = f"출납계산서 잔액 {outside_statement.total_balance:,}원"

        file_results.append(FileResult(uploaded.name, kind, detail=detail))
    except Exception as exc:
        file_results.append(FileResult(uploaded.name, UNKNOWN, error=str(exc)))

st.subheader("2. 자료 자동 확인")
for item in file_results:
    if item.error:
        st.error(f"❗ {item.filename} — {item.error}")
    elif item.detected_type == UNKNOWN:
        st.warning(f"△ {item.filename} — 파일 종류를 자동으로 확인하지 못했습니다.")
    else:
        st.success(f"✓ {item.detected_type} — {item.filename}  ·  {item.detail}")

missing = []
if school is None:
    missing.append("학교회계 현금출납부")
if outside is None:
    missing.append("세입세출외현금 현금출납부")
if outside_statement is None:
    missing.append("세입세출외현금 출납계산서")
if len(banks) < 3:
    missing.append("농협 통장거래내역(학교회계·세외·법인카드)")

if missing:
    st.warning("아직 필요한 자료가 부족합니다: " + ", ".join(missing))
    st.stop()

rec = reconcile(
    banks=banks,
    school=school,
    outside=outside,
    outside_statement=outside_statement,
    fixed_deposit=int(fixed_deposit),
)

st.subheader("3. 자동 대조 결과")
if rec.reference_date:
    st.caption(
        f"점검 기준일: {rec.reference_date:%Y-%m-%d} · "
        "농협의 현재통화잔액이 아니라 기준일의 마지막 거래후잔액을 사용합니다."
    )

cols = st.columns(max(1, len(rec.checks)))
for col, check in zip(cols, rec.checks):
    with col:
        st.metric(
            check.item,
            "일치" if check.ok else "확인 필요",
            f"차이 {check.difference or 0:,}원",
        )

for check in rec.checks:
    icon = "✅" if check.ok else "⚠️"
    st.write(
        f"{icon} **{check.item}**  ·  "
        f"장부 {check.ledger or 0:,}원 / "
        f"통장 {check.bank or 0:,}원 / "
        f"차이 {check.difference or 0:,}원"
    )

if rec.card_checks:
    st.markdown("#### 법인카드 대금결제")
    for card in rec.card_checks:
        icon = "✅" if card.ok else "⚠️"
        st.write(
            f"{icon} {card.date} · "
            f"결제 {card.payment:,}원 · "
            f"결제 후 잔액 {card.balance_after:,}원"
        )
else:
    st.warning("법인카드 대금결제(NH비씨대금) 거래를 찾지 못했습니다.")

if rec.unknown_banks:
    st.warning(
        "기준일 장부잔액과 자동 매칭되지 않은 통장자료가 있습니다. "
        "금액 규모로 억지 추정하지 않고 확인 대상으로 남겼습니다."
    )

st.subheader("4. 결과 받기")
xlsx = build_reconciliation_xlsx(rec)
st.download_button(
    "통장잔액 대조 엑셀 받기",
    data=xlsx,
    file_name="자율적_내부점검_통장잔액대조.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    type="primary",
    use_container_width=True,
)

st.caption(
    "현재 1차 버전은 파일 자동판별·기준일 잔액대조·법인카드 결제후 잔액 확인까지 구현했습니다. "
    "내부점검보고서 PDF와 통장사본 정리 PDF는 제공된 샘플 양식을 기준으로 다음 단계에서 붙입니다."
)
