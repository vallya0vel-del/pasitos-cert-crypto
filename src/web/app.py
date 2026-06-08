"""
app.py
------
Aplicación Flask principal para el Sistema de Certificados Digitales
de Pasitos Education & Health A.C.
"""

import os
import sys
from pathlib import Path

# Agregar /src al path para importar módulos existentes
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask
from flask_session import Session

from .routes.auth import auth_bp
from .routes.dashboard import dashboard_bp
from .routes.certificados import certificados_bp
from .routes.admin import admin_bp
from .routes.verificar import verificar_bp
from .routes.catalogo import catalogo_bp
from .routes.datos import datos_bp
from .routes.nosotros import nosotros_bp
from .routes.ayuda import ayuda_bp


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )

    # ─── Configuración ────────────────────────────────────────────────────────
    secret = os.environ.get("PASITOS_SECRET_KEY")
    if not secret:
        import warnings
        warnings.warn(
            "PASITOS_SECRET_KEY no está definida. "
            "Las sesiones se invalidarán al reiniciar el servidor.",
            stacklevel=2,
        )
        secret = os.urandom(32)
    app.config["SECRET_KEY"] = secret
    app.config["SESSION_TYPE"] = "filesystem"
    app.config["SESSION_FILE_DIR"] = str(Path(__file__).parent.parent.parent / ".flask_sessions")
    app.config["SESSION_PERMANENT"] = False
    app.config["SESSION_USE_SIGNER"] = True

    Session(app)

    # ─── Blueprints ───────────────────────────────────────────────────────────
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(certificados_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(verificar_bp)
    app.register_blueprint(catalogo_bp)
    app.register_blueprint(datos_bp)
    app.register_blueprint(nosotros_bp)
    app.register_blueprint(ayuda_bp)

    return app
