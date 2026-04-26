"""patch verify logic v3 - byte level"""
with open('app/gemini_engine.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the line with f-string findall
target_line_no = None
for i, line in enumerate(lines):
    if "pairs = re.findall(f'" in line and "law_name_pattern" in line:
        target_line_no = i
        break

if target_line_no is None:
    print("Target line not found")
    exit(1)

print(f"Found target at line {target_line_no + 1}")

# Find the start of the verify block: "# 해당 줄에서 법령명+조문 쌍 추출"
start = target_line_no - 1  # comment line before

# Find end: "    answer = " after this block
end = None
for i in range(target_line_no, len(lines)):
    if lines[i].strip().startswith("if not is_verified:"):
        # skip 2 more lines (the replace line and new_lines.append)
        end = i + 2  # lines[i], lines[i+1], lines[i+2]
        # Find the actual "    answer" line
        for j in range(i, min(i+5, len(lines))):
            if "answer =" in lines[j] and "join" in lines[j]:
                end = j
                break
        break

print(f"Block: lines {start+1} to {end+1}")

# Also add combined_pattern before "# 답변에서 법령 인용을 줄 단위로 검증"
for i in range(max(0, start-5), start):
    if "# 답변에서 법령 인용을 줄 단위로 검증" in lines[i]:
        # Insert combined_pattern after this line
        lines.insert(i+1, "    combined_pattern = re.compile(law_name_pattern + r'\\s*' + article_pattern)\n")
        # Adjust indices
        start += 1
        end += 1
        target_line_no += 1
        print(f"Inserted combined_pattern at line {i+2}")
        break

# Replace the old block
new_block = [
    "            # 해당 줄에서 법령명+조문 쌍 추출\n",
    "            found_pairs = []\n",
    "            for m in combined_pattern.finditer(line):\n",
    "                full = m.group(0)\n",
    "                ln_m = re.match(law_name_pattern, full)\n",
    "                art_m = re.search(article_pattern, full)\n",
    "                if ln_m and art_m:\n",
    "                    found_pairs.append((ln_m.group(0).strip(), art_m.group(0)))\n",
    "            articles_only = re.findall(article_pattern, line)\n",
    "            is_verified = True\n",
    "\n",
    "            if found_pairs:\n",
    "                for law_name, article in found_pairs:\n",
    "                    if (law_name, article) not in verified_law_articles:\n",
    "                        is_verified = False\n",
    "                        break\n",
    "            elif articles_only:\n",
    "                for art in articles_only:\n",
    "                    if art not in verified_articles_only:\n",
    "                        is_verified = False\n",
    "                        break\n",
]

lines[start:end] = new_block
    
with open('app/gemini_engine.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("OK: patched")
