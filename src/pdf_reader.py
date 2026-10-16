import io
import re
import fitz
from config.categorias import CLIENTES_CATEGORIES, SERVICIOS_CATEGORIES, ARTICULACIONES_CATEGORIES
from src.normalizer import cite_name_from_filename, normalize_number, normalize_text

# Patrones tolerantes a saltos de línea del texto extraído por PyMuPDF.
PATTERNS = {
    "Persona jurídica": r"PERSONA\s+JUR[IÍ]DICA",
    "Persona natural con negocio": r"PERSONA\s+NATURAL\s+CON\s+NEGOCIO",
    "Asociación / cooperativa": r"ASOCIACI[ÓO]N\s*/?\s*COOPERATIVA",
    "Emprendedor": r"EMPRENDEDOR",
    "Academia": r"ACADEMIA",
    "Otros": r"OTROS",
    "Asistencia técnica": r"ASISTENCIA\s+T[ÉE]CNICA",
    "Diseño y desarrollo de productos": r"DISE[ÑN]O\s+Y\s+DESARROLLO\s+DE\s+PRODUCTOS?",
    "Soporte productivo": r"SOPORTE\s+PRODUCTIVO",
    "Ensayos de laboratorio": r"ENSAYOS\s+DE\s+LABORATORIO",
    "Capacitación": r"CAPACITACI[ÓO]N",
    "Certificación de competencias laborales": r"CERTIFICACI[ÓO]N\s+DE\s+COMPETENCIAS\s+LABORALES",
    "Información tecnológica especializada": r"INFORMACI[ÓO]N\s+TECNOL[ÓO]GICA\s+ESPECIALIZADA",
    "Promoción de I+D+i": r"PROMOCI[ÓO]N\s+I\s*\+\s*D\s*\+\s*I",
    "Articulación comercial productiva": r"ARTICULACI[ÓO]N\s+COMERCIAL\s+PRODUCTIVA",
    "Participación en el desarrollo de normas técnicas u hojas de ruta nacionales": r"PARTICIPACI[ÓO]N\s+EN\s+EL\s+DESARROLLO\s+DE\s+NORMAS\s+T[ÉE]CNICAS\s+U\s+HOJAS\s+DE\s+RUTA\s+NACIONALES",
    "Acciones de coordinación con actores de investigación, desarrollo e innovación, ferias y visitas guiadas": r"ACCIONES\s+DE\s+COORDINACI[ÓO]N\s+CON\s+ACTORES\s+DE\s+INVESTIGACI[ÓO]N,?\s+DESARROLLO\s+E\s+INNOVACI[ÓO]N,?\s+FERIAS\s+Y\s+VISITAS\s+GUIADAS",
    "Participación en la elaboración de perfil ocupacional y/o estándares de competencia laboral": r"PARTICIPACI[ÓO]N\s+EN\s+LA\s+ELABORACI[ÓO]N\s+DE\s+PERFIL\s+OCUPACIONAL\s+Y/O\s+EST[ÁA]NDARES\s+DE\s+COMPETENCIA\s+LABORAL",
    "Acciones de articulación de la Red CITE": r"ACCIONES\s+DE\s+ARTICULACI[ÓO]N\s+DE\s+LA\s+RED\s+CITE",
    "Participación como entidad asociada o co-ejecutora en proyectos no formulados por los CITE/UT": r"PARTICIPACI[ÓO]N\s+COMO\s+ENTIDAD\s+ASOCIADA\s+O\s+CO-?EJECUTORA\s+EN\s+PROYECTOS\s+NO\s+FORMULADOS\s+POR\s+LOS\s+CITE/UT",
}


def _read_bytes(pdf_file):
    if hasattr(pdf_file, "getvalue"):
        return pdf_file.getvalue()
    if hasattr(pdf_file, "seek"):
        pdf_file.seek(0)
    if hasattr(pdf_file, "read"):
        return pdf_file.read()
    if isinstance(pdf_file, (bytes, bytearray)):
        return bytes(pdf_file)
    with open(pdf_file, "rb") as f:
        return f.read()


def _extract_category(text: str, category: str):
    pat = PATTERNS[category]
    # El valor numérico está inmediatamente después de la etiqueta en la capa de texto.
    m = re.search(pat + r"\s*([0-9][0-9,.]*)", text, flags=re.I | re.S)
    return normalize_number(m.group(1)) if m else None


def _source_and_period(text: str):
    source = "NO EXTRAÍDO"
    for line in [x.strip() for x in text.splitlines() if x.strip()]:
        nline = normalize_text(line)
        if "registro administrativo cite" in nline or "registros administrativos cite" in nline:
            source = line
            break
    if source == "NO EXTRAÍDO":
        return source, "NO EXTRAÍDO"

    n = normalize_text(source)
    months = [
        ("enero", "Enero"), ("febrero", "Febrero"), ("marzo", "Marzo"),
        ("abril", "Abril"), ("mayo", "Mayo"), ("junio", "Junio"),
        ("julio", "Julio"), ("agosto", "Agosto"),
        ("setiembre", "Setiembre"), ("septiembre", "Setiembre"),
        ("octubre", "Octubre"), ("noviembre", "Noviembre"), ("diciembre", "Diciembre"),
    ]
    year_match = re.search(r"20\d{2}", n)
    year = year_match.group(0) if year_match else None
    found = [(token, label) for token, label in months if token in n]
    if year and "enero" in n:
        # El último mes mencionado en la fuente es el corte acumulado.
        order = [x[0] for x in months]
        end = max(found, key=lambda x: order.index(x[0]))[1] if found else None
        if end:
            return source, f"Enero - {end} {year}"
    if year and found:
        return source, f"{found[-1][1]} {year}"
    return source, source


def _timeline(text: str):
    """Captura la secuencia visual de totales y comparativos, incluyendo '--'."""
    matches = re.findall(r"(?m)^\s*(--|[0-9][0-9,.]*)\s*\n\s*Ene\s*-?\s*(Ene|Feb|Mar|Abr|May|Jun|Jul|Ago|Set|Sep|Oct|Nov|Dic)\s*(\d{3,4})\s*$", text, flags=re.I)
    return [(normalize_number(v), abbr.title(), y) for v, abbr, y in matches]

def extract_pdf_data(pdf_file) -> dict:
    filename = getattr(pdf_file, "name", None) or (str(pdf_file).split("/")[-1] if isinstance(pdf_file, str) else "desconocido.pdf")
    result = {
        "filename": filename, "cite_name": cite_name_from_filename(filename),
        "periodo_encontrado": "NO EXTRAÍDO", "fuente_texto": "NO EXTRAÍDO",
        "clientes": {}, "servicios": {}, "articulaciones": {},
        "historicos": {"clientes": {}, "servicios": {}},
        "raw_text": "", "errores_extraccion": [],
    }
    try:
        doc = fitz.open(stream=_read_bytes(pdf_file), filetype="pdf")
        text = "\n".join(page.get_text("text") for page in doc)
        result["raw_text"] = text
        result["fuente_texto"], result["periodo_encontrado"] = _source_and_period(text)

        for cat in CLIENTES_CATEGORIES[:-1]:
            v = _extract_category(text, cat)
            if v is not None: result["clientes"][cat] = v
        for cat in SERVICIOS_CATEGORIES[:-1]:
            v = _extract_category(text, cat)
            if v is not None: result["servicios"][cat] = v
        for cat in ARTICULACIONES_CATEGORIES[:-1]:
            v = _extract_category(text, cat)
            if v is not None: result["articulaciones"][cat] = v

        timeline = _timeline(text)
        if result["cite_name"] == "NACIONAL":
            # Maqueta nacional: clientes 2026, articulaciones 2026, clientes 2025/2024, servicios 2026/2025/2024.
            if len(timeline) >= 1: result["clientes"]["Total"] = timeline[0][0]
            if len(timeline) >= 2: result["articulaciones"]["Total"] = timeline[1][0]
            if len(timeline) >= 3: result["historicos"]["clientes"][f"Ene-{timeline[2][1]} 2025"] = timeline[2][0]
            if len(timeline) >= 4: result["historicos"]["clientes"][f"Ene-{timeline[3][1]} 2024"] = timeline[3][0]
            if len(timeline) >= 5: result["servicios"]["Total"] = timeline[4][0]
            if len(timeline) >= 6: result["historicos"]["servicios"][f"Ene-{timeline[5][1]} 2025"] = timeline[5][0]
            if len(timeline) >= 7: result["historicos"]["servicios"][f"Ene-{timeline[6][1]} 2024"] = timeline[6][0]
        else:
            # CITE/UT: dentro de cada año, los dos primeros valores son Clientes y Servicios; un tercer 2026 es Articulaciones.
            by_year = {}
            for value, _abbr, year in timeline:
                by_year.setdefault(year, []).append((value, _abbr))
            y26 = by_year.get("2026", [])
            y25 = by_year.get("2025", [])
            y24 = by_year.get("2024", [])
            y204 = by_year.get("204", [])  # tolera el typo editorial "Ene-Set 204" para no perder el valor
            if len(y26) >= 1: result["clientes"]["Total"] = y26[0][0]
            if len(y26) >= 2: result["servicios"]["Total"] = y26[1][0]
            if len(y26) >= 3: result["articulaciones"]["Total"] = y26[2][0]
            if len(y25) >= 1: result["historicos"]["clientes"][f"Ene-{y25[0][1]} 2025"] = y25[0][0]
            if len(y25) >= 2: result["historicos"]["servicios"][f"Ene-{y25[1][1]} 2025"] = y25[1][0]
            if y204:
                result["historicos"]["clientes"][f"Ene-{y204[0][1]} 2024"] = y204[0][0]
                if len(y24) >= 1: result["historicos"]["servicios"][f"Ene-{y24[0][1]} 2024"] = y24[0][0]
            else:
                if len(y24) >= 1: result["historicos"]["clientes"][f"Ene-{y24[0][1]} 2024"] = y24[0][0]
                if len(y24) >= 2: result["historicos"]["servicios"][f"Ene-{y24[1][1]} 2024"] = y24[1][0]


        # Si el bloque de articulaciones no aparece, se deja vacío: no se inventan ceros.
        if "acciones de articulacion" not in normalize_text(text):
            result["articulaciones"] = {}
    except Exception as e:
        result["errores_extraccion"].append(f"{type(e).__name__}: {e}")
    return result
