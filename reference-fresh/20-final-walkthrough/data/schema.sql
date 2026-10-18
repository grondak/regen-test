CREATE TABLE inventory (
  sku TEXT PRIMARY KEY,
  description TEXT NOT NULL,
  bin_location TEXT NOT NULL,
  quantity INTEGER NOT NULL CHECK (quantity >= 0),
  unit TEXT NOT NULL
);

CREATE TABLE orders (
  order_id TEXT PRIMARY KEY,
  status TEXT NOT NULL
);

CREATE TABLE order_lines (
  order_id TEXT NOT NULL,
  sku TEXT NOT NULL,
  quantity INTEGER NOT NULL CHECK (quantity > 0),
  PRIMARY KEY (order_id, sku),
  FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE,
  FOREIGN KEY (sku) REFERENCES inventory(sku)
);
