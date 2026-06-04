# Pasitos - Sistema de Certificados Digitales

Herramienta en Python para generar y verificar los certificados digitales de **Pasitos Education & Health A.C.**, con sede en Valle de los Molinos, Zapopan, Jalisco.

Pasitos es una organización socio-formadora con más de 5 años ofreciendo servicios educativos y de salud a niñas, niños y adolescentes en situación vulnerable. Cuenta con 8 programas activos (Guardería Integral, Terapia de Lenguaje, Salud Visual, Salud Dental, Apoyo Psicosocial, Pasitos Bilingüe, entre otros), más de 6,000 beneficiarios y 500 voluntarios.

## Stack

| Componente | Librería |
|---|---|
| Firma digital | `cryptography` (ECDSA SECP256R1) |
| Hashing | `hashlib` SHA-256 |
| Contrasenas | `bcrypt` |
| QR | `qrcode[pil]` + `Pillow` |
| PDF | `reportlab` + `playwright` |
| Datos | `csv` (stdlib) |

## Estructura

```
pasitos-cert-crypto/
├── src/
│   ├── auth/            # login y roles
│   ├── crypto/          # firma y verificacion ECDSA
│   ├── data_manager/    # lectura de CSV
│   ├── pdf_generator/   # generacion de PDFs y QR
│   ├── main.py          # CLI principal
│   └── verificar.py     # verificacion local de certificados
├── data/                # CSVs con datos (ignorado en git)
├── docs/templates/      # plantillas HTML y assets
├── tests/
└── requirements.txt
```

## Instalacion

```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
pip install -r requirements.txt
playwright install chromium
```

## Uso

```bash
python src/main.py
```

Pide credenciales. Solo los roles `ADMIN` y `OPERATOR` pueden emitir certificados.

Para verificar un certificado por folio:

```bash
python src/verificar.py VER-0001
```

## Seguridad

- Las llaves privadas (`.pem`) no se versionan (ver `.gitignore`).
- Los CSVs con datos personales (CURP, nombre) no se incluyen en el repositorio.
- Las contrasenas se guardan como hashes bcrypt.
- El login usa comparacion en tiempo constante para evitar timing attacks.

## Contacto Pasitos

- **Web:** [pasitosac.org](https://www.pasitosac.org/)
- **Email:** info@pasitoseducation.com
- **Tel:** +52 332 780 5441
- **Direccion:** Valle de los Molinos, Zapopan, Jalisco

## Licencia

MIT - Proyecto academico, Tecnologico de Monterrey Campus Guadalajara (GDA).
