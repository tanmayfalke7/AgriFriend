"""Index agricultural PDF documents into the local ChromaDB knowledge base.

Usage (from the repository root):
    python scripts/create_embeddings.py Washim.pdf

The first run downloads the multilingual embedding model if it is not already
cached.  Re-running with the same PDF is safe: its content hash is used for
deduplication.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
from pathlib import Path

import chromadb
import fitz  # PyMuPDF
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).resolve().parents[1]
CHROMA_PATH = ROOT / "data" / "chroma_db"
SOURCE_PATH = ROOT / "data" / "source_documents"
COLLECTION_NAME = "agricultural_knowledge"
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def clean_text(text: str) -> str:
    """Normalise PDF extraction artifacts without discarding non-English text."""
    text = text.replace("\x00", " ").replace("�", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]*\n+", "\n", text)
    return text.strip()


def split_text(text: str, chunk_size: int = 2800, overlap: int = 400) -> list[str]:
    """Make overlapping, non-empty character chunks, preferring sentence breaks."""
    text = clean_text(text)
    if not text:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)
        if end < len(text):
            boundary = max(text.rfind(". ", start + chunk_size // 2, end),
                           text.rfind("\n", start + chunk_size // 2, end))
            if boundary > start:
                end = boundary + 1
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


def extract_chunks(pdf_path: Path) -> list[tuple[str, int, int]]:
    """Return (text, page_number, per-page_chunk_index) entries from a PDF."""
    document = fitz.open(pdf_path)
    try:
        entries: list[tuple[str, int, int]] = []
        for page_number, page in enumerate(document, start=1):
            for index, chunk in enumerate(split_text(page.get_text("text"))):
                entries.append((chunk, page_number, index))
        return entries
    finally:
        document.close()


def index_pdf(pdf_path: Path) -> int:
    if not pdf_path.is_file() or pdf_path.suffix.lower() != ".pdf":
        raise ValueError(f"Expected an existing PDF file, got: {pdf_path}")

    pdf_hash = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    chunks = extract_chunks(pdf_path)
    if not chunks:
        raise RuntimeError("No extractable text was found. This PDF may need OCR.")

    CHROMA_PATH.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"description": "Verified agricultural PDF knowledge base"},
    )
    existing = collection.get(where={"document_hash": pdf_hash}, include=[])
    if existing["ids"]:
        print(f"Already indexed: {pdf_path.name} ({len(existing['ids'])} chunks)")
        return len(existing["ids"])

    print(f"Loading multilingual embedding model: {MODEL_NAME}")
    model = SentenceTransformer(MODEL_NAME)
    documents = [text for text, _, _ in chunks]
    embeddings = model.encode(
        documents, normalize_embeddings=True, show_progress_bar=True
    ).tolist()
    ids = [f"{pdf_hash[:16]}-{index:04d}" for index in range(len(documents))]
    metadata = [
        {
            "document_id": pdf_hash,
            "document_hash": pdf_hash,
            "document_name": pdf_path.name,
            "source": str(pdf_path.name),
            "page_number": page_number,
            "chunk_index": index,
            "page_chunk_index": page_chunk_index,
            "language": "en",
        }
        for index, (_, page_number, page_chunk_index) in enumerate(chunks)
    ]
    collection.add(ids=ids, documents=documents, embeddings=embeddings, metadatas=metadata)

    SOURCE_PATH.mkdir(parents=True, exist_ok=True)
    copied_path = SOURCE_PATH / f"{pdf_hash[:16]}_{pdf_path.name}"
    if not copied_path.exists():
        shutil.copy2(pdf_path, copied_path)
    print(f"Indexed {len(documents)} chunks from {pdf_path.name}")
    print(f"Collection: {COLLECTION_NAME}; persistent path: {CHROMA_PATH}")
    return len(documents)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create ChromaDB embeddings from an agricultural PDF")
    parser.add_argument("pdf", nargs="?", default="Washim.pdf", type=Path)
    args = parser.parse_args()
    path = args.pdf if args.pdf.is_absolute() else ROOT / args.pdf
    index_pdf(path)
