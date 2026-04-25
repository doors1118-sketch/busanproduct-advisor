import os
import json
import time
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

pdfs = [
    r"C:\Users\doors\OneDrive\바탕 화면\사무실 메뉴얼 제작_추출\메뉴얼 제작\계약메뉴얼\(1권) 2025 공공구매제도 실무가이드.pdf",
    r"C:\Users\doors\OneDrive\바탕 화면\사무실 메뉴얼 제작_추출\메뉴얼 소스\(25.9.15)지방계약 실무 매뉴얼.pdf" # Wait, the path is in 계약메뉴얼
]
pdfs[1] = r"C:\Users\doors\OneDrive\바탕 화면\사무실 메뉴얼 제작_추출\메뉴얼 제작\계약메뉴얼\(25.9.15)지방계약 실무 매뉴얼.pdf"

def extract_from_pdf(pdf_path):
    print(f"Uploading {os.path.basename(pdf_path)}...")
    uploaded_file = genai.upload_file(pdf_path)
    
    print("Waiting for processing...")
    while uploaded_file.state.name == "PROCESSING":
        time.sleep(5)
        uploaded_file = genai.get_file(uploaded_file.name)
        
    print("Extracting...")
    model = genai.GenerativeModel("gemini-2.5-flash")
    prompt = """
    이 문서는 공공계약 및 구매제도 실무 가이드/매뉴얼입니다.
    문서 내부를 꼼꼼히 살펴보고, '자주 묻는 질문', 'Q&A', '질의응답' 섹션을 모두 찾으세요.
    해당 섹션에 있는 **모든 질문(Q)**들만 추출해서 JSON 배열 형식으로 반환하세요.
    응답이나 다른 텍스트는 제외하고 순수하게 '질문' 텍스트만 문자열 배열로 만들어주세요.
    예시: ["계약보증금 면제 대상은 어떻게 되나요?", "하도급 대금 직불 조건은 무엇인가요?"]
    반드시 JSON 형식으로만 응답하세요.
    """
    
    response = model.generate_content([uploaded_file, prompt])
    text = response.text.strip()
    
    if text.startswith('```json'):
        text = text[7:-3]
    elif text.startswith('```'):
        text = text[3:-3]
        
    try:
        q_list = json.loads(text)
        return q_list
    except Exception as e:
        print(f"Failed to parse JSON: {e}")
        print(text[:200])
        return []

all_questions = {}
for p in pdfs:
    qs = extract_from_pdf(p)
    all_questions[os.path.basename(p)] = qs
    print(f"Extracted {len(qs)} questions from {os.path.basename(p)}")

with open("qa_list.json", "w", encoding="utf-8") as f:
    json.dump(all_questions, f, ensure_ascii=False, indent=2)

total = sum(len(qs) for qs in all_questions.values())
print(f"Total questions extracted: {total}")
