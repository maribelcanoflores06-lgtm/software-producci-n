function agregarLinea(prefix) {
  const total = document.getElementById('id_' + prefix + '-TOTAL_FORMS');
  const body = document.getElementById('lineas-body');
  const tpl = document.getElementById('linea-vacia');
  if (!total || !body || !tpl) return;
  const index = total.value;
  const html = tpl.innerHTML.split('__prefix__').join(index);
  body.insertAdjacentHTML('beforeend', html);
  total.value = String(parseInt(index, 10) + 1);
  filtrarInsumos();
  contarLineas();
}

function quitarLinea(boton) {
  const fila = boton.closest('tr');
  if (!fila) return;
  const marca = fila.querySelector('input[name$="-DELETE"]');
  if (marca) {
    if (marca.type === 'checkbox') marca.checked = true;
    else marca.value = 'on';
  }
  fila.hidden = true;
  renumerarSecuencias();
  contarLineas();
}

function renumerarSecuencias() {
  const filas = document.querySelectorAll('#lineas-body tr:not([hidden])');
  let numero = 1;
  filas.forEach(function (fila) {
    const secuencia = fila.querySelector('input[name$="-secuencia"]');
    if (!secuencia || secuencia.disabled) return;
    secuencia.value = String(numero);
    numero += 1;
  });
}

function aplicarCatalogo(select, catalogo, pt) {
  const actual = select.value;
  const elegido = actual && String(actual) !== String(pt) ? String(actual) : '';
  select.innerHTML = '';
  const vacio = document.createElement('option');
  vacio.value = '';
  vacio.textContent = '—';
  if (!elegido) vacio.selected = true;
  select.appendChild(vacio);
  catalogo.forEach(function (item) {
    if (String(item.id) === String(pt)) return;
    const opcion = document.createElement('option');
    opcion.value = String(item.id);
    opcion.textContent = item.label;
    if (String(item.id) === elegido) opcion.selected = true;
    select.appendChild(opcion);
  });
}

function filtrarInsumos() {
  const nodo = document.getElementById('catalogo-insumos');
  const producto = document.getElementById('id_articulo_pt');
  if (!nodo || !producto) return;
  let catalogo;
  try {
    catalogo = JSON.parse(nodo.textContent);
  } catch (error) {
    return;
  }
  const pt = producto.value;
  document.querySelectorAll('select[name$="-articulo_insumo"]').forEach(function (select) {
    aplicarCatalogo(select, catalogo, pt);
  });
  const plantilla = document.getElementById('linea-vacia');
  if (plantilla && plantilla.content) {
    plantilla.content.querySelectorAll('select[name$="-articulo_insumo"]').forEach(function (select) {
      aplicarCatalogo(select, catalogo, pt);
    });
  }
}

function contarLineas() {
  const n = document.querySelectorAll('#lineas-body tr:not([hidden])').length;
  const contador = document.getElementById('contador');
  const total = document.getElementById('contador-total');
  if (contador) contador.textContent = String(n);
  if (total) total.textContent = String(n);
}

function enlazarPermisos() {
  document.querySelectorAll('.perm-row').forEach(function (fila) {
    const ver = fila.querySelector('input[name="ver"]');
    const mod = fila.querySelector('input[name="modificar"]');
    if (!ver || !mod || ver.disabled) return;
    mod.addEventListener('change', function () {
      if (mod.checked) ver.checked = true;
    });
    ver.addEventListener('change', function () {
      if (!ver.checked) mod.checked = false;
    });
  });
}

document.addEventListener('DOMContentLoaded', function () {
  contarLineas();
  filtrarInsumos();
  enlazarPermisos();
  const producto = document.getElementById('id_articulo_pt');
  if (producto) producto.addEventListener('change', filtrarInsumos);
});
