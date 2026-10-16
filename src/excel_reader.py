import pandas as pd
from src.normalizer import normalize_cite_name, normalize_number
from config.categorias import CLIENTES_CATEGORIES, SERVICIOS_CATEGORIES, ARTICULACIONES_CATEGORIES
import re
import unicodedata


MONTH_MAP = {
    "ene": "Enero", "enero": "Enero",
    "feb": "Febrero", "febrero": "Febrero",
    "mar": "Marzo", "marzo": "Marzo",
    "abr": "Abril", "abril": "Abril",
    "may": "Mayo", "mayo": "Mayo",
    "jun": "Junio", "junio": "Junio",
    "jul": "Julio", "julio": "Julio",
    "ago": "Agosto", "agosto": "Agosto",
    "set": "Setiembre", "sep": "Setiembre", "setiembre": "Setiembre", "septiembre": "Setiembre",
    "oct": "Octubre", "octubre": "Octubre",
    "nov": "Noviembre", "noviembre": "Noviembre",
    "dic": "Diciembre", "diciembre": "Diciembre",
}

def _plain(value):
    text = str(value or "")
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c)).lower()

def detect_reporting_period(excel_data: dict) -> dict:
    """Detecta el corte directamente de los encabezados del Excel oficial."""
    candidates = []
    for df in excel_data.values():
        for value in df.iloc[:8, :8].to_numpy().ravel():
            if pd.isna(value):
                continue
            text = _plain(value)
            m = re.search(r"ene(?:ro)?\s*[-–—]\s*(ene|feb|mar|abr|may|jun|jul|ago|set|sep|oct|nov|dic|enero|febrero|marzo|abril|mayo|junio|julio|agosto|setiembre|septiembre|octubre|noviembre|diciembre)\s*(20\d{2})", text, re.I)
            if m:
                candidates.append((m.group(1).lower(), int(m.group(2))))
    if not candidates:
        raise ValueError("No se pudo detectar el período de corte en los encabezados del Excel de referencia.")
    # El encabezado contiene comparativos 2024/2025 y el corte vigente 2026; usamos el año más reciente.
    month_token, year = max(candidates, key=lambda x: x[1])
    month_name = MONTH_MAP[month_token]
    abbr = {"Enero":"Ene","Febrero":"Feb","Marzo":"Mar","Abril":"Abr","Mayo":"May","Junio":"Jun","Julio":"Jul","Agosto":"Ago","Setiembre":"Set","Octubre":"Oct","Noviembre":"Nov","Diciembre":"Dic"}[month_name]
    return {"month": month_name, "abbr": abbr, "year": year, "expected_period": f"Enero - {month_name} {year}"}


def load_excel_data(excel_file) -> dict:
    xls = pd.ExcelFile(excel_file)
    required = {"CLIENTES", "SERVICIOS", "ARTICULACIONES"}
    found = {s.upper(): s for s in xls.sheet_names}
    missing = required - set(found)
    if missing:
        raise ValueError(f"Faltan hojas obligatorias en el Excel: {', '.join(sorted(missing))}")
    return {k.lower(): pd.read_excel(xls, sheet_name=found[k], header=None) for k in required}


def _build_block(df: pd.DataFrame, categories: list[str], historical: bool, period_meta: dict | None = None) -> dict:
    out = {}
    # Nacional: categorías en fila 2 (índice 2); desde columna 3 para clientes/servicios y 1 para articulaciones.
    start = 3 if historical else 1
    national = {cat: normalize_number(df.iloc[2, start+i]) for i, cat in enumerate(categories)}
    if historical:
        prefix = f"Ene-{period_meta['abbr']}" if period_meta else "Ene-Set"
        national[f"{prefix} 2024"] = normalize_number(df.iloc[2, 1])
        national[f"{prefix} 2025"] = normalize_number(df.iloc[2, 2])
    out["NACIONAL"] = national

    # Detalle CITE/UT empieza en fila 6 (índice 6).
    for r in range(6, len(df)):
        raw_name = df.iloc[r, 0]
        if pd.isna(raw_name) or not str(raw_name).strip():
            continue
        name = normalize_cite_name(raw_name)
        vals = {cat: normalize_number(df.iloc[r, start+i]) for i, cat in enumerate(categories)}
        if historical:
            prefix = f"Ene-{period_meta['abbr']}" if period_meta else "Ene-Set"
            vals[f"{prefix} 2024"] = normalize_number(df.iloc[r, 1])
            vals[f"{prefix} 2025"] = normalize_number(df.iloc[r, 2])
        out[name] = vals
    return out


def extract_expected_values(excel_data: dict) -> dict:
    period_meta = detect_reporting_period(excel_data)
    return {
        "_meta": period_meta,
        "clientes": _build_block(excel_data["clientes"], CLIENTES_CATEGORIES, True, period_meta),
        "servicios": _build_block(excel_data["servicios"], SERVICIOS_CATEGORIES, True, period_meta),
        "articulaciones": _build_block(excel_data["articulaciones"], ARTICULACIONES_CATEGORIES, False),
    }
