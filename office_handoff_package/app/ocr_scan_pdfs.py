"""스캔 PDF OCR 처리 → 텍스트 파일 저장"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import fitz
import easyocr
import os

reader = easyocr.Reader(['ko', 'en'], gpu=False)

SCAN_PDFS = [
    r"C:\Users\COMTREE\Desktop\메뉴얼 제작\계약메뉴얼\2025 조합추천수의계약 제도 안내자료.pdf",
    r"C:\Users\COMTREE\Desktop\메뉴얼 제작\계약메뉴얼\[2026 공공구매지원 설명회 자료] 성능인증제도.pdf",
    r"C:\Users\COMTREE\Desktop\메뉴얼 제작\계약메뉴얼\[2026 공공구매지원 설명회 자료] 직접생산확인제도.pdf",
]

for pdf_path in SCAN_PDFS:
    if not os.path.exists(pdf_path):
        print(f"[SKIP] not found: {os.path.basename(pdf_path)}")
        continue

    fname = os.path.basename(pdf_path)
    output_path = pdf_path.replace('.pdf', '_OCR.txt')
    print(f"\n[OCR] {fname}")

    doc = fitz.open(pdf_path)
    all_text = []

    for i, page in enumerate(doc):
        pix = page.get_pixmap(dpi=200)  # 200dpi (속도-품질 균형)
        img_path = os.path.join(os.environ['TEMP'], f'_ocr_page_{i}.png')
        pix.save(img_path)

        results = reader.readtext(img_path, detail=0, paragraph=True)
        page_text = '\n'.join(results)
        all_text.append(f"=== Page {i+1} ===\n{page_text}")

        os.remove(img_path)

        if (i + 1) % 10 == 0 or i == len(doc) - 1:
            print(f"  page {i+1}/{len(doc)}")

    doc.close()

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n\n'.join(all_text))

    print(f"  -> saved: {os.path.basename(output_path)} ({len(all_text)} pages)")

print("\n[DONE] OCR complete")
