const $ = (selector) => document.querySelector(selector);
const savedMargin = Number.parseInt(localStorage.getItem('profitMargin') || '30', 10);
const savedRate = Number.parseFloat(localStorage.getItem('bcvRate') || '');
const state = {
  query: '',
  timer: null,
  pinConfigured: true,
  margin: Number.isFinite(savedMargin) && savedMargin >= 0 && savedMargin <= 200 ? savedMargin : 30,
  rate: Number.isFinite(savedRate) && savedRate > 0 ? savedRate : null,
  hideCost: localStorage.getItem('hideCost') === '1',
  items: []
};
const money = new Intl.NumberFormat('es-VE', { style: 'currency', currency: 'USD', minimumFractionDigits: 2 });
const bolivar = new Intl.NumberFormat('es-VE', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

function bolivarPrice(usd) {
  return state.rate ? `Bs. ${bolivar.format(usd * state.rate)}` : '';
}
const number = new Intl.NumberFormat('es-VE', { maximumFractionDigits: 2 });

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, char => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', "'":'&#39;', '"':'&quot;' }[char]));
}

function formatDate(value) {
  if (!value) return 'Sin datos';
  return new Intl.DateTimeFormat('es-VE', { day:'2-digit', month:'short', year:'numeric' }).format(new Date(value));
}

async function request(url, options) {
  const response = await fetch(url, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || 'No se pudo completar la solicitud');
  return data;
}

async function loadStats() {
  const data = await request('/api/stats');
  $('#statProducts').textContent = number.format(data.count);
  $('#statUnits').textContent = number.format(data.units);
  $('#statDate').textContent = formatDate(data.updated_at);
  state.pinConfigured = data.pin_configured;
  $('#pinSetup').classList.toggle('hidden', data.pin_configured);
  $('#uploadFields').classList.toggle('hidden', !data.pin_configured);
}

function productRow(item) {
  const out = item.stock <= 0;
  const sale = item.cost * (1 + state.margin / 100);
  return `<tr>
    <td><div class="product-name">${escapeHtml(item.description)}</div></td>
    <td><span class="code">${escapeHtml(item.code)}</span></td>
    <td><span class="stock ${out ? 'out' : ''}">${out ? 'Agotado' : number.format(item.stock)}</span></td>
    <td class="cost-value">${money.format(item.cost)}</td>
    <td class="sale-price">${money.format(sale)}${state.rate ? `<div>${bolivarPrice(sale)}</div>` : ''}</td>
  </tr>`;
}

function productCard(item) {
  const out = item.stock <= 0;
  const sale = item.cost * (1 + state.margin / 100);
  return `<article class="card">
    <div class="cost-line"><span>Costo</span><strong>${money.format(item.cost)}</strong></div>
    <div class="card-top"><h3>${escapeHtml(item.description)}</h3><div class="sale-block"><span>Venta +${state.margin}%</span><strong>${money.format(sale)}</strong>${state.rate ? `<strong>${bolivarPrice(sale)}</strong>` : ''}</div></div>
    <div class="card-bottom"><span class="code">${escapeHtml(item.code)}</span><span class="stock ${out ? 'out' : ''}">${out ? 'Agotado' : number.format(item.stock) + ' disp.'}</span></div>
  </article>`;
}

function renderProducts() {
  $('#marginValue').textContent = `${state.margin}%`;
  $('#saleHeader').textContent = `Venta +${state.margin}%`;
  const slider = $('#marginSlider');
  slider.value = state.margin;
  slider.style.setProperty('--range-progress', `${state.margin / 2}%`);
  document.querySelectorAll('[data-margin]').forEach(button => {
    button.classList.toggle('active', Number(button.dataset.margin) === state.margin);
  });
  $('#rateLabel').textContent = state.rate ? `BCV Bs. ${bolivar.format(state.rate)}` : 'Dólar BCV';
  $('#productRows').innerHTML = state.items.map(productRow).join('');
  $('#mobileCards').innerHTML = state.items.map(productCard).join('');
}

function setMargin(value) {
  state.margin = Math.min(200, Math.max(0, Number(value)));
  localStorage.setItem('profitMargin', String(state.margin));
  renderProducts();
}

async function loadProducts(query = '') {
  $('#loading').classList.remove('hidden');
  $('#empty').classList.add('hidden');
  $('#desktopTable').classList.add('hidden');
  $('#mobileCards').classList.add('hidden');
  $('#limitNote').classList.add('hidden');
  try {
    const data = await request(`/api/products?q=${encodeURIComponent(query)}&limit=100`);
    state.items = data.items;
    $('#loading').classList.add('hidden');
    $('#resultTitle').textContent = query ? `Resultados para “${query}”` : 'Todos los productos';
    $('#resultMeta').textContent = `${number.format(data.count)} ${data.count === 1 ? 'producto encontrado' : 'productos encontrados'}`;
    $('#clearSearch').classList.toggle('hidden', !query);
    if (!data.items.length) {
      renderProducts();
      $('#empty').classList.remove('hidden');
      return;
    }
    renderProducts();
    $('#desktopTable').classList.remove('hidden');
    $('#mobileCards').classList.remove('hidden');
    if (data.count > data.items.length) {
      $('#limitNote').textContent = `Mostrando los primeros ${data.items.length}. Escribe más letras para precisar la búsqueda.`;
      $('#limitNote').classList.remove('hidden');
    }
  } catch (error) {
    $('#loading').innerHTML = `<strong>No se pudo cargar:</strong> ${escapeHtml(error.message)}`;
  }
}

$('#marginSlider').value = state.margin;
$('#hideCost').checked = state.hideCost;
document.body.classList.toggle('hide-cost', state.hideCost);
$('#hideCost').addEventListener('change', event => {
  state.hideCost = event.target.checked;
  localStorage.setItem('hideCost', state.hideCost ? '1' : '0');
  document.body.classList.toggle('hide-cost', state.hideCost);
});
$('#marginSlider').addEventListener('input', event => setMargin(event.target.value));
document.querySelectorAll('[data-margin]').forEach(button => {
  button.addEventListener('click', () => setMargin(button.dataset.margin));
});

$('#search').addEventListener('input', event => {
  state.query = event.target.value.trim();
  clearTimeout(state.timer);
  state.timer = setTimeout(() => loadProducts(state.query), 90);
});

$('#clearSearch').addEventListener('click', () => {
  $('#search').value = '';
  state.query = '';
  loadProducts();
  $('#search').focus();
});

document.addEventListener('keydown', event => {
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
    event.preventDefault();
    $('#search').focus();
  }
  if (event.key === 'Escape' && $('#uploadDialog').open) $('#uploadDialog').close();
  if (event.key === 'Escape' && $('#rateDialog').open) $('#rateDialog').close();
});

$('#openRate').addEventListener('click', () => {
  $('#rateInput').value = state.rate ? bolivar.format(state.rate) : '';
  $('#rateStatus').classList.add('hidden');
  $('#rateDialog').showModal();
  $('#rateInput').select();
});
$('#closeRate').addEventListener('click', () => $('#rateDialog').close());
$('#rateDialog').addEventListener('click', event => {
  if (event.target === $('#rateDialog')) $('#rateDialog').close();
});

$('#rateForm').addEventListener('submit', event => {
  event.preventDefault();
  const raw = $('#rateInput').value.trim().replace(/\s/g, '');
  if (!raw) {
    state.rate = null;
    localStorage.removeItem('bcvRate');
  } else {
    // Acepta formato venezolano: 1.234,56 o 36,50
    const value = Number.parseFloat(raw.includes(',') ? raw.replace(/\./g, '').replace(',', '.') : raw);
    if (!Number.isFinite(value) || value <= 0) {
      $('#rateStatus').textContent = 'Escribe un número mayor que cero, por ejemplo 36,50.';
      $('#rateStatus').classList.remove('hidden');
      return;
    }
    state.rate = value;
    localStorage.setItem('bcvRate', String(value));
  }
  $('#rateDialog').close();
  renderProducts();
});

$('#openUpload').addEventListener('click', () => $('#uploadDialog').showModal());
$('#closeUpload').addEventListener('click', () => $('#uploadDialog').close());
$('#uploadDialog').addEventListener('click', event => {
  if (event.target === $('#uploadDialog')) $('#uploadDialog').close();
});

$('#excelFile').addEventListener('change', event => {
  const file = event.target.files[0];
  $('#fileLabel').textContent = file ? file.name : 'Seleccionar archivo Excel';
});

function showStatus(message, error = false) {
  const node = $('#uploadStatus');
  node.textContent = message;
  node.classList.remove('hidden');
  node.classList.toggle('error', error);
}

$('#savePin').addEventListener('click', async () => {
  const button = $('#savePin');
  const pin = $('#newPin').value.trim();
  button.disabled = true;
  try {
    await request('/api/setup-pin', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ pin }) });
    showStatus('Clave creada. Ya puedes importar tu archivo.');
    await loadStats();
    $('#pin').focus();
  } catch (error) {
    showStatus(error.message, true);
  } finally { button.disabled = false; }
});

$('#uploadForm').addEventListener('submit', async event => {
  event.preventDefault();
  const file = $('#excelFile').files[0];
  if (!file) return showStatus('Selecciona un archivo .xlsx.', true);
  const button = $('#uploadButton');
  const form = new FormData();
  form.append('file', file);
  form.append('pin', $('#pin').value);
  button.disabled = true;
  button.textContent = 'Importando…';
  showStatus('Leyendo y validando el archivo…');
  try {
    const data = await request('/api/import', { method:'POST', body:form });
    const warning = data.errors.length ? ` Se omitieron ${data.errors.length} filas con errores.` : '';
    showStatus(`Listo: ${number.format(data.count)} productos publicados.${warning}`);
    $('#excelFile').value = '';
    $('#fileLabel').textContent = 'Seleccionar archivo Excel';
    await Promise.all([loadStats(), loadProducts(state.query)]);
  } catch (error) {
    showStatus(error.message, true);
  } finally {
    button.disabled = false;
    button.textContent = 'Importar y publicar';
  }
});

renderProducts();
Promise.all([loadStats(), loadProducts()]).catch(error => console.error(error));
