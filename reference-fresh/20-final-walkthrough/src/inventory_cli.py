#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

REQUIRED_FIELDS = ("sku", "description", "bin_location", "quantity", "unit")


def load_inventory(path: Path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SystemExit(f"error: cannot read {path}: {exc}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"error: invalid JSON in {path}: {exc}")

    if not isinstance(data, list):
        raise SystemExit("error: inventory JSON must be an array")

    for index, item in enumerate(data):
        if not isinstance(item, dict):
            raise SystemExit(f"error: inventory item {index} must be an object")
        missing = [field for field in REQUIRED_FIELDS if field not in item]
        if missing:
            raise SystemExit(f"error: inventory item {index} missing required fields: {', '.join(missing)}")
    return data


def command_list(items):
    for item in items:
        print(f"{item['sku']}\t{item['description']}\t{item['bin_location']}\t{item['quantity']} {item['unit']}")


def command_find(items, sku):
    for item in items:
        if item["sku"] == sku:
            print(json.dumps(item, indent=2, sort_keys=True))
            return 0
    print(f"error: SKU not found: {sku}", file=sys.stderr)
    return 1


def command_dump(items):
    print(json.dumps(items, indent=2, sort_keys=True))


def build_parser():
    parser = argparse.ArgumentParser(description="TinyWMS inventory CLI")
    parser.add_argument("inventory_file", type=Path)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list")
    find_parser = subparsers.add_parser("find")
    find_parser.add_argument("sku")
    subparsers.add_parser("dump")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    items = load_inventory(args.inventory_file)
    if args.command == "list":
        command_list(items)
        return 0
    if args.command == "find":
        return command_find(items, args.sku)
    if args.command == "dump":
        command_dump(items)
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
