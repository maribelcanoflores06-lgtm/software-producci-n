# Visual Reference — Software de Producción

Mockups estáticos para alinear UI antes de la especificación / implementación. Datos textiles marcados como **EJEMPLO**.

## Entregables

| Ruta | Qué es |
|------|--------|
| `04-visual/index.html` | Un solo HTML (CSS/JS embebidos, sin CDN). Navegación entre pantallas vía menú / `?screen=` |
| `04-visual/captura-01-menu-ingreso.png` | Menú lateral + Ingreso compra nacional |
| `04-visual/captura-02-declaracion.png` | Declaración de producción (tabs + modo %) |
| `04-visual/captura-03-orden-produccion.png` | OP + BOM escalado + hoja de ruta |
| `04-visual/captura-04-kardex.png` | Kardex promedio ponderado + revalorización PT |
| `referencias/` | Capturas del sistema actual (cabecera/grilla) y foto Odoo (menú) |

Abrir mockups: `file:///…/04-visual/index.html` o servir la carpeta. Deep-link: `?auto=1&screen=declaracion`.

## Pantallas en el HTML

Login · Menú principal · Ingreso · Salida · Transferencia · Salida a producción · Declaración de producción · Orden de producción · Receta (lote base) · Roles y pantallas · Stock · Kardex.

## Decisiones de estilo

1. **Shell tipo Odoo:** sidebar oscuro (`#2c2c2c`) con grupos por módulo; ítem activo en morado (`#714B67`); topbar morada con breadcrumb. El menú se filtra por rol en runtime (en el mockup Admin ve todo).
2. **Formularios densos (sistema actual):** cabecera compacta en filas — Almacén, Año/Mes/F. Registro, Tipo Operación, Nota N° `(AUTO)`, Origen/Destino, Proveedor/Razón social (obligatorio en ingreso), Tipo comprobante + Serie/Número/Fecha Doc. Ref., Obs.
3. **Grilla de ítems:** Código, Producto, Lote, Ubicación, Stock, Cant., U/M, Kilo/Und/Metro Ref, Obs. (+ Costo unit. en ingreso). Contador `Registro N de N` a la izquierda; **Guardar** / **Cancelar** a la derecha.
4. **Declaración:** pestañas *Productos Obtenidos* / *Insumos Utilizados*; caja de modo consumo **% sobre WIP** o **manual**; totales al pie (cant. PT, costo insumos, costo fab. = 0 hasta fin de mes, unitario).
5. **Acento:** morado Odoo + grises utilitarios; tipografía Segoe UI / Tahoma; sin dependencias externas para poder abrir el HTML offline en la laptop de la demo.
6. **Datos de ejemplo:** artículos textiles (hilo 20/1, tela jersey, polo piqué, botones, bolsas), proveedores/clientes ficticios, TR-2026-…, OP-2026-00015. Etiqueta naranja `EJEMPLO` / `ej.` en pantallas y capturas.
7. **Cambios de diseño posteriores:** CSS/plantillas desacoplados de la lógica Kardex — se puede retocar layout o colores sin tocar el modelo. Campos configurables tipo Odoo Studio quedan fuera de la demo.

## Cómo regenerar capturas

```bash
cd /workspace/software-produccion/04-visual
BASE="file://$PWD/index.html"
for pair in "ingreso:captura-01-menu-ingreso" "declaracion:captura-02-declaracion" \
            "op:captura-03-orden-produccion" "kardex:captura-04-kardex"; do
  s=${pair%%:*}; f=${pair##*:}
  google-chrome --headless=new --disable-gpu --hide-scrollbars \
    --window-size=1400,900 --screenshot="$PWD/${f}.png" \
    "${BASE}?auto=1&screen=${s}"
done
```

## Siguiente paso

`ESPECIFICACION.md` (to spec) con campos, validaciones y contratos de API/vistas alineados a estos mockups + breadboarding.
