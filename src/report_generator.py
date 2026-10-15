import io
import pandas as pd
from config.categorias import CLIENTES_CATEGORIES, SERVICIOS_CATEGORIES, ARTICULACIONES_CATEGORIES


def _reconstructed(items, block, cats):
    rows=[]
    for item in items:
        vals=item.get(block,{})
        rows.append({"CITE/UT": item.get("cite_name"), **{c: vals.get(c) for c in cats}})
    return pd.DataFrame(rows)


def generate_excel_report(all_comparisons: list, all_issues: list, pdf_reconstructed_data: list) -> bytes:
    out=io.BytesIO()
    with pd.ExcelWriter(out, engine="xlsxwriter") as writer:
        comp=pd.DataFrame(all_comparisons)
        issues=pd.DataFrame(all_issues)
        resumen=pd.DataFrame({"Indicador":["Infografías procesadas","Comparaciones","Coincidencias","Errores","Revisiones","Observaciones de fuente"],"Valor":[
            len(pdf_reconstructed_data), len(comp), int((comp.get("estado",pd.Series(dtype=str))=="COINCIDE").sum()),
            int((comp.get("estado",pd.Series(dtype=str))=="ERROR").sum()), int((comp.get("estado",pd.Series(dtype=str))=="REVISAR").sum()),
            sum(1 for i in all_issues if i.get("tipo") in {"ERROR DE PERÍODO","REVISAR FUENTE"})]})
        resumen.to_excel(writer,sheet_name="RESUMEN",index=False)
        _reconstructed(pdf_reconstructed_data,"clientes",CLIENTES_CATEGORIES).to_excel(writer,sheet_name="PDF_CLIENTES",index=False)
        _reconstructed(pdf_reconstructed_data,"servicios",SERVICIOS_CATEGORIES).to_excel(writer,sheet_name="PDF_SERVICIOS",index=False)
        _reconstructed(pdf_reconstructed_data,"articulaciones",ARTICULACIONES_CATEGORIES).to_excel(writer,sheet_name="PDF_ARTICULACIONES",index=False)
        (comp if not comp.empty else pd.DataFrame(columns=["cite","bloque","categoria","excel","pdf","estado","observacion"])).to_excel(writer,sheet_name="COMPARACION",index=False)
        (issues if not issues.empty else pd.DataFrame(columns=["cite","tipo","bloque","elemento","descripcion"])).to_excel(writer,sheet_name="ERRORES_Y_OBSERVACIONES",index=False)
        book=writer.book
        head=book.add_format({"bold":True,"bg_color":"#B72727","font_color":"#FFFFFF","text_wrap":True,"align":"center","valign":"vcenter"})
        for ws in writer.sheets.values():
            ws.freeze_panes(1,0); ws.autofilter(0,0,max(0,ws.dim_rowmax),max(0,ws.dim_colmax))
            ws.set_row(0,32,head); ws.set_column(0,0,38); ws.set_column(1,max(1,ws.dim_colmax),22)
    return out.getvalue()
