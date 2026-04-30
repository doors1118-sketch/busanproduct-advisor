import json
import os

files = ['scenario_a_raw.json', 'scenario_b_raw.json', 'scenario_c_raw.json', 'scenario_d_raw.json']
out_content = ""

for f in files:
    try:
        with open(f, 'r', encoding='utf-8-sig') as file:
            data = json.load(file)
            out_content += f"\n### {f}\n```json\n{json.dumps(data, ensure_ascii=False, indent=2)}\n```\n"
    except Exception as e:
        out_content += f"\n### {f}\nError reading file: {e}\n"

with open('final_raw_results.md', 'w', encoding='utf-8') as out_file:
    out_file.write(out_content)
