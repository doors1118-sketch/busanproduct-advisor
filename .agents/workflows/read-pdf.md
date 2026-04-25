---
description: PDF 파일 읽기 (텍스트 기반 + 이미지/스캔 기반 모두 지원)
---

# PDF 파일 읽기 워크플로우

PDF 파일을 만나면 아래 순서로 처리한다.

## 1단계: 텍스트 추출 시도

```python
import fitz
doc = fitz.open(r'PDF_PATH')
text = chr(10).join([page.get_text() for page in doc])
```

- 텍스트가 정상적으로 추출되면 → **완료**
- 텍스트가 비어있거나 극히 짧으면 (페이지당 100자 미만) → **2단계로**

## 2단계: 이미지 기반 PDF → EasyOCR로 읽기

// turbo-all

```python
import fitz
import easyocr
import os

reader = easyocr.Reader(['ko', 'en'], gpu=False)
doc = fitz.open(r'PDF_PATH')

all_text = []
for i, page in enumerate(doc):
    # 페이지를 이미지로 변환 (해상도 300dpi)
    pix = page.get_pixmap(dpi=300)
    img_path = os.path.join(r'c:\Users\doors\OneDrive\바탕 화면\사무실 메뉴얼 제작_추출\메뉴얼 제작', f'_ocr_temp_page_{i}.png')
    pix.save(img_path)
    
    # EasyOCR로 텍스트 인식
    results = reader.readtext(img_path, detail=0, paragraph=True)
    page_text = chr(10).join(results)
    all_text.append(f'=== Page {i+1} ===\n{page_text}')
    
    # 임시 이미지 삭제
    os.remove(img_path)

doc.close()
final_text = chr(10).join(all_text)

# 결과를 txt 파일로 저장
output_path = r'PDF_PATH'.replace('.pdf', '_OCR결과.txt')
with open(output_path, 'w', encoding='utf-8') as f:
    f.write(final_text)
```

## 참고사항

- **EasyOCR 첫 실행 시** 한국어 모델을 자동 다운로드 (약 100MB, 1회만)
- **인코딩 문제** 발생 시 반드시 UTF-8로 파일 저장 후 view_file로 읽을 것
- **대용량 PDF** (50페이지 이상)는 구간을 나눠서 처리
- 스캔 품질이 낮으면 `dpi=400`으로 올리면 인식률 향상
