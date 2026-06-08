# Sistema de Certificados Digitales — Pasitos Education & Health A.C.

Herramienta en Python para emitir y verificar certificados de capacitación con firma digital, desarrollada para **Pasitos Education & Health A.C.** (Valle de los Molinos, Zapopan, Jalisco).

Pasitos es una asociación civil con más de 5 años de operación, enfocada en servicios educativos y de salud para niñas, niños y familias en situación vulnerable. Este sistema cubre el ciclo completo: registro de participantes → emisión del certificado firmado → descarga del PDF → verificación pública por folio.

---

## Stack

| Componente | Librería / Herramienta |
|---|---|
| Interfaz web | `Flask 3.x` + `Flask-Session` |
| Firma digital | `cryptography` — ECDSA SECP256R1, nonce RFC 6979 |
| Hashing | `hashlib` SHA-256 |
| Contraseñas | `bcrypt` (tiempo constante) |
| PDF | `playwright` (Chromium headless) + `pypdf` (merge) |
| QR | `qrcode[pil]` + `Pillow` |
| Datos | `csv` (stdlib) |
| Sesiones | Filesystem (`.flask_sessions/`) |

---

## Estructura

```
pasitos-cert-crypto/
├── run_web.py                   # punto de entrada: python run_web.py
├── src/
│   ├── web/
│   │   ├── app.py               # fábrica Flask, registro de blueprints
│   │   ├── routes/
│   │   │   ├── auth.py          # login/logout, decorador login_required
│   │   │   ├── dashboard.py     # panel principal con estadísticas
│   │   │   ├── certificados.py  # emisión, descarga, re-emisión, export
│   │   │   ├── verificar.py     # verificación pública por folio
│   │   │   ├── admin.py         # gestión de usuarios (solo admin)
│   │   │   ├── catalogo.py      # catálogo de cursos (CRUD + export CSV)
│   │   │   ├── datos.py         # carga del CSV de registros
│   │   │   ├── nosotros.py      # info del proyecto y organización
│   │   │   └── ayuda.py         # guía de uso y referencia de campos
│   │   ├── templates/           # Jinja2 (base.html + páginas)
│   │   └── static/css/          # CSS puro, sin frameworks externos
│   ├── auth/                    # RBAC: roles admin, operator, viewer
│   ├── crypto/                  # generación de llaves, firma ECDSA
│   ├── data_manager/            # lectura de CSVs, enriquecimiento
│   ├── pdf_generator/           # HTML→PDF via Playwright, merge pypdf
│   ├── main.py                  # CLI alternativa
│   └── verificar.py             # verificación desde terminal
├── data/
│   ├── catalogo_cursos.csv      # catálogo de cursos (versionado)
│   ├── registros_cursos.csv     # participantes — NO versionado (CURPs)
│   └── instrucciones_uso.csv    # referencia de campos del CSV
├── docs/templates/
│   ├── certificado.html         # plantilla del certificado (Playwright)
│   └── boleta.html              # plantilla de la boleta de calificaciones
├── keys/                        # llaves PEM — NO versionadas
├── output/
│   └── certificados.json        # registro de todos los certificados emitidos
└── requirements.txt
```

---

## Instalación

```bash
# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Instalar Chromium para Playwright
playwright install chromium

# 3. Definir la llave secreta (evita que las sesiones se invaliden al reiniciar)
copy .env.example .env
# Edita .env y pon un valor largo y aleatorio en PASITOS_SECRET_KEY
```

En Windows, cargar la variable antes de iniciar el servidor:

```powershell
$env:PASITOS_SECRET_KEY = "tu-clave-aqui"
python run_web.py
```

---

## Uso

### Servidor web

```bash
python run_web.py
```

Abre `http://localhost:5000`. Las credenciales de demostración están en `/ayuda` dentro del sistema.

### CLI (sin servidor)

```bash
python src/main.py                     # emitir certificados desde terminal
python src/verificar.py VER-0001       # verificar un folio
```

---

## Páginas del sistema

| Ruta | Descripción | Acceso |
|---|---|---|
| `/` | Panel principal con estadísticas | Todos |
| `/certificados` | Lista, búsqueda, descarga, re-emisión | Todos |
| `/certificados/emitir` | Emisión con firma ECDSA | Admin, Operator |
| `/verificar` | Verificación pública por folio | Sin login |
| `/catalogo` | Catálogo de cursos con CRUD | Todos (edición: Admin, Operator) |
| `/datos` | Carga del CSV de registros | Todos (subida: Admin, Operator) |
| `/nosotros` | Info del proyecto y especificaciones criptográficas | Todos |
| `/ayuda` | Guía de campos, credenciales de demo, comandos | Todos |
| `/admin/usuarios` | Gestión de usuarios | Solo Admin |

---

## Seguridad

- La llave privada (`keys/private_key.pem`) no se versiona. Sin ella no se pueden emitir nuevos certificados, pero los existentes se siguen verificando con la llave pública.
- El CSV de registros (`data/registros_cursos.csv`) contiene CURPs y nombres completos y está excluido de git.
- Las contraseñas se almacenan como hashes bcrypt; la comparación usa tiempo constante.
- `PASITOS_SECRET_KEY` se lee de variable de entorno. Si no está definida, se genera una aleatoria en cada inicio (lo que invalida sesiones activas).
- El catálogo de cursos (`data/catalogo_cursos.csv`) no contiene datos personales y sí se versiona.

---

## Catálogo de cursos

| ID | Curso | Tipo | Horas |
|---|---|---|---|
| C-001 | Puericultura | Capacitación Técnica | 80h |
| C-002 | Asistente Educativo | Capacitación Técnica | 80h |
| C-003 | Primeros Auxilios Pediátricos | Taller Práctico | 50h |
| C-004 | Estimulación Temprana | Taller Práctico | 40h |
| C-005 | Terapia de Lenguaje para Cuidadores | Taller Práctico | 30h |
| C-006 | Apoyo Psicosocial y Crianza Positiva | Taller Práctico | 20h |
| C-007 | Orientación Familiar para Cuidadores | Taller Práctico | 15h |

El catálogo se puede editar desde la interfaz web en `/catalogo` y exportar como CSV.

---

## Contacto Pasitos

- **Web:** [pasitosac.org](https://www.pasitosac.org/)
- **Email:** info@pasitoseducation.com
- **Tel:** +52 332 780 5441
- **Dirección:** Valle de los Molinos, Zapopan, Jalisco

---

## Licencia

MIT — Proyecto académico, Tecnológico de Monterrey Campus Guadalajara.
