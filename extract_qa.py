import fitz
import re
import os

pdf1 = r"C:\Users\doors\OneDrive\바탕 화면\사무실 메뉴얼 제작_추출\메뉴얼 제작\계약메뉴얼\(1권) 2025 공공구매제도 실무가이드.pdf"
pdf2 = r"C:\Users\doors\OneDrive\바탕 화면\사무실 메뉴얼 제작_추출\메뉴얼 제작\계약메뉴얼\(25.9.15)지방계약 실무 매뉴얼.pdf"

def extract_qa(pdf_path):
    questions = []
    if not os.path.exists(pdf_path):
        print(f"File not found: {pdf_path}")
        return questions
        
    doc = fitz.open(pdf_path)
    for i in range(len(doc)):
        text = doc[i].get_text()
        # Look for lines starting with Q. Q: 질문: 질의 등
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            if re.match(r'^(Q\.|Q\s*:|질의\s*|질문\s*)', line, re.IGNORECASE):
                if len(line) > 10:  # Avoid too short lines
                    questions.append(line)
    doc.close()
    return questions

q1 = extract_qa(pdf1)
q2 = extract_qa(pdf2)

print(f"Total Qs in PDF 1: {len(q1)}")
print(f"Sample: {q1[:3]}")
print(f"Total Qs in PDF 2: {len(q2)}")
print(f"Sample: {q2[:3]}")

# Save to a file for later use
with open("extracted_qa.txt", "w", encoding="utf-8") as f:
    f.write(f"--- PDF 1 ---\n")
    for q in q1:
        f.write(q + "\n")
    f.write(f"\n--- PDF 2 ---\n")
    for q in q2:
        f.write(q + "\n")
