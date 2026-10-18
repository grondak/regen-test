import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(fileURLToPath(new URL('..', import.meta.url)));
const app = readFileSync(resolve(root, 'src/web/app.js'), 'utf8');
const index = readFileSync(resolve(root, 'src/web/index.html'), 'utf8');
const style = readFileSync(resolve(root, 'src/web/style.css'), 'utf8');

test('browser inventory uses same-origin or a runtime override', () => {
  assert.match(app, /window\.TINYWMS_API_BASE_URL/);
  assert.match(app, /window\.location\.origin/);
  assert.match(app, /new URL\('\/inventory'/);
  assert.doesNotMatch(app, /127\.0\.0\.1:8000/);
});

test('inventory page submits visible order JSON with POST', () => {
  assert.match(app, /new URL\('\/orders'/);
  assert.match(app, /method:\s*'POST'/);
  assert.match(app, /JSON\.stringify\(payload\)/);
  assert.match(index, /order-json/);
  assert.match(index, /response-json/);
  assert.match(style, /#response-json/);
});

test('accepted order refreshes the rendered inventory', () => {
  assert.match(app, /responseJson\.textContent/);
  assert.match(app, /await loadInventory\(\)/);
  assert.match(app, /form\.addEventListener\('submit', submitOrder\)/);
  assert.match(app, /renderInventory/);
});
