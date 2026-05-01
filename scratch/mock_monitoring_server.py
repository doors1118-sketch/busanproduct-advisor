from fastapi import FastAPI
import uvicorn

app = FastAPI()

def mock_response():
    return {
        "meta": {"source_refreshed_at": {"company_master": "2026-05-02T03:00:00+09:00"}},
        "candidates": [
            {
                "company_id": "hmac_pseudonymous_id_123",
                "company_name": "테스트업체",
                "location": "부산광역시 테스트구",
                "license_or_business_type": ["소방시설공사업"],
                "main_products": ["책상", "의자"],
                "candidate_types": ["local_procurement_company"],
                "primary_candidate_type": "local_procurement_company",
                "route_codes": ["LOCAL_VENDOR_REVIEW"],
                "check_codes": ["CHECK_REG"],
                "business_status": "active",
                "display_status": "후보",
                "source_refs": ["company_master"]
            }
        ]
    }

def mock_list_response():
    return {
        "meta": {"source_refreshed_at": {"company_master": "2026-05-02T03:00:00+09:00"}},
        "candidates": [
            {"name": "소방시설공사업", "count": 100},
            {"name": "전기공사업", "count": 150}
        ]
    }

@app.get("/api/chatbot/company/license-search")
def license_search(license_name: str = ""): return mock_response()

@app.get("/api/chatbot/company/product-search")
def product_search(product_name: str = ""): return mock_response()

@app.get("/api/chatbot/company/category-search")
def category_search(category_name: str = ""): return mock_response()

@app.get("/api/chatbot/company/manufacturers")
def manufacturers(product_name: str = ""): return mock_response()

@app.get("/api/chatbot/company/license-list")
def license_list(): return mock_list_response()

@app.get("/api/chatbot/company/product-list")
def product_list(): return mock_list_response()

@app.get("/api/chatbot/company/category-list")
def category_list(): return mock_list_response()

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
