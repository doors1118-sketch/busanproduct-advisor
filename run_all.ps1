$ErrorActionPreference = "Stop"

Write-Host "Installing PyMuPDF..."
.venv312\Scripts\python.exe -m pip install PyMuPDF

Write-Host "Running ingest_manuals.py..."
.venv312\Scripts\python.exe app\ingest_manuals.py

Write-Host "Running ingest_pps_qa.py..."
.venv312\Scripts\python.exe app\ingest_pps_qa.py

Write-Host "Re-building BM25 for laws just in case..."
.venv312\Scripts\python.exe -c "
import chromadb
from rank_bm25 import BM25Okapi
import pickle
import os

print('Building BM25 for laws...')
client = chromadb.PersistentClient(path='C:\\dev\\busan_procurement_chatbot\\.chroma')
collection = client.get_collection('laws')
data = collection.get(include=['documents', 'metadatas'])
docs = data['documents']
if docs:
    tokenized = [d.split() for d in docs]
    bm25 = BM25Okapi(tokenized)
    with open('C:\\dev\\busan_procurement_chatbot\\.chroma\\bm25_laws.pkl', 'wb') as f:
        pickle.dump(bm25, f)
        print('Saved bm25_laws.pkl')
"

Write-Host "Checking ChromaDB status..."
.venv312\Scripts\python.exe check_chroma_db.py > chroma_status.txt

Write-Host "Running Stage Verification..."
.venv312\Scripts\python.exe scripts\run_staging_verification.py > new_staging.txt 2>&1

Write-Host "DONE"
