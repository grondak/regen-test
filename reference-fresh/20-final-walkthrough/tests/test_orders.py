import json
import unittest

from src.lambda_inventory import parse_order_request, OrderValidationError


class OrderRequestTests(unittest.TestCase):
    def test_parse_order_request_accepts_valid_payload(self):
        event = {
            'body': json.dumps(
                {
                    'order_id': 'ORD-1001',
                    'lines': [
                        {'sku': 'SKU-1001', 'quantity': 2, 'description': 'Blue widget'},
                        {'sku': 'SKU-1002', 'quantity': 1},
                    ],
                }
            )
        }

        order = parse_order_request(event)

        self.assertEqual(order.order_id, 'ORD-1001')
        self.assertEqual(len(order.lines), 2)
        self.assertEqual(order.lines[0].sku, 'SKU-1001')
        self.assertEqual(order.lines[0].quantity, 2)
        self.assertEqual(order.lines[0].description, 'Blue widget')

    def test_parse_order_request_rejects_invalid_quantities(self):
        event = {'body': json.dumps({'order_id': 'ORD-1002', 'lines': [{'sku': 'SKU-1001', 'quantity': 0}]})}

        with self.assertRaises(OrderValidationError):
            parse_order_request(event)


if __name__ == '__main__':
    unittest.main()
