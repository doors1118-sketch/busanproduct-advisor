import sys

filepath = 'phase8_gateway_export_flat/test_runtime_integration_v0_1.py'
with open(filepath, 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('"proceed_to_rule_engine"', '"local_purchase_support_flow"')

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(text)
