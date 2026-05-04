import json, sys, os, hashlib, fitz
sys.stdout.reconfigure(encoding='utf-8')

base = r'c:\Users\COMTREE\Desktop\메뉴얼 제작\app\data'
candidate_path = os.path.join(base, 'legal_source_registry_master_by_jurisdiction_v0_1_candidate.json')

pdf_paths = {
    '지방자치단체 입찰시 낙찰자 결정기준': r'C:\Users\COMTREE\Desktop\[개정전문] 지방자치단체 입찰시 낙찰자 결정기준.pdf',
    '지방자치단체 입찰 및 계약집행기준': r'C:\Users\COMTREE\Desktop\지방자치단체 입찰 및 계약집행기준(행정안전부예규)(제332호)(20250708).pdf'
}

with open(candidate_path, encoding='utf-8') as f:
    cand = json.load(f)

updated_count = 0

for c in cand:
    norm_title = c.get('normalized_title')
    if norm_title in pdf_paths:
        fp = pdf_paths[norm_title]
        if os.path.exists(fp):
            with open(fp, 'rb') as f_pdf:
                b = f_pdf.read()
                file_hash = hashlib.sha256(b).hexdigest()
            
            doc = fitz.open(fp)
            text = chr(10).join([page.get_text() for page in doc])
            page_count = doc.page_count
            doc.close()
            
            c['source_file_path'] = fp
            c['source_file_hash'] = file_hash
            c['full_text_length'] = len(text)
            c['article_count'] = page_count # Temporarily using page count for article count as requested
            c['review_status'] = 'verified'
            c['registry_trust_level'] = 'verified'
            c['source_type'] = 'pdf_manual'
            
            updated_count += 1
            print(f"Updated {norm_title}: Hash {file_hash[:8]}, Length {len(text)}")
        else:
            print(f"File missing for {norm_title}: {fp}")

if updated_count > 0:
    with open(candidate_path, 'w', encoding='utf-8') as f:
        json.dump(cand, f, ensure_ascii=False, indent=2)
    print(f"Saved candidate json with {updated_count} updates.")
