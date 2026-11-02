import sys
from pathlib import Path

from app import import_workbook

if len(sys.argv) != 2:
    raise SystemExit("Uso: seed.py archivo.xlsx")
path = Path(sys.argv[1]).resolve()
result = import_workbook(path, path.name)
print(f"Importados: {result['count']} | Hoja: {result['sheet']} | Errores: {len(result['errors'])}")
