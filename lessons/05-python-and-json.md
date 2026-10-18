# Session 5 — Only the Python you need, and JSON

**Stage:** `01-json-backbone` · **Repo support:** Yes · **Run from:** `01-json-backbone/`

**Concept (20 min):** values, lists, dictionaries, loops, functions, files; JSON objects/arrays/types and serialization.
**Demo (20 min):** load `inventory.json`, print inventory, find a SKU, change a quantity, serialize back to JSON.

## Run sheet

**Step 1: look at the data first.**
```bash
cat data/inventory.json                       # an array of 3 objects
python3 -m json.tool data/inventory.json      # same, pretty-printed and validated
```
Map JSON to Python: array → list, object → dict, string → str, number → int, `true/false/null` → `True/False/None`.

**Step 2: the repo's CLI does it for you; read its code afterwards.**
```bash
python3 src/inventory_cli.py data/inventory.json list
python3 src/inventory_cli.py data/inventory.json find SKU-1001
python3 src/inventory_cli.py data/inventory.json find NOPE; echo "exit: $?"     # error on stderr, exit 1
python3 src/inventory_cli.py data/inventory.json dump
```
`src/inventory_cli.py` is about 60 lines and uses every Python feature this session needs: functions, a loop, a dict lookup, file reading, `json.loads` and `json.dumps`.

**Step 3: live-code the demo yourself (the CLI cannot change a quantity).** Type this in a Python prompt (`python3`) or a file; work on a copy, not the original:
```python
import json
items = json.load(open('data/inventory.json'))     # list of dicts
for item in items:                                  # loop
    print(item['sku'], item['quantity'])
def find(sku):                                      # function
    for item in items:
        if item['sku'] == sku:
            return item
widget = find('SKU-1001')
widget['quantity'] -= 1                             # change a quantity
json.dump(items, open('/tmp/inventory-changed.json', 'w'), indent=2)    # serialize back
```
```bash
python3 src/inventory_cli.py /tmp/inventory-changed.json find SKU-1001   # the CLI reads your output
diff data/inventory.json /tmp/inventory-changed.json
```

**Step 4: break it on purpose.** Remove a comma from a copy of the file and run the CLI to read the JSON error. Delete the `unit` field from one item to see the contract check (`missing required fields`).

## Talking points
- JSON is text. `json.loads`/`json.dumps` convert between that text and Python values; the file on disk is the "wire format".
- The required fields (`sku`, `description`, `bin_location`, `quantity`, `unit`) are the contract the whole course keeps.
- Keep the Python minimal: no classes, no imports beyond `json`/`sys`. The point is the data, not the language.
