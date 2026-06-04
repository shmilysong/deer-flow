import re
import unicodedata

_ZERO_WIDTH = re.compile(r'[\u200B\u200C\u200D\uFEFF\u00AD\u2060\u180E]')

_SUSPICIOUS_PINYIN = re.compile(
    r'x[iìíǐī]\s*j[iìíǐī]n\s*p[iìíǐī]n\s*g|'
    r't\s*r\s*u\s*m\s*p|'
    r'x[iìíǐī]\s*d[aàáǎā]\s*d[aàáǎā]',
    re.IGNORECASE
)


def _to_halfwidth(match) -> str:
    return chr(ord(match.group(0)) - 0xFEE0)


def preprocess(text: str) -> tuple[str, bool]:
    if not text:
        return text, False
    suspicious = False

    text = unicodedata.normalize('NFC', text)

    cleaned = _ZERO_WIDTH.sub('', text)
    if cleaned != text:
        suspicious = True
    text = cleaned

    text = re.sub(r'[\uFF01-\uFF5E]', _to_halfwidth, text)

    text = re.sub(r'[\s\-_]{2,}', ' ', text)

    text = re.sub(
        r'\b([a-zA-Z])(\s+[a-zA-Z]){4,}\b',
        lambda m: m.group(0).replace(' ', ''),
        text
    )
    text = text.strip().lower()

    if _SUSPICIOUS_PINYIN.search(text):
        suspicious = True

    return text, suspicious
