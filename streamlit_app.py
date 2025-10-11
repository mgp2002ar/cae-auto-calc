
import streamlit as st
from compute import calc_res010, calc_ter030, CalcError

st.set_page_config(page_title="CAE AutoCalc", page_icon="⚡", layout="centered")

st.title("CAE AutoCalc")
st.caption("Calculadora AETOTAL (RES010/TER030) con extracción automática de Ki/Kf. Soporta ZIP y OCR.")

tab1, tab2 = st.tabs(["RES010", "TER030"])

with tab1:
    st.subheader("RES010")
    S = st.text_input("S (m² rehabilitados)", value="1652")
    colz = st.columns(2)
    with colz[0]:
        zona = st.text_input("Zona climática CTE (ej. D3) (opcional)")
    with colz[1]:
        override_G = st.text_input("Override G (opcional, ej. 61)")

    st.write("### Subir archivos")
    files = st.file_uploader("XML/PDF/CSV (puedes subir varios)", type=["xml","pdf","csv"], accept_multiple_files=True)
    zip_up = st.file_uploader("...o subir una carpeta comprimida (.zip)", type=["zip"], accept_multiple_files=False)

    if st.button("Calcular RES010", type="primary"):
        try:
            uploaded = []
            if files:
                for f in files:
                    uploaded.append((f.name.lower(), f.read()))
            zip_bytes = zip_up.read() if zip_up else None
            res = calc_res010(S, zona, override_G, uploaded, zip_bytes)
            st.success("Cálculo realizado")
            st.json(res)
        except CalcError as e:
            st.error(str(e))
        except Exception as e:
            st.exception(e)

with tab2:
    st.subheader("TER030")
    PAnt = st.text_input("PAnt (kW)", value="10")
    PPos = st.text_input("PPos (kW)", value="6")
    t = st.text_input("t (h/año)", value="2000")

    if st.button("Calcular TER030"):
        try:
            res = calc_ter030(PAnt, PPos, t)
            st.success("Cálculo realizado")
            st.json(res)
        except CalcError as e:
            st.error(str(e))
        except Exception as e:
            st.exception(e)
