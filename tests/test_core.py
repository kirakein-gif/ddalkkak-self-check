from datetime import datetime
import unittest

from core.detector import SCHOOL_LEDGER, OUTSIDE_LEDGER, OUTSIDE_STATEMENT, detect_type
from core.models import BankStatement, LedgerSummary, OutsideCashStatement, Transaction, WorkbookData
from core.reconcile import reconcile


class CoreTests(unittest.TestCase):
    def test_detects_ledgers_by_structure_not_filename(self):
        school = WorkbookData("anything.xlsx", {"현금출납부": [["일자","제목","채주","세부사업명","세부항목명","원가비목","수입액","지출액","잔액"]]})
        outside = WorkbookData("anything.xlsx", {"현금출납부": [["년 월 일","종목","제목","채권자","수입액(1)","지급액(2)","잔액(1)-(2)","결의번호"]]})
        statement = WorkbookData("anything.xlsx", {"x": [["전년도이월금액(1)","현년도수납금액(2)","계(1+2)","세외종목","반환금액(3)","잔액(1+2-3)"]]})
        self.assertEqual(detect_type(school), SCHOOL_LEDGER)
        self.assertEqual(detect_type(outside), OUTSIDE_LEDGER)
        self.assertEqual(detect_type(statement), OUTSIDE_STATEMENT)

    def test_reference_date_transaction_balance_wins_over_current_balance(self):
        ref = datetime(2026, 8, 31)
        school = LedgerSummary("s", "school", 1000, 500, 500, ref)
        outside = LedgerSummary("o", "outside", 300, 200, 100, ref)
        statement = OutsideCashStatement("c", 100, as_of=ref)
        school_bank = BankStatement(
            "school.xls", current_balance=9999,
            transactions=[
                Transaction(datetime(2026, 9, 1, 9), deposit=10, balance=510),
                Transaction(datetime(2026, 8, 31, 17), withdrawal=20, balance=500),
            ],
        )
        outside_bank = BankStatement(
            "outside.xls", current_balance=1,
            transactions=[Transaction(datetime(2026, 8, 31, 9), deposit=5, balance=100)],
        )
        card = BankStatement(
            "card.xls",
            transactions=[Transaction(datetime(2026, 8, 27, 17), withdrawal=200, balance=0, description="NH비씨대금")],
        )
        rec = reconcile([school_bank, outside_bank, card], school, outside, statement)
        self.assertTrue(rec.cashbook_ok)
        self.assertTrue(rec.card_ok)
        self.assertEqual(rec.school_bank.filename, "school.xls")
        self.assertEqual(rec.outside_bank.filename, "outside.xls")

    def test_school_account_can_be_identified_by_elimination_then_fixed_deposit(self):
        ref = datetime(2026, 8, 31)
        school = LedgerSummary("s", "school", 2000, 1000, 1000, ref)
        outside = LedgerSummary("o", "outside", 300, 200, 100, ref)
        statement = OutsideCashStatement("c", 100, as_of=ref)
        school_bank = BankStatement("school.xls", transactions=[Transaction(ref, balance=700)])
        outside_bank = BankStatement("outside.xls", transactions=[Transaction(ref, balance=100)])
        rec0 = reconcile([school_bank, outside_bank], school, outside, statement, fixed_deposit=0)
        self.assertIsNotNone(rec0.school_bank)
        self.assertFalse(rec0.cashbook_ok)
        rec = reconcile([school_bank, outside_bank], school, outside, statement, fixed_deposit=300)
        self.assertTrue(rec.cashbook_ok)


if __name__ == "__main__":
    unittest.main()
