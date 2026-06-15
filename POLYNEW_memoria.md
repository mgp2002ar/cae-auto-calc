# POLYNEW — Memoria completa del proyecto

> Guardado el 15/06/2026. Conversación con Claude Code.
> Usuario: Marcos Poggi (poggimarcos7s@gmail.com)

---

## 1. QUÉ ES POLYNEW

Competidor mejorado de **PolyBoard 7** (CAD de muebles de tablero) y **OptiCut 6** (optimizador de corte de paneles) de Boole & Partners. El objetivo NO es copiar código, solo entender conceptos, modelos de datos y funcionalidad para construir algo mejor.

---

## 2. VISIÓN DEL PRODUCTO

### Módulos planificados

| Módulo | Descripción |
|--------|-------------|
| **Motor de corte** | Algoritmo guillotina 2 etapas + FFD + refinement |
| **Generador de muebles** | IA por voz/texto → diseño 3D de mueble |
| **Medidas AR** | ARKit/LiDAR (iPhone) para medir espacios sin cinta métrica |
| **Análisis estructural** | Deflexión de vigas, normas EN 14749 / EN 16122 |
| **Despiece automático** | Lista de paneles con cantos, materiales, herrajes |
| **Exportación a proveedor** | Envío de orden de corte a proveedor de tableros |
| **Manual de montaje IA** | Instrucciones tipo IKEA, SVG por paso, generadas por Claude |
| **Código QR en paneles** | Cada panel tiene QR → paso de montaje exacto |
| **Calculadora de precio** | Oculta hasta el pago |
| **Marketplace carpinteros** | Red de autónomos, GPS tracking, escrow pago, valoraciones |

---

## 3. INGENIERÍA INVERSA — RESULTADOS

### 3.1 OptiCut 6 (OptiCoupe.exe)
- **Archivo analizado:** `opticut_completo.md` — 1.217 funciones, 1.7 MB
- **Ruta local:** `C:\Users\poggi\Desktop\Proyectos Marcos\Polynew\analysis\opticut_completo.md`

**Algoritmo reconstruido:**
```
1. First Fit Decreasing (FFD): ordena piezas de mayor a menor
2. Guillotina 2 etapas:
   - Etapa 1: cortes horizontales → tiras
   - Etapa 2: cortes verticales → piezas dentro de cada tira
3. Greedy: coloca cada pieza en el primer hueco disponible
4. Refinement: intercambia piezas para reducir desperdicio
```

**Función de coste (4 criterios):**
```
Coste = W1×(desperdicio/area) + W2×|cortes_X| + W3×|cortes_Y| + W4×area_colocada
```

**Categorías de funciones:**
- ALGORITMO_CORTE: 198
- MODELO_DATOS: 451
- GESTION_RETALES: 74

**Funciones núcleo (Sonnet) identificadas:**
`0065dc30, 00690740, 00695e00, 00693f00, 00733c80, 00b10f9b, 00971880, 00a0c100, 00a17bf0`

**Confirmado:** algoritmo single-threaded.

---

### 3.2 PolyBoard 7 (PolyBoard.exe)
- **Archivo analizado:** `polyboard_completo.md` — 1.970 funciones, 3.03 MB, 70.918 líneas
- **Coste análisis:** ~9 €
- **Ruta local:** `C:\Users\poggi\Desktop\Proyectos Marcos\Polynew\analysis\polyboard_completo.md`

**Distribución de categorías:**
| Categoría | Funciones |
|-----------|-----------|
| MODELO_DATOS | 682 |
| DESPIECE | 307 |
| GEOMETRIA_3D | 245 |
| EXPORTACION_CORTE | 69 |
| GENERADOR_MUEBLE | 27 |
| CANTOS / MATERIALES / HERRAJES | ~180 |
| RENDER_3D / INTERFAZ | ~200 |
| SERIALIZACION / LECTOR_PARAMETROS | ~160 |

**Módulos clave:**
- `DESPIECE` (307 funciones): lista de corte — pieza central del sistema
- `EXPORTACION_CORTE` (69 funciones): puente PolyBoard → OptiCut (formato `.ocp`)
- `GENERADOR_MUEBLE` (27 funciones): núcleo del CAD — construye el armario

---

## 4. SCRIPT DE ANÁLISIS

Ruta: `C:\Users\poggi\Desktop\Proyectos Marcos\Polynew\src\analyze_polyboard_full.py`

```python
import os, re, time
os.environ.setdefault("GHIDRA_INSTALL_DIR", r"C:\Users\poggi\Downloads\ghidra_12.1.2_PUBLIC_20260605\ghidra_12.1.2_PUBLIC")
import pyghidra
pyghidra.start()
from anthropic import Anthropic
from ghidra.app.decompiler import DecompInterface
from ghidra.util.task import ConsoleTaskMonitor
from ghidra.program.util import DefinedDataIterator

BIN    = r"C:\Program Files (x86)\Boole & Partners\PolyBoard 7\PolyBoard.exe"
OUTDIR = r"C:\Users\poggi\Desktop\Proyectos Marcos\Polynew\analysis"
PROJ   = r"C:\Users\poggi\Desktop\Proyectos Marcos\Polynew\ghidra_proj"
KEY    = os.environ.get("ANTHROPIC_API_KEY")
client = Anthropic(api_key=KEY)

MODEL_CORE = "claude-opus-4-8"           # funciones núcleo (top 45 más grandes)
MODEL_REST = "claude-haiku-4-5-20251001" # el resto

KEYWORDS = [
    "cabinet","panel","board","shelf","drawer","door","carcass","furniture",
    "edge","banding","groove","dado","rabbet","joint","dowel","hinge","hardware",
    "fitting","thickness","material","grain","laminate",
    "panneau","armoire","etagere","tiroir","porte","chant","materiau","epaisseur",
    "charniere","quincaillerie","meuble","caisson","rainure","tablette",
    "vertex","mesh","normal","matrix","transform","extrude","contour","polygon",
    "cutting","optimiz","opticut","ocp","dxf","export","cutlist","nesting","despiece",
]

DEPTH_CALLEES = 2
TOP_LARGEST   = 45
MAX_FUNCS     = 2500
```

**Características:**
- Descubrimiento automático de semillas: top 45 funciones más grandes (Opus) + matching de strings de dominio
- Cierre del grafo: 2 niveles de callees + 1 nivel de callers
- **Reanudable:** lee funciones ya analizadas del archivo de salida, no repite ni gasta tokens

---

## 5. CONOCIMIENTO TÉCNICO EXTRAÍDO

### 5.1 Algoritmo de corte a implementar

```python
def guillotine_cut(sheet_w, sheet_h, pieces):
    """
    pieces: lista de (w, h, id) ordenadas FFD (mayor a menor área)
    Retorna: lista de (id, x, y, w, h, sheet_idx)
    """
    # Etapa 1: tiras horizontales
    strips = []
    for piece in pieces:
        placed = False
        for strip in strips:
            if strip['remaining_w'] >= piece.w and strip['h'] >= piece.h:
                # coloca en strip
                placed = True; break
        if not placed:
            strips.append(new_strip(piece))  # nueva tira
    # Etapa 2: refinement por intercambio
    # Función de coste: W1*(waste/area) + W2*|cuts_x| + W3*|cuts_y| + W4*placed_area
```

### 5.2 Análisis estructural — deflexión de estantes

**Fórmula de deflexión de viga biapoyada con carga distribuida:**
```
δ = (5 × w × L⁴) / (384 × E × I)
```

Donde:
- `δ` = deflexión máxima (m)
- `w` = carga distribuida (N/m)
- `L` = longitud libre del estante (m)
- `E` = módulo de elasticidad del material (Pa)
  - MDF estándar: 3.000 MPa
  - MDF HMR: 3.500 MPa
  - Aglomerado: 2.500 MPa
  - Contrachapado abedul: 10.000 MPa
- `I` = momento de inercia = (b × h³) / 12

**Norma EN 14749 (mobiliario doméstico):**
- Nivel 1: 1,5 kg/dm²
- Nivel 2: 2,0 kg/dm²

**Norma EN 16122 (mobiliario oficina):**
- Nivel 1: 2,0 kg/dm²
- Nivel 2: 3,5 kg/dm²

**Límite de flecha aceptable:** L/300 (regla general carpintería)

```python
def deflection_check(L_mm, b_mm, h_mm, load_kg_dm2, E_MPa=3000):
    """
    Retorna (deflection_mm, ok, ratio)
    ok = True si deflexión < L/300
    """
    w = load_kg_dm2 * 9.81 * 10  # N/m (1 kg/dm² sobre b metros de ancho)
    L = L_mm / 1000
    b = b_mm / 1000
    h = h_mm / 1000
    I = (b * h**3) / 12
    E = E_MPa * 1e6
    delta = (5 * w * L**4) / (384 * E * I)
    limit = L / 300
    return delta * 1000, delta < limit, delta / limit
```

### 5.3 Reglas de montaje (codificables)

**Secuencia básica de un armario:**
1. Laterales + fondo (si hay dado ya fresado)
2. Baldas fijas con tacos/pasadores
3. Panel superior (tapa)
4. Panel trasero:
   - Si **dado**: encaja al montar los laterales
   - Si **plantado**: atornilla al final
5. Guías de cajones
6. Puertas (abatibles/correderas)
7. Tiradores y herrajes

**Reglas cam-lock (minifix/confirmat):**
1. Housing en panel A (pre-instalado)
2. Bolt en panel B (pre-instalado)
3. Unir paneles
4. Introducir bolt en housing
5. Girar todos SUELTOS primero
6. Apretar alternando (no en secuencia lineal)

**Tipos de herrajes codificables:**
- Bisagras Blum (ángulo apertura: 95°/110°/170°)
- Guías Blum Tandembox (extensión total, soft-close)
- Cam-lock / Confirmat
- Pasadores de baldas (diámetro 5mm, paso 32mm sistema)
- Correderas de puertas (anchura canal: 8mm estándar)

### 5.4 Manual de montaje IA

**Estructura de cada paso:**
```json
{
  "step": 1,
  "title": "Montar lateral izquierdo con fondo",
  "pieces": ["LateralIzq_001", "Fondo_001"],
  "hardware": ["cam_lock_x4", "pasador_x8"],
  "illustration": "SVG generado por Claude",
  "note": "Verificar que el dado del fondo queda a 6mm del borde trasero",
  "qr_url": "https://polynew.app/step/1?mueble=XXX"
}
```

**Generación SVG:** Claude API con prompt de vista explosionada simplificada estilo IKEA.

---

## 6. ARQUITECTURA TECNOLÓGICA PLANIFICADA

```
┌─────────────────────────────────────────────────────────────┐
│                     POLYNEW APP                             │
├──────────────┬──────────────┬──────────────┬────────────────┤
│  Mobile/AR   │  Web CAD     │  Backend API  │  Marketplace   │
│  (React Native│  (Streamlit  │  (FastAPI +   │  (carpinteros, │
│  + ARKit)    │  o React)    │  Claude API)  │  proveedores)  │
└──────────────┴──────────────┴──────────────┴────────────────┘
         │              │              │
         ▼              ▼              ▼
┌─────────────────────────────────────────────────────────────┐
│                      CORE ENGINE (Python)                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ Motor Corte  │  │ Generador    │  │ Análisis         │  │
│  │ (guillotina) │  │ Mueble       │  │ Estructural      │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ Despiece     │  │ Manual       │  │ Exportación      │  │
│  │ (lista corte)│  │ Montaje IA   │  │ (DXF/OptiCut)   │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                    ┌─────────────────┐
                    │  SQLite / DB    │
                    │  (modelo datos) │
                    └─────────────────┘
```

**Stack recomendado:**
- **Backend:** Python 3.11+, FastAPI
- **UI MVP:** Streamlit
- **UI producción:** React + Three.js (3D)
- **Mobile:** React Native + ViroReact (ARKit/ARCore)
- **Base de datos:** SQLite (MVP) → PostgreSQL (producción)
- **IA:** Claude API (claude-opus-4-8 para diseño, claude-haiku para descripciones)
- **IDE:** Visual Studio Code en Windows
- **Versión:** Git (este repo o nuevo repo `polynew`)

---

## 7. ESTRUCTURA DE CARPETAS SUGERIDA PARA POLYNEW

```
C:\Users\poggi\Desktop\Proyectos Marcos\Polynew\
├── analysis\
│   ├── opticut_completo.md       ← ya generado (1.217 funciones)
│   └── polyboard_completo.md     ← ya generado (1.970 funciones)
├── src\
│   ├── analyze_polyboard_full.py ← script de análisis (ya usado)
│   ├── engine\
│   │   ├── __init__.py
│   │   ├── cut_optimizer.py      ← motor guillotina (PRIMER MÓDULO)
│   │   ├── furniture_model.py    ← modelo de datos del mueble
│   │   ├── structural.py         ← análisis deflexión estantes
│   │   └── cut_list.py           ← generación de despiece
│   ├── api\
│   │   ├── main.py               ← FastAPI
│   │   └── routes\
│   ├── ui\
│   │   └── app.py                ← Streamlit MVP
│   └── ai\
│       ├── designer.py           ← IA → diseño mueble
│       └── manual_generator.py   ← IA → manual montaje
├── tests\
│   ├── test_cut_optimizer.py
│   └── test_structural.py
├── requirements.txt
└── .vscode\
    └── settings.json
```

---

## 8. ORDEN DE IMPLEMENTACIÓN RECOMENDADO

### Fase 1 — Motor de corte (MVP testeable, ~1-2 semanas)
1. `cut_optimizer.py`: FFD + guillotina 2 etapas
2. Tests con casos conocidos (tablero 2440×1220, piezas variadas)
3. UI Streamlit básica: entrada de piezas → mapa visual de cortes

### Fase 2 — Modelo de mueble (~2 semanas)
1. `furniture_model.py`: Cabinet, Panel, Edge, Hardware
2. `cut_list.py`: de mueble → lista de piezas
3. `structural.py`: deflexión + alerta visual

### Fase 3 — IA Designer (~1-2 semanas)
1. Prompt Claude: "armario esquinero 2m, 3 cajones, blanco" → JSON de mueble
2. Validación estructural automática
3. Sugerencia de materiales y espesores

### Fase 4 — Cadena completa (~3-4 semanas)
1. Manual de montaje IA (SVG + QR)
2. Exportación a proveedor de corte
3. Calculadora de precio

### Fase 5 — Marketplace (~ongoing)
1. Proveedores de corte
2. Bolsa de carpinteros
3. Pagos con escrow

---

## 9. SETUP INICIAL EN VS CODE

### Extensiones a instalar:
- Python (Microsoft)
- Pylance
- GitLens
- Thunder Client (para probar API)
- Markdown Preview Enhanced

### Terminal integrada (PowerShell):
```powershell
# Crear entorno virtual
cd "C:\Users\poggi\Desktop\Proyectos Marcos\Polynew"
python -m venv .venv
.venv\Scripts\Activate.ps1

# Instalar dependencias base
pip install anthropic fastapi streamlit uvicorn pytest

# Variable de entorno API key
$env:ANTHROPIC_API_KEY = "tu-key-aqui"
```

### `.vscode/settings.json` sugerido:
```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}\\.venv\\Scripts\\python.exe",
  "python.formatting.provider": "black",
  "editor.formatOnSave": true,
  "files.autoSave": "afterDelay",
  "terminal.integrated.defaultProfile.windows": "PowerShell"
}
```

---

## 10. NOTAS IMPORTANTES

- **PyGhidra:** requiere `GHIDRA_INSTALL_DIR` como variable de entorno antes de `import pyghidra`
- **Modelo de análisis:** Los archivos `.md` ya están generados. No hace falta volver a correr el análisis. Solo leer los `.md` para extraer datos.
- **Costo análisis:** ~9 € total (polyboard_completo.md)
- **Script reanudable:** Si se interrumpe, relanza el mismo script — lee las funciones ya procesadas del `.md` y continúa desde donde se quedó.
- **Este repo (`cae-auto-calc`):** es una calculadora de certificados de ahorro energético (CAE), proyecto distinto. Tiene Streamlit + motor de cálculo RES010/TER030. Está en GitHub: `mgp2002ar/cae-auto-calc`.

---

## 11. GHIDRA — INFO DEL ENTORNO

```
GHIDRA_INSTALL_DIR = C:\Users\poggi\Downloads\ghidra_12.1.2_PUBLIC_20260605\ghidra_12.1.2_PUBLIC
PolyBoard.exe      = C:\Program Files (x86)\Boole & Partners\PolyBoard 7\PolyBoard.exe
Proyecto Ghidra    = C:\Users\poggi\Desktop\Proyectos Marcos\Polynew\ghidra_proj\poly_full
```

**Binarios analizados:**
- PolyBoard.exe — PE32 MSVC, 32-bit Windows
- OptiCoupe.exe — PE32 MSVC, 32-bit Windows (OptiCut 6)

---

*Fin de la memoria. Última actualización: 15/06/2026.*
