import unittest

from core.detector import detect_pdf_text, SCHOOL_LEDGER, OUTSIDE_LEDGER, OUTSIDE_STATEMENT


class PdfDetectionTests(unittest.TestCase):
    def test_pdf_text_detection(self):
        self.assertEqual(detect_pdf_text("현금출납부 일자 제목 채주(납부자) 세부사업명 수입액 지출액 잔액"), SCHOOL_LEDGER)
        self.assertEqual(detect_pdf_text("세입세출외현금 현금출납부 종목 채권자 수입액(1) 지급액(2) 결의번호"), OUTSIDE_LEDGER)
        self.assertEqual(detect_pdf_text("세입세출외현금 출납계산서 전년도이월금액(1) 현년도수납금액(2)"), OUTSIDE_STATEMENT)


if __name__ == "__main__":
    unittest.main()
