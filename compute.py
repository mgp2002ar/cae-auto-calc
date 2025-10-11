
from __future__ import annotations
import io, re, csv, zipfile
from typing import List, Optional, Tuple, Dict, Any
from decimal import Decimal, InvalidOperation
from lxml import etree

# PDF extraction
from pdfminer.high_level import extract_text as pdfminer_extract_text
import fitz  # PyMuPDF
try:
    import pytesseract
    from PIL import Image
    OCR_AVAILABLE = True
except Exception:
    OCR_AVAILABLE = False

DECIMAL = Decimal
ALLOWED_EXT = {'.xml', '.pdf', '.csv'}

class CalcError(Exception):
    pass

def norm_decimal(val: Any) -> DECIMAL:
    if val is None: raise CalcError("Valor numérico faltante")
    if isinstance(val, (int, float, DECIMAL)): return DECIMAL(str(val))
    s = str(val).strip().replace(" ", "").replace("·", "").replace(",", ".")
    try: return DECIMAL(s)
    except Exception: raise CalcError(f"No puedo interpretar el número: {val}")

# Tabla G (puedes cargar CSV)
G_VALUES: Dict[Tuple[int, str], int] = {(3, 'D'): 61}

def load_g_table_from_csv(content: bytes) -> None:
    reader = csv.DictReader(io.StringIO(content.decode('utf-8')))
    tmp: Dict[Tuple[int, str], int] = {}
    for row in reader:
        zcv = int(str(row['ZCV']).strip())
        zci = str(row['ZCI']).strip().upper()
        g   = int(str(row['G']).strip())
        tmp[(zcv, zci)] = g
    if not tmp: raise CalcError("CSV de G sin filas válidas")
    G_VALUES.clear(); G_VALUES.update(tmp)

def zcte_to_zcv_zci(zcte: str) -> Tuple[int, str]:
    zcte = zcte.strip().upper()
    m = re.match(r"^([A-E])\s*([1-5])$", zcte)
    if not m: raise CalcError(f"Zona climática CTE no reconocida: {zcte}")
    zci, zcv = m.group(1), int(m.group(2))
    return (zcv, zci)

def get_G_from_zone(zcte: str) -> int:
    zcv, zci = zcte_to_zcv_zci(zcte)
    key = (zcv, zci)
    if key not in G_VALUES: raise CalcError(f"No hay G para ZCV={zcv}/ZCI={zci}. Carga g_table.csv.")
    return G_VALUES[key]

def parse_cee_xml(content: bytes):
    try:
        tree = etree.parse(io.BytesIO(content))
        root = tree.getroot()
    except Exception as e:
        raise CalcError(f"XML inválido: {e}")
    text_all = etree.tostring(root, encoding="unicode")
    # zona
    zcte = None
    candidates_zone = tree.xpath("//*[contains(translate(name(),'abcdefghijklmnopqrstuvwxyz','ABCDEFGHIJKLMNOPQRSTUVWXYZ'),'ZONACLIMAT')]/text()")
    for c in candidates_zone:
        m = re.search(r"([A-E][1-5])", c.strip().upper())
        if m: zcte = m.group(1); break
    if not zcte:
        m = re.search(r"ZONA\s*CLIM[ÁA]TICA.*?([A-E][1-5])", text_all, re.IGNORECASE|re.DOTALL)
        if m: zcte = m.group(1).upper()
    # K
    k_val = None
    k_nodes = tree.xpath("//*[contains(translate(name(),'abcdefghijklmnopqrstuvwxyz','ABCDEFGHIJKLMNOPQRSTUVWXYZ'),'KGLOBAL') or contains(., 'K global')]//text()")
    for t in k_nodes:
        num = re.search(r"([0-9]+[\.,]?[0-9]*)", t)
        if num: k_val = norm_decimal(num.group(1)); break
    if k_val is None:
        m = re.search(r"K\s*(global)?[^0-9]*([0-9]+[\.,]?[0-9]*)\s*W\s*/\s*m²\s*·?\s*K", text_all, re.IGNORECASE)
        if m: k_val = norm_decimal(m.group(2))
    return zcte, k_val

def pdf_extract_text_robust(content: bytes) -> str:
    try:
        txt = pdfminer_extract_text(io.BytesIO(content)) or ""
    except Exception:
        txt = ""
    if txt.strip(): return txt
    # PyMuPDF
    try:
        doc = fitz.open(stream=content, filetype="pdf")
        parts = []
        for page in doc:
            t = page.get_text("text") or ""
            if t: parts.append(t)
        txt2 = "\n".join(parts)
        if txt2.strip(): return txt2
    except Exception:
        pass
    # OCR
    if not OCR_AVAILABLE: return ""
    try:
        doc = fitz.open(stream=content, filetype="pdf")
        parts = []
        for page in doc:
            pix = page.get_pixmap(dpi=200)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            parts.append(pytesseract.image_to_string(img))
        return "\n".join(parts)
    except Exception:
        return ""

def parse_k_zone_from_text(txt: str):
    zcte = None
    m = re.search(r"Zona\s*clim[aá]tica\s*[:\-]?\s*([A-E][1-5])", txt, re.IGNORECASE)
    if m: zcte = m.group(1).upper()
    k_val = None
    m2 = re.search(r"K\s*(global)?\s*(HE1)?\s*[:=]?\s*([0-9]+(?:[\.,][0-9]+)?)\s*W\s*/\s*m²\s*·?\s*K", txt, re.IGNORECASE)
    if m2: k_val = norm_decimal(m2.group(3))
    return zcte, k_val

def collect_from_zip(zip_bytes: bytes) -> List[Tuple[str, bytes]]:
    blobs = []
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for info in zf.infolist():
            if info.is_dir(): continue
            name = info.filename.lower()
            if not any(name.endswith(ext) for ext in ALLOWED_EXT): continue
            with zf.open(info,'r') as fh:
                content = fh.read()
                base = name.split('/')[-1]
                blobs.append((base, content))
    return blobs

def best_from_blobs(blobs: List[Tuple[str, bytes]]) -> Tuple[Optional[str], Optional[DECIMAL]]:
    z, k = None, None
    for name, content in blobs:
        if name.endswith('.xml'):
            try:
                z2, k2 = parse_cee_xml(content)
                z = z or z2; k = k or k2
            except Exception:
                pass
    for name, content in blobs:
        if name.endswith('.pdf') and (z is None or k is None):
            txt = pdf_extract_text_robust(content)
            z2, k2 = parse_k_zone_from_text(txt)
            z = z or z2; k = k or k2
    return z, k

def calc_res010(S: str, zona_climatica_cte: Optional[str], override_G: Optional[str],
                uploaded_files: List[Tuple[str, bytes]], zip_bytes: Optional[bytes] = None):
    blobs = list(uploaded_files)
    if zip_bytes:
        blobs.extend(collect_from_zip(zip_bytes))

    # carga g_table si llega
    for name, content in blobs:
        if name.endswith('.csv') and ('g_table' in name or ('g' in name and any(w in name for w in ['tabla','anexo','coef']))):
            load_g_table_from_csv(content)

    # split
    init_blobs, final_blobs, others = [], [], []
    for name, content in blobs:
        if any(t in name for t in ['inicial','initial','antes']): init_blobs.append((name, content))
        elif any(t in name for t in ['final','despues','después','after']): final_blobs.append((name, content))
        else: others.append((name, content))

    z_i, k_i = best_from_blobs(init_blobs)
    z_f, k_f = best_from_blobs(final_blobs)
    zcte = (zona_climatica_cte.upper().strip() if zona_climatica_cte else None) or z_i or z_f
    Ki, Kf = k_i, k_f
    if (Ki is None or Kf is None) and others:
        z_o, k_o = best_from_blobs(others)
        zcte = zcte or z_o
        if Ki is None and k_o is not None: Ki = k_o
        elif Kf is None and k_o is not None: Kf = k_o

    if Ki is None or Kf is None:
        raise CalcError("No pude extraer Ki/Kf. Sube informes CTE con texto u OCR, o separa los nombres en inicial/final.")

    if override_G and override_G.strip():
        G = norm_decimal(override_G)
    else:
        if not zcte: raise CalcError("Falta la zona climática CTE o el 'override_G'.")
        G = Decimal(str(get_G_from_zone(zcte)))

    S_val = norm_decimal(S)
    if S_val <= 0: raise CalcError("S debe ser > 0")
    delta_k = norm_decimal(Ki) - norm_decimal(Kf)
    if delta_k <= 0: raise CalcError("Ki debe ser > Kf")

    aetotal = (delta_k * S_val * G)
    return {
        "zona_climatica_cte": zcte, "Ki_W_m2K": str(Ki), "Kf_W_m2K": str(Kf),
        "S_m2": str(S_val), "G": str(G),
        "AETOTAL_kWh_anio": f"{aetotal:.2f}", "CAE": f"{aetotal:.0f}"
    }

def calc_ter030(PAnt: str, PPos: str, t: str):
    PAnt_v = norm_decimal(PAnt); PPos_v = norm_decimal(PPos); t_v = norm_decimal(t)
    if PAnt_v <= 0 or PPos_v < 0: raise CalcError("Potencias no válidas")
    if t_v <= 0: raise CalcError("t debe ser > 0")
    if PAnt_v <= PPos_v: raise CalcError("PAnt debe ser > PPos")
    aetotal = (PAnt_v - PPos_v) * t_v
    return {"PAnt_kW": str(PAnt_v), "PPos_kW": str(PPos_v), "t_h_anio": str(t_v),
            "AETOTAL_kWh_anio": f"{aetotal:.2f}", "CAE": f"{aetotal:.0f}"}
