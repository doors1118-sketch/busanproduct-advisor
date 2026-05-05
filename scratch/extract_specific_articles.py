import requests
import xml.etree.ElementTree as ET

BASE_URL = "http://www.law.go.kr/DRF"
OC = "busanproduct1"

def api_get(endpoint, params, timeout=15):
    params["OC"] = OC
    params["type"] = "XML"
    r = requests.get(f"{BASE_URL}/{endpoint}", params=params, timeout=timeout)
    r.raise_for_status()
    return ET.fromstring(r.content)

def print_article(root, target_jo_list, out_f):
    for jo in root.findall(".//조문단위"):
        jo_no_el = jo.find("조문번호")
        if jo_no_el is not None and jo_no_el.text in target_jo_list:
            title = jo.find("조문제목")
            out_f.write(f"\n[{jo_no_el.text}] {title.text if title is not None else ''}\n")
            
            content = jo.find("조문내용")
            if content is not None and content.text:
                out_f.write(content.text.strip() + "\n")
            
            for hang in jo.findall(".//항"):
                hang_el = hang.find("항내용")
                if hang_el is not None and hang_el.text:
                    out_f.write("  " + hang_el.text.strip() + "\n")
                    
                for ho in hang.findall(".//호"):
                    ho_el = ho.find("호내용")
                    if ho_el is not None and ho_el.text:
                        out_f.write("    " + ho_el.text.strip() + "\n")
                        
                    for mok in ho.findall(".//목"):
                        mok_el = mok.find("목내용")
                        if mok_el is not None and mok_el.text:
                            out_f.write("      " + mok_el.text.strip() + "\n")

with open('scratch/articles.txt', 'w', encoding='utf-8') as f:
    f.write("=" * 60 + "\n")
    f.write("지방계약법 시행령 (MST: 281055)\n")
    f.write("=" * 60 + "\n")
    root = api_get("lawService.do", {"target": "law", "MST": "281055"})
    print_article(root, ["25", "25의2", "30"], f)

    f.write("\n" + "=" * 60 + "\n")
    f.write("국가계약법 시행령 (MST: 280803)\n")
    f.write("=" * 60 + "\n")
    root2 = api_get("lawService.do", {"target": "law", "MST": "280803"})
    print_article(root2, ["26", "72"], f)
