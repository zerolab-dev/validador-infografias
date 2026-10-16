import re
import unicodedata
from pathlib import Path


def normalize_text(text) -> str:
    if text is None:
        return ""
    s = re.sub(r"\s+", " ", str(text).replace("\n", " ").replace("\r", " ")).strip()
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def normalize_cite_name(name: str) -> str:
    s = re.sub(r"\s+", " ", str(name or "")).strip()
    # Normalización mínima: conserva el nombre institucional, solo limpia espacios.
    return s


def cite_key(name: str) -> str:
    s = normalize_text(name)
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s


def cite_name_from_filename(filename: str) -> str:
    stem = Path(filename).stem
    if normalize_text(stem).startswith("infografia pp0093"):
        return "NACIONAL"
    month = r"(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|setiembre|septiembre|octubre|noviembre|diciembre)"
    stem = re.sub(rf"[_\- ]*{month}[_\- ]*20\d{{2}}.*$", "", stem, flags=re.I)
    return normalize_cite_name(stem)


def normalize_number(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        if isinstance(value, float) and value != value:
            return None
        return int(value) if float(value).is_integer() else float(value)
    s = str(value).strip()
    if not s or s.lower() in {"nan", "none", "n/a", "--", "-"}:
        return None
    s = re.sub(r"[^0-9,.-]", "", s)
    if not s:
        return None
    # En estas infografías punto/coma se usan como separador de miles.
    if re.fullmatch(r"\d{1,3}([,.]\d{3})+", s):
        return int(s.replace(",", "").replace(".", ""))
    try:
        return int(s.replace(",", ""))
    except ValueError:
        try:
            return float(s.replace(",", ""))
        except ValueError:
            return None
