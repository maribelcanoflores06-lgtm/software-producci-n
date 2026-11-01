# Define Goal — Software de Producción (prototipo)

## Objetivo
Prototipo web en Python, ejecutado en local desde una laptop, para presentarlo al cliente. Cubre tres módulos: control de almacén, control de producción y costeo de fabricación. Precio: USD 1,500 (USD 500 por módulo). Una propuesta anterior de USD 6,000 fue rechazada.

## Maestros
- Artículos, con tipo de material. La tabla de tipos es fija y no se edita: materia prima, materiales auxiliares, repuestos y suministros, envases y embalajes, desperdicios, producto terminado.
- Clientes y proveedores.
- Trabajadores: código, nombres, tipo de documento (DNI, pasaporte, otros) y número de documento.
- Almacenes, por ahora en versión básica.
- Procesos y rutas. Cada producto terminado tiene una ruta asignada, que se fija al crear la orden de producción.

## Operaciones de almacén (todas actualizan el Kardex)
1. Ingreso. Subtipos: compra nacional, importación, muestras y otros, con el mismo formulario.
2. Salida.
3. Transferencia entre almacenes.
4. Salida a producción y entrada de producción. Ambas deben estar vinculadas a una orden de producción, para poder costear.

## Orden de producción
- Campos: cliente, producto terminado, fecha de registro y ruta. Al elegir el producto se carga su ruta.
- Genera dos salidas: la lista de materiales y la hoja de ruta.

## Costeo
- Valorización manual en soles al registrar cada ingreso. Kardex valorizado.
- Los costos de producción (luz, mano de obra) se importan de forma masiva al Kardex.
- Fuera de alcance: el costo real, porque requiere un módulo de compras.

## Reportes para la demo
1. Lista de materiales y hoja de ruta por orden de producción.
2. Stock por almacén, con número de transacción.
3. Kardex o lista de movimientos.

## Criterio de éxito de la demo
Mostrar el flujo completo: crear materiales, crear la orden de producción y registrar los movimientos de almacén, con los reportes al día.

## Decisiones (grill me)
- Cada producto terminado tiene su propia lista de materiales (receta), formada con artículos del maestro de materiales. La orden de producción toma esa lista para generar el reporte de materiales.
- La receta se define por lote base (ej. 100 unidades); la OP indica cantidad a producir y el reporte escala: cantidad_OP / lote_base × cantidad_receta.
- Kardex valorizado por promedio ponderado.
- Costo de fabricación (luz, MO, etc.) se asigna manualmente por orden de producción.
- En la entrada de producción, el usuario decide el consumo de insumos de dos formas: (a) un % de consumo sobre lo enviado a producción, o (b) seleccionando qué insumos enviados (y cuánto) se usaron. Costo PT = insumos consumidos (prom. ponderado) + costo de fabricación de la OP.
- Lo enviado a producción y no consumido queda como stock en proceso (WIP) asociado a la OP.
- El stock en proceso vive en un almacén virtual "En proceso", visible en el reporte de stock.
- Una OP admite varias entradas de producción parciales hasta su cierre.
- A fin de mes se ingresan (carga masiva) los costos de fabricación por cada declaración de producción; el sistema revaloriza esas entradas y el Kardex (prom. ponderado) desde esa fecha.
- Maestros se crean a mano en pantalla (sin carga Excel) para la demo.
- Clientes y proveedores: 2 pantallas y 2 tablas separadas en la BD.
- Almacenes "en proceso": el usuario los crea como un almacén más, con un booleano es_proceso; esos almacenes solo participan en salidas a producción y entradas de producción.
- Las rutas son independientes (no asociadas al producto terminado); se eligen al crear la OP.
- Multiusuario con login y permisos por pantalla: cada usuario (o rol) tiene asignadas las pantallas que puede ver/usar; incluye pantalla de administración de usuarios y permisos.
- Permisos por roles: cada rol tiene pantallas asignadas y a cada usuario se le asigna un rol.
- Demo: no se implementa cierre de OP.
- Ingreso a almacén: proveedor obligatorio.
- Trabajadores: solo catálogo por ahora.
- Maestro de años (periodos): cada movimiento de almacén se asocia a un año; al cierre anual el saldo final (cantidad y valor) pasa como saldo inicial del año siguiente, para que las consultas no recorran todo el histórico.
- id_anio es FK en movimientos de almacén (cabecera) y en órdenes de producción.
- Almacén tiene campo `codigo` (ej. ALM01). Número de nota de almacén = CODALMACEN-AÑO-CORRELATIVO (correlativo por almacén y año, ej. ALM01-2026-000001).
- Código de OP = OP-AÑO-CORRELATIVO (correlativo por año, ej. OP-2026-0001).
- Demo: opción para cargar saldo inicial (pantalla) y botón de datos de ejemplo.
