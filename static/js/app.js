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
  pintarMaquinasRuta();
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
  pintarMaquinasRuta();
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

function pintarMaquinasRuta() {
  const nodo = document.getElementById('catalogo-maquinas');
  const lista = document.getElementById('maquinas-ruta');
  if (!nodo || !lista) return;
  let catalogo;
  try {
    catalogo = JSON.parse(nodo.textContent);
  } catch (error) {
    return;
  }
  lista.innerHTML = '';
  const filas = document.querySelectorAll('#lineas-body tr:not([hidden])');
  filas.forEach(function (fila) {
    const select = fila.querySelector('select[name$="-proceso"]');
    const secuencia = fila.querySelector('input[name$="-secuencia"]');
    if (!select) return;
    const opcion = select.options[select.selectedIndex];
    const etiqueta = opcion && opcion.value ? opcion.textContent : '';
    const numero = secuencia && secuencia.value ? secuencia.value + ' · ' : '';
    const item = document.createElement('li');
    if (!select.value) {
      item.textContent = numero + 'Elija un proceso para ver las máquinas que pueden realizarlo.';
    } else {
      const maquinas = catalogo[String(select.value)] || [];
      if (!maquinas.length) {
        item.textContent = numero + etiqueta + ' — ninguna máquina activa puede realizarlo.';
      } else {
        const nombres = maquinas.map(function (maquina) {
          return maquina.codigo + ' ' + maquina.nombre;
        }).join(', ');
        item.textContent = numero + etiqueta + ' — ' + nombres;
      }
    }
    lista.appendChild(item);
  });
}

function contarLineas() {
  const n = document.querySelectorAll('#lineas-body tr:not([hidden])').length;
  const contador = document.getElementById('contador');
  const total = document.getElementById('contador-total');
  if (contador) contador.textContent = String(n);
  if (total) total.textContent = String(n);
}

function enlazarAutofiltro() {
  document.querySelectorAll('form[data-autofiltro]').forEach(function (form) {
    form.querySelectorAll('select, input[type="checkbox"], input[type="radio"], input[type="date"]').forEach(function (control) {
      control.addEventListener('change', function () {
        form.submit();
      });
    });
    form.querySelectorAll('input[type="search"], input[type="text"]').forEach(function (campo) {
      campo.addEventListener('keydown', function (event) {
        if (event.key !== 'Enter') return;
        event.preventDefault();
        form.submit();
      });
    });
  });
}

function enlazarConfirmacion() {
  document.querySelectorAll('form[data-confirmar]').forEach(function (form) {
    form.addEventListener('submit', function (event) {
      const texto = form.getAttribute('data-confirmar');
      if (texto && !window.confirm(texto)) event.preventDefault();
    });
  });
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

var MESES = [
  '', 'ENERO', 'FEBRERO', 'MARZO', 'ABRIL', 'MAYO', 'JUNIO',
  'JULIO', 'AGOSTO', 'SEPTIEMBRE', 'OCTUBRE', 'NOVIEMBRE', 'DICIEMBRE',
];

function pintarMes() {
  var fecha = document.getElementById('id_fecha');
  var mes = document.getElementById('mes-derivado');
  if (!fecha || !mes) return;
  var numero = parseInt((fecha.value || '').slice(5, 7), 10);
  mes.value = MESES[numero] || '';
}

document.addEventListener('DOMContentLoaded', function () {
  contarLineas();
  filtrarInsumos();
  pintarMaquinasRuta();
  pintarMes();
  enlazarAutofiltro();
  enlazarConfirmacion();
  enlazarPermisos();
  var fecha = document.getElementById('id_fecha');
  if (fecha) {
    fecha.addEventListener('change', pintarMes);
    fecha.addEventListener('input', pintarMes);
  }
  document.addEventListener('change', function (event) {
    const nombre = event.target && event.target.name;
    if (nombre && nombre.indexOf('-proceso') !== -1) pintarMaquinasRuta();
  });
  const producto = document.getElementById('id_articulo_pt');
  if (producto) producto.addEventListener('change', filtrarInsumos);
});
