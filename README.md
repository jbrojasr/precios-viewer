# Visor de Precios

Aplicación web para visualizar, buscar y gestionar un inventario de productos con costos, existencias y cálculo automático de márgenes de ganancia.

## Características

- 🔍 **Búsqueda avanzada**: Busca por código, descripción o nombre del producto
- 📊 **Visualización clara**: Tabla en desktop y tarjetas en móvil
- 💰 **Cálculo de márgenes**: Ajusta dinámicamente el porcentaje de ganancia
- 📱 **Responsivo**: Funciona perfectamente en cualquier dispositivo
- 📤 **Importación Excel**: Carga nuevos inventarios desde archivos .xlsx
- 🔐 **Protegido con PIN**: Control de acceso para actualizaciones

## Búsqueda especial

- **Búsqueda normal**: `Negro` → busca en código y descripción
- **Búsqueda en descripción**: `*Negro` → busca SOLO en descripción

## Requisitos

- Python 3.11+
- Flask
- openpyxl
- better-sqlite3

## Instalación

```bash
python -m venv .venv
source .venv/bin/activate  # En Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Ejecución

```bash
# Desarrollo con auto-reload
python -m waitress --listen=0.0.0.0:8080 app:app

# O con Flask
export FLASK_ENV=development
flask run
```

La aplicación estará disponible en `http://localhost:8080`

## Estructura

```
.
├── app.py                 # Aplicación Flask principal
├── templates/
│   └── index.html        # Interfaz web
├── static/
│   ├── app.js           # Lógica del frontend
│   └── styles.css       # Estilos
├── data/
│   └── prices.db        # Base de datos SQLite
├── seed.py              # Script para poblar datos
└── test_smoke.py        # Tests básicos
```

## API Endpoints

- `GET /` - Página principal
- `GET /health` - Estado de la aplicación
- `GET /api/stats` - Estadísticas del inventario
- `GET /api/products?q=...` - Buscar productos
- `POST /api/setup-pin` - Configurar PIN de acceso
- `POST /api/import` - Importar archivo Excel

## Licencia

MIT
