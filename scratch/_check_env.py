import os

with open('.env', 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if '=' not in line:
            continue
        key = line.split('=', 1)[0].strip()
        val = line.split('=', 1)[1].strip().strip('"').strip("'")
        has_val = len(val) > 0
        print(f'{key}: has_value={has_val}, len={len(val)}')
