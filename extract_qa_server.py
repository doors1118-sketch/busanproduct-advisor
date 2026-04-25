import os
import json
import time
import shutil
from google import genai
from dotenv import load_dotenv

load_dotenv("/root/advisor/.env")
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

pdfs = [
    "/root/advisor/계약메뉴얼/(1권) 2025 공공구매제도 실무가이드.pdf",
    "/root/advisor/계약메뉴얼/(25.9.15)지방계약 실무 매뉴얼.pdf"
]

def extract_from_pdf(pdf_path):
    print(f"Uploading {os.path.basename(pdf_path)}...")
    
    # Avoid Unicode HTTP header issues by using ASCII filename
    temp_path = "/root/advisor/temp_upload.pdf"
    shutil.copy2(pdf_path, temp_path)
    
    uploaded_file = client.files.upload(file=temp_path)
    
    print("Waiting for processing...")
    # Polling state
    while True:
        f = client.files.get(name=uploaded_file.name)
        if f.state == "ACTIVE":
            break
        elif f.state == "FAILED":
            print("File processing failed.")
            return []
        time.sleep(5)
        
    print("Extracting...")
    prompt = """
    이 문서는 공공계약 및 구매제도 실무 가이드/매뉴얼입니다.
    문서 내부를 꼼꼼히 살펴보고, '자주 묻는 질문', 'Q&A', '질의응답', 'FAQ', '문. (질문)' 등 질문과 답변이 있는 섹션을 모두 찾으세요.
    해당 섹션에 있는 **모든 질문(Q)**들만 추출해서 JSON 배열 형식으로 반환하세요.
    응답이나 다른 텍스트는 제외하고 순수하게 '질문' 텍스트만 문자열 배열로 만들어주세요.
    만약 그런 섹션이 없다면 빈 배열 [] 을 반환하세요.
    예시: ["계약보증금 면제 대상은 어떻게 되나요?", "하도급 대금 직불 조건은 무엇인가요?"]
    반드시 JSON 형식으로만 응답하세요.
    """
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=[f, prompt]
    )
    text = response.text.strip()
    
    if text.startswith('```json'):
        text = text[7:-3]
    elif text.startswith('```'):
        text = text[3:-3]
        
    try:
        q_list = json.loads(text)
        # delete the file after use
        client.files.delete(name=uploaded_file.name)
        os.remove(temp_path)
        return q_list
    except Exception as e:
        print(f"Failed to parse JSON: {e}")
        print(text[:200])
        os.remove(temp_path)
        return []

all_questions = {}
for p in pdfs:
    if os.path.exists(p):
        qs = extract_from_pdf(p)
        all_questions[os.path.basename(p)] = qs
        print(f"Extracted {len(qs)} questions from {os.path.basename(p)}")
    else:
        print(f"File not found: {p}")

with open("/root/advisor/qa_list.json", "w", encoding="utf-8") as f:
    json.dump(all_questions, f, ensure_ascii=False, indent=2)

total = sum(len(qs) for qs in all_questions.values())
print(f"Total questions extracted: {total}")
