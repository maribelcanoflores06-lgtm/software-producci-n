# Software de Producción

Prototipo local para la demo a un cliente textil. Corre en una laptop con Python, Django y un archivo SQLite. No hace falta instalar un servidor de base de datos.

**Fase 1** (esta entrega): acceso, roles, permisos por pantalla, maestro de años y maestros base (artículos, recetas, clientes, proveedores, trabajadores, almacenes, procesos y rutas), más el saldo inicial y la carga de datos de ejemplo.

Almacén operativo, órdenes de producción, costeo y reportes aparecen en el menú según el rol, y la pantalla indica que llegan en una fase posterior. El permiso ya se aplica: quien no tiene la pantalla recibe 403.

## Requisitos

- Python 3.12 (también sirve 3.11)
- Windows, macOS o Linux

## Cómo correrlo en Windows

En PowerShell o en el Símbolo del sistema, dentro de la carpeta del proyecto:

```bat
py -3 -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py runserver 127.0.0.1:8765
```

Abra el navegador en [http://127.0.0.1:8765](http://127.0.0.1:8765).

Si `py` no existe, use `python` en los mismos comandos. Si el puerto 8765 está ocupado, cambie el número en el último comando y en la dirección del navegador.

Para que otra persona en la misma red vea la demo:

```bat
python manage.py runserver 0.0.0.0:8765
```

Windows puede pedir permiso en el firewall. La dirección es `http://IP-DE-LA-LAPTOP:8765`.

## Cómo correrlo en macOS o Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py runserver 127.0.0.1:8765
```

## Usuarios de la demo

Contraseñas solo para esta laptop. Están también en la pantalla de ingreso, marcadas como ejemplo.

| Usuario | Contraseña | Rol |
| --- | --- | --- |
| maribel | demo-admin | Admin |
| almacenero | demo-alm | Almacenero (artículos y almacenes en solo lectura; almacén y stock) |
| jefeprod | demo-prod | Jefe de producción |
| consulta | demo-consulta | Consulta (solo reportes, sin modificar) |

`seed_demo` no cambia la contraseña ni el rol de un usuario que ya existe. Sí vuelve a dejar los permisos de los cuatro roles de fábrica como en la especificación.

Solo la base, sin el catálogo textil:

```bat
python manage.py seed_demo --solo-base
```

Con la sesión de `maribel`, el botón **Cargar datos de ejemplo** del menú principal hace lo mismo, y solo si todavía no hay artículos, almacenes, clientes, proveedores, trabajadores, procesos ni rutas.

## Datos de ejemplo

Quedan marcados con la etiqueta **EJEMPLO**. Incluyen el año 2026 activo, los almacenes `ALM01`, `ALM02`, `ALM03` y `PROC01` (este último es de proceso), la receta del polo `PT-POL-PIQ-B` con lote base 100, la ruta `RUTA-POLO-01` (sin producto asociado) y saldos iniciales en `ALM01`:

| Artículo | Cantidad | Costo unitario S/ |
| --- | --- | --- |
| MP-HIL-20/1 | 100 kg | 2.0000 |
| MP-TEL-JER | 250 m | 4.5000 |
| AUX-BOT-14 | 1000 und | 0.0500 |
| ENV-BOL-P | 500 und | 0.0200 |

Cada saldo genera una nota `ALM01-2026-00000N` y la primera fila de Kardex de ese artículo. Los demás almacenes quedan con correlativo 0. El correlativo de órdenes (`OP-2026-####`) queda en 0.

## Pruebas

```bat
python manage.py test
```

Cubren el criterio de la fase 1: login de los cuatro usuarios, menú de Consulta sin ingreso, POST a ingreso en 403, receta por lote 100, ruta sin producto, `PROC01` de proceso, año 2026 activo, código de almacén único, saldo inicial con nota y Kardex, cierre de año y la carga de ejemplo una sola vez.

## Respaldo antes de la presentación

El archivo de la base es `db.sqlite3`, en la carpeta del proyecto.

```bat
copy db.sqlite3 db.sqlite3.bak
```

En macOS o Linux: `cp db.sqlite3 db.sqlite3.bak`.

## Zona horaria e idioma

La interfaz está en español. La hora es `America/Lima`. Cantidades y montos usan 4 decimales. En los formularios puede escribir el decimal con punto o con coma.

## Documentos

La especificación y el contexto de diseño están en `docs/`:

- `docs/ESPECIFICACION.md` (manda si hay contradicción)
- `docs/01-DEFINE-GOAL.md`
- `docs/02-SHAPING.md`
- `docs/03-BREADBOARDING.md`
- `docs/04-VISUAL-REFERENCE.md`
- `docs/04-visual/index.html` (mockups)
