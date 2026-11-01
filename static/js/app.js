function agregarLinea(prefix) {
  const total = document.getElementById('id_' + prefix + '-TOTAL_FORMS');
  const body = document.getElementById('lineas-body');
  const tpl = document.getElementById('linea-vacia');
  if (!total || !body || !tpl) return;
  const index = total.value;
  const html = tpl.innerHTML.split('__prefix__').join(index);
  body.insertAdjacentHTML('beforeend', html);
  total.value = String(parseInt(index, 10) + 1);
  contarLineas();
}

function contarLineas() {
  const filas = document.querySelectorAll('#lineas-body tr');
  const n = filas.length;
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
  enlazarPermisos();
});
