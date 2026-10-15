import pandas as pd
from src.normalizer import normalize_cite_name, normalize_number
from config.categorias import CLIENTES_CATEGORIES, SERVICIOS_CATEGORIES, ARTICULACIONES_CATEGORIES


def load_excel_data(excel_file) -> dict:
    xls = pd.ExcelFile(excel_file)
    required = {"CLIENTES", "SERVICIOS", "ARTICULACIONES"}
    found = {s.upper(): s for s in xls.sheet_names}
    missing = required - set(found)
    if missing:
        raise ValueError(f"Faltan hojas obligatorias en el Excel: {', '.join(sorted(missing))}")
    return {k.lower(): pd.read_excel(xls, sheet_name=found[k], header=None) for k in required}


def _build_block(df: pd.DataFrame, categories: list[str], historical: bool) -> dict:
    out = {}
    # Nacional: categorías en fila 2 (índice 2); desde columna 3 para clientes/servicios y 1 para articulaciones.
    start = 3 if historical else 1
    national = {cat: normalize_number(df.iloc[2, start+i]) for i, cat in enumerate(categories)}
    if historical:
        national["Ene-Set 2024"] = normalize_number(df.iloc[2, 1])
        national["Ene-Set 2025"] = normalize_number(df.iloc[2, 2])
    out["NACIONAL"] = national

    # Detalle CITE/UT empieza en fila 6 (índice 6).
    for r in range(6, len(df)):
        raw_name = df.iloc[r, 0]
        if pd.isna(raw_name) or not str(raw_name).strip():
            continue
        name = normalize_cite_name(raw_name)
        vals = {cat: normalize_number(df.iloc[r, start+i]) for i, cat in enumerate(categories)}
        if historical:
            vals["Ene-Set 2024"] = normalize_number(df.iloc[r, 1])
            vals["Ene-Set 2025"] = normalize_number(df.iloc[r, 2])
        out[name] = vals
    return out


def extract_expected_values(excel_data: dict) -> dict:
    return {
        "clientes": _build_block(excel_data["clientes"], CLIENTES_CATEGORIES, True),
        "servicios": _build_block(excel_data["servicios"], SERVICIOS_CATEGORIES, True),
        "articulaciones": _build_block(excel_data["articulaciones"], ARTICULACIONES_CATEGORIES, False),
    }
