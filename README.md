# Pasitos — Sistema de Certificados Digitales

Sistema open-source en Python para la emisión y validación de certificados digitales para **Pasitos Education & Health A.C.**, organización socio-formadora ubicada en Valle de los Molinos, Zapopan, Jalisco.

> "Cada pequeño paso que damos junto a nuestros beneficiarios se convierte en un gran salto hacia un futuro lleno de oportunidades." — Pasitos A.C.

Pasitos lleva más de 5 años brindando servicios educativos y de salud a niñas, niños y adolescentes en situación vulnerable a través de 8 programas activos (Guardería Integral, Terapia de Lenguaje, Salud Visual, Salud Dental, Apoyo Psicosocial, Pasitos Bilingüe, entre otros) con más de 6,000 beneficiarios y 500 voluntarios.

Este sistema contribuye al **ODS 9 — Industria, Innovación e Infraestructura** garantizando seguridad, trazabilidad y no-repudio en los documentos digitales emitidos por la organización, mediante criptografía de curva elíptica (ECDSA SECP256R1).

---

## Stack tecnológico

| Componente | Librería |
|---|---|
| Firma digital | `cryptography` (ECDSA SECP256R1) |
| Hashing | `hashlib` SHA-256 |
| Contraseñas | `bcrypt` (Blowfish adaptativo + salting) |
| QR codes | `qrcode[pil]` + `Pillow` |
| PDF | `reportlab` |
| Datos | `csv` (stdlib) |

## Estructura del repositorio

```
pasitos-cert-crypto/
├── src/
│   ├── auth/            # RBAC + bcrypt 
│   ├── crypto/          # ECDSA sign/verify 
│   ├── data_manager/    # Lector CSV 
│   ├── pdf_generator/   # Builder PDF + QR
│   └── main.py          # Orquestador CLI)
├── data/                # CSVs
├── docs/
├── tests/
└── requirements.txt
```

## Instalación

```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
pip install -r requirements.txt
```

## Uso rápido

```bash
python src/main.py
```

El sistema solicitará credenciales. Solo roles `ADMIN` u `OPERATOR` pueden emitir certificados.

## Seguridad

- Las llaves privadas (`.pem`) **nunca** se versionan (ver `.gitignore`).
- Los CSVs con datos personales (CURP, nombre) están excluidos del repositorio.
- Las contraseñas se almacenan exclusivamente como hashes bcrypt con salt único por usuario.
- Las comparaciones de login usan tiempo constante para prevenir timing attacks.

## Contacto Pasitos

- **Web:** [pasitosac.org](https://www.pasitosac.org/)
- **Email:** info@pasitoseducation.com
- **Tel:** +52 332 780 5441
- **Dirección:** Valle de los Molinos, Zapopan, Jalisco

## Licencia

MIT — Proyecto académico, Tecnológico de Monterrey Campus Guadalajara (GDA)
