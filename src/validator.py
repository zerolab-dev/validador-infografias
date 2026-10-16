import re
from config.categorias import CLIENTES_CATEGORIES, SERVICIOS_CATEGORIES, ARTICULACIONES_CATEGORIES
from src.normalizer import cite_key, normalize_text


def _find_expected_name(cite_name: str, block: dict):
    if cite_name == "NACIONAL" and "NACIONAL" in block:
        return "NACIONAL"
    key = cite_key(cite_name)
    exact = [n for n in block if cite_key(n) == key]
    if exact: return exact[0]
    # Fallback prudente para diferencias menores de nombre; nunca elige si hay ambigüedad.
    candidates = [n for n in block if key and (key in cite_key(n) or cite_key(n) in key)]
    return candidates[0] if len(candidates) == 1 else None


def _compare_block(cite, block_name, pdf_vals, exp_vals, categories, comparisons, issues):
    for cat in categories:
        ev = exp_vals.get(cat)
        present = cat in pdf_vals
        pv = pdf_vals.get(cat)
        # Categoría con valor oficial 0/ausente puede omitirse visualmente en el PDF.
        if not present and ev in (None, 0):
            state, obs = "COINCIDE", "Categoría sin valor oficial; puede omitirse en la infografía."
        elif not present:
            state, obs = "REVISAR", "El valor esperado existe en Excel pero no pudo extraerse del PDF."
        elif ev in (None, 0) and pv in (None, 0):
            state, obs = "COINCIDE", "Sin valor/valor cero en ambas fuentes."
        elif ev is None and pv not in (None, 0):
            state, obs = "ERROR", "El PDF muestra un valor en una categoría sin valor oficial en Excel."
        elif pv == ev:
            state, obs = "COINCIDE", "Valores idénticos."
        else:
            state, obs = "ERROR", f"Discrepancia: Excel={ev} vs PDF={pv}."
        comparisons.append({"cite": cite, "bloque": block_name, "categoria": cat, "excel": ev, "pdf": pv if present else "NO EXTRAÍDO", "estado": state, "observacion": obs})
        if state != "COINCIDE":
            issues.append({"cite": cite, "tipo": "ERROR NUMÉRICO" if state == "ERROR" else "REVISAR EXTRACCIÓN", "bloque": block_name, "elemento": cat, "descripcion": obs})

    total = pdf_vals.get("Total")
    if total is not None:
        numeric = [pdf_vals.get(c) for c in categories if c != "Total" and pdf_vals.get(c) is not None]
        expected_nonzero = [c for c in categories if c != "Total" and exp_vals.get(c) not in (None, 0)]
        # Solo declara consistencia si todas las categorías oficiales no-cero fueron extraídas.
        if all(c in pdf_vals for c in expected_nonzero):
            s = sum(numeric)
            if s != total:
                issues.append({"cite": cite, "tipo": "ERROR DE CONSISTENCIA INTERNA", "bloque": block_name, "elemento": "Total", "descripcion": f"Suma de categorías PDF ({s}) != Total PDF ({total})."})


def validate_infographic(pdf_data: dict, expected_data: dict) -> dict:
    comparisons, issues = [], []
    cite = pdf_data.get("cite_name", "NO EXTRAÍDO")

    if pdf_data.get("errores_extraccion"):
        for err in pdf_data["errores_extraccion"]:
            issues.append({"cite": cite, "tipo": "ERROR DE EXTRACCIÓN", "bloque": "PDF", "elemento": "Archivo", "descripcion": err})

    period = pdf_data.get("periodo_encontrado", "NO EXTRAÍDO")
    expected_period = expected_data.get("_meta", {}).get("expected_period")
    if not expected_period:
        raise ValueError("El Excel de referencia no contiene un período de corte detectable.")
    if period != expected_period:
        issues.append({"cite": cite, "tipo": "ERROR DE PERÍODO" if period != "NO EXTRAÍDO" else "REVISAR FUENTE", "bloque": "Fuente", "elemento": "Periodo", "descripcion": f"Esperado: {expected_period}. Encontrado: {period}."})

    raw_norm = normalize_text(pdf_data.get("raw_text", ""))
    # Detecta referencias a meses anteriores dentro de notas de no atención; no marca menciones históricas normales.
    if re.search(r"no ha brindado servicios.{0,80}(julio|agosto) 2026", raw_norm):
        issues.append({"cite": cite, "tipo": "REVISAR TEXTO / POSIBLE TEXTO DESACTUALIZADO", "bloque": "Texto", "elemento": "Referencia temporal", "descripcion": f"Se detectó una nota de no atención referida a un mes anterior al corte de {expected_data.get('_meta', {}).get('month', 'reporte')} {expected_data.get('_meta', {}).get('year', '')}."})
    if re.search(r"ene\s*-?\s*set\s*204(?!\d)", raw_norm):
        issues.append({"cite": cite, "tipo": "ERROR DE TEXTO", "bloque": "Texto", "elemento": "Año comparativo", "descripcion": "Se detectó 'Ene-Set 204'; revisar porque probablemente corresponde a 'Ene-Set 2024'."})

    specs = [
        ("clientes", "Clientes", CLIENTES_CATEGORIES),
        ("servicios", "Servicios", SERVICIOS_CATEGORIES),
        ("articulaciones", "Articulaciones", ARTICULACIONES_CATEGORIES),
    ]
    matched_names = {}
    for key, label, cats in specs:
        expected_block = expected_data.get(key, {})
        matched = _find_expected_name(cite, expected_block)
        matched_names[key] = matched
        if not matched:
            # Articulaciones puede no tener fila para CITE sin acciones; no es error por sí mismo.
            if key != "articulaciones":
                issues.append({"cite": cite, "tipo": "REVISAR IDENTIFICACIÓN", "bloque": label, "elemento": "CITE/UT", "descripcion": "No se encontró una coincidencia única del CITE/UT en el Excel."})
            continue
        pdf_vals = pdf_data.get(key, {})
        exp_vals = expected_block[matched]
        if key == "articulaciones" and not pdf_vals and all(exp_vals.get(c) in (None, 0) for c in cats):
            continue
        _compare_block(cite, label, pdf_vals, exp_vals, cats, comparisons, issues)

    # Comparativos históricos de clientes y servicios.
    for key, label in (("clientes", "Clientes históricos"), ("servicios", "Servicios históricos")):
        matched = matched_names.get(key)
        if not matched: continue
        exp = expected_data[key][matched]
        got = pdf_data.get("historicos", {}).get(key, {})
        period_prefix = f"Ene-{expected_data.get('_meta', {}).get('abbr', 'Set')}"
        for period_key in (f"{period_prefix} 2025", f"{period_prefix} 2024"):
            ev, pv = exp.get(period_key), got.get(period_key)
            if ev is None and pv is None:
                state, obs = "COINCIDE", "Sin valor histórico."
            elif pv is None and ev is not None:
                state, obs = "REVISAR", "No se pudo extraer el comparativo histórico del PDF."
            elif ev == pv:
                state, obs = "COINCIDE", "Valores idénticos."
            else:
                state, obs = "ERROR", f"Discrepancia: Excel={ev} vs PDF={pv}."
            comparisons.append({"cite": cite, "bloque": label, "categoria": period_key, "excel": ev, "pdf": pv if pv is not None else "NO EXTRAÍDO", "estado": state, "observacion": obs})
            if state != "COINCIDE":
                issues.append({"cite": cite, "tipo": "ERROR HISTÓRICO" if state == "ERROR" else "REVISAR EXTRACCIÓN", "bloque": label, "elemento": period_key, "descripcion": obs})

    return {"cite": cite, "comparisons": comparisons, "issues": issues, "periodo_valido": period == expected_period}
