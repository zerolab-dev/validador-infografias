# Validador de Infografías CITE

Aplicación Streamlit para contrastar infografías PDF con el Excel oficial de CLIENTES, SERVICIOS y ARTICULACIONES.

## Principios
- El Excel es la fuente oficial.
- La extracción del PDF es independiente: nunca se completa un dato PDF con información del Excel.
- Un dato oficial positivo no extraído del PDF se marca **REVISAR**, no como cero.
- Categorías oficiales sin valor pueden omitirse visualmente en la infografía.

## Ejecución
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Entrada
- 1 Excel `.xlsx` con hojas `CLIENTES`, `SERVICIOS`, `ARTICULACIONES`.
- Uno o múltiples PDF de infografías con la estructura institucional usada en 2026.

## Salida
La aplicación muestra resumen, comparación detallada, tablas reconstruidas exclusivamente desde PDF y observaciones. También genera un Excel con `RESUMEN`, `PDF_CLIENTES`, `PDF_SERVICIOS`, `PDF_ARTICULACIONES`, `COMPARACION` y `ERRORES_Y_OBSERVACIONES`.

## Alcance
El parser está especializado en la estructura de las infografías CITE/UT suministradas. Si cambia sustancialmente la maqueta o las etiquetas, se debe actualizar `src/pdf_reader.py`.
