const apiBase = window.TINYWMS_API_BASE_URL || window.location.origin;
const inventoryUrl = new URL('/inventory', apiBase).toString();
const ordersUrl = new URL('/orders', apiBase).toString();
const status = document.getElementById('status');
const body = document.getElementById('inventory-body');
const error = document.getElementById('error');
const form = document.getElementById('order-form');
const orderJson = document.getElementById('order-json');
const submitStatus = document.getElementById('submit-status');
const refreshButton = document.getElementById('refresh-button');
const apiBaseLabel = document.getElementById('api-base');
const responseJson = document.getElementById('response-json');

apiBaseLabel.textContent = apiBase;

function renderInventory(items) {
  status.textContent = `Loaded ${items.length} items`;
  body.innerHTML = items
    .map(
      (item) => `
        <tr>
          <td>${item.sku}</td>
          <td>${item.description}</td>
          <td>${item.bin_location}</td>
          <td data-sku="${item.sku}">${item.quantity}</td>
          <td>${item.unit}</td>
        </tr>`,
    )
    .join('');
}

function loadInventory() {
  error.textContent = '';
  return fetch(inventoryUrl)
    .then((response) => {
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      return response.json();
    })
    .then(renderInventory)
    .catch((err) => {
      status.textContent = 'Failed to load inventory';
      error.textContent = err.message;
    });
}

function defaultOrder() {
  return {
    order_id: `ORD-${Date.now()}`,
    lines: [{ sku: 'SKU-1001', quantity: 1 }],
  };
}

function syncEditor() {
  orderJson.value = JSON.stringify(defaultOrder(), null, 2);
}

function submitOrder(event) {
  event.preventDefault();
  submitStatus.textContent = 'Submitting order...';
  error.textContent = '';
  responseJson.textContent = '';
  let payload;
  try {
    payload = JSON.parse(orderJson.value);
  } catch (err) {
    submitStatus.textContent = 'Order JSON is invalid';
    error.textContent = err.message;
    return;
  }
  fetch(ordersUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
    .then(async (response) => {
      const responseBody = await response.json();
      responseJson.textContent = JSON.stringify(responseBody, null, 2);
      if (!response.ok) {
        throw new Error(responseBody.error || `HTTP ${response.status}`);
      }
      submitStatus.textContent = `Accepted ${responseBody.order_id}`;
      await loadInventory();
    })
    .catch((err) => {
      submitStatus.textContent = 'Order rejected';
      error.textContent = err.message;
    });
}

refreshButton.addEventListener('click', loadInventory);
form.addEventListener('submit', submitOrder);
syncEditor();
loadInventory();
