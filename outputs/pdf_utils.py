from __future__ import annotations

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT

FONT = "HYGothic-Medium"


def register_korean_font() -> str:
    try:
        pdfmetrics.getFont(FONT)
    except KeyError:
        pdfmetrics.registerFont(UnicodeCIDFont(FONT))
    return FONT


def styles():
    font = register_korean_font()
    ss = getSampleStyleSheet()
    return {
        "body": ParagraphStyle(
            "KBody", parent=ss["BodyText"], fontName=font, fontSize=9.5,
            leading=13, alignment=TA_LEFT, wordWrap="CJK",
        ),
        "body_center": ParagraphStyle(
            "KBodyCenter", parent=ss["BodyText"], fontName=font, fontSize=9.5,
            leading=13, alignment=TA_CENTER, wordWrap="CJK",
        ),
        "small": ParagraphStyle(
            "KSmall", parent=ss["BodyText"], fontName=font, fontSize=8,
            leading=10.5, alignment=TA_LEFT, wordWrap="CJK",
        ),
        "small_center": ParagraphStyle(
            "KSmallCenter", parent=ss["BodyText"], fontName=font, fontSize=8,
            leading=10.5, alignment=TA_CENTER, wordWrap="CJK",
        ),
        "title": ParagraphStyle(
            "KTitle", parent=ss["Title"], fontName=font, fontSize=22,
            leading=26, alignment=TA_CENTER, wordWrap="CJK",
        ),
        "subtitle": ParagraphStyle(
            "KSubtitle", parent=ss["BodyText"], fontName=font, fontSize=10,
            leading=14, alignment=TA_CENTER, wordWrap="CJK",
        ),
    }
