"""
Punto de entrada para la aplicación web de Pasitos.
Ejecutar desde la raíz del proyecto: python run_web.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from web.app import create_app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, port=5000)
