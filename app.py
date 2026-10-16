import pandas as pd
import streamlit as st
from src.excel_reader import load_excel_data, extract_expected_values
from src.pdf_reader import extract_pdf_data
from src.validator import validate_infographic
from src.report_generator import generate_excel_report

st.set_page_config(page_title="Validador de Infografías CITE", page_icon="📊", layout="wide")
st.markdown("""<style>.stButton>button{background:#B72727;color:white;font-weight:700;border:none}.stButton>button:hover{background:#8f1f1f;color:white}</style>""",unsafe_allow_html=True)
st.title("Validador de Infografías CITE")
st.caption("Validación automatizada de información estadística · Excel oficial vs. infografías PDF")

with st.sidebar:
    st.header("Carga de archivos")
    excel_file=st.file_uploader("Excel de referencia",type=["xlsx"])
    pdf_files=st.file_uploader("Infografías PDF",type=["pdf"],accept_multiple_files=True)
    validar=st.button("VALIDAR INFOGRAFÍAS",use_container_width=True)

if "validation" not in st.session_state: st.session_state.validation=None
if validar:
    if not excel_file or not pdf_files:
        st.error("Carga el Excel de referencia y al menos una infografía PDF.")
    else:
        try:
            with st.spinner("Extrayendo y contrastando información..."):
                expected=extract_expected_values(load_excel_data(excel_file))
                expected_period=expected["_meta"]["expected_period"]
                reconstructed=[]; comparisons=[]; issues=[]
                for f in pdf_files:
                    d=extract_pdf_data(f); reconstructed.append(d)
                    v=validate_infographic(d,expected); comparisons.extend(v["comparisons"]); issues.extend(v["issues"])
                st.session_state.validation={"reconstructed":reconstructed,"comparisons":comparisons,"issues":issues,"expected_period":expected_period}
            st.success("Validación completada.")
        except Exception as e:
            st.exception(e)

r=st.session_state.validation
if r:
    comp=pd.DataFrame(r["comparisons"]); issues=pd.DataFrame(r["issues"]); rec=r["reconstructed"]; expected_period=r.get("expected_period", "")
    errors=int((comp["estado"]=="ERROR").sum()) if not comp.empty else 0
    reviews=int((comp["estado"]=="REVISAR").sum()) if not comp.empty else 0
    matches=int((comp["estado"]=="COINCIDE").sum()) if not comp.empty else 0
    source_errors=sum(1 for x in r["issues"] if x.get("tipo") in {"ERROR DE PERÍODO","REVISAR FUENTE"})
    cols=st.columns(6)
    for c,(lab,val) in zip(cols,[("Infografías",len(rec)),("Comparaciones",len(comp)),("Coincidencias",matches),("Errores",errors),("Revisar",reviews),("Fuentes observadas",source_errors)]): c.metric(lab,val)

    t1,t2,t3,t4=st.tabs(["Resumen por infografía","Comparación","Tablas PDF","Errores y observaciones"])
    with t1:
        rows=[]
        for p in rec:
            cite=p["cite_name"]
            ci=issues[issues["cite"]==cite] if not issues.empty else pd.DataFrame()
            cc=comp[comp["cite"]==cite] if not comp.empty else pd.DataFrame()
            err=int((cc["estado"]=="ERROR").sum()) if not cc.empty else 0
            rev=int((cc["estado"]=="REVISAR").sum()) if not cc.empty else 0
            rows.append({"Archivo":p["filename"],"CITE/UT":cite,"Errores":err,"Revisar":rev,"Observaciones":len(ci),"Fuente":"OK" if p["periodo_encontrado"]==expected_period else "ERROR","Estado":"CORRECTO" if err==0 and rev==0 and len(ci)==0 else "OBSERVADO"})
        st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
    with t2:
        show_all=st.checkbox("Mostrar coincidencias",False)
        view=comp if show_all else comp[comp["estado"]!="COINCIDE"]
        f1,f2,f3=st.columns(3)
        cites=["Todos"]+sorted(comp["cite"].dropna().unique().tolist()); blocks=["Todos"]+sorted(comp["bloque"].dropna().unique().tolist()); states=["Todos"]+sorted(comp["estado"].dropna().unique().tolist())
        fc=f1.selectbox("CITE/UT",cites); fb=f2.selectbox("Bloque",blocks); fs=f3.selectbox("Estado",states)
        if fc!="Todos": view=view[view["cite"]==fc]
        if fb!="Todos": view=view[view["bloque"]==fb]
        if fs!="Todos": view=view[view["estado"]==fs]
        st.dataframe(view,use_container_width=True,hide_index=True)
    with t3:
        def table(block):
            rows=[]
            for p in rec: rows.append({"CITE/UT":p["cite_name"],**p.get(block,{})})
            return pd.DataFrame(rows)
        st.markdown("#### CLIENTES PDF"); st.dataframe(table("clientes"),use_container_width=True,hide_index=True)
        st.markdown("#### SERVICIOS PDF"); st.dataframe(table("servicios"),use_container_width=True,hide_index=True)
        st.markdown("#### ARTICULACIONES PDF"); st.dataframe(table("articulaciones"),use_container_width=True,hide_index=True)
    with t4:
        if issues.empty: st.success("No se detectaron errores ni observaciones.")
        else: st.dataframe(issues,use_container_width=True,hide_index=True)

    report=generate_excel_report(r["comparisons"],r["issues"],r["reconstructed"])
    st.download_button("Descargar reporte de validación",report,"Reporte_Validacion_CITE.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True)
else:
    st.info("Carga el Excel maestro y las infografías PDF para iniciar la validación.")
