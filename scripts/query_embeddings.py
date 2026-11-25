"""Small verification utility for the persisted agricultural vector database."""

from __future__ import annotations

import argparse

import chromadb
from sentence_transformers import SentenceTransformer

from create_embeddings import CHROMA_PATH, COLLECTION_NAME, MODEL_NAME


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("question", nargs="?", default="What crops are grown in Washim district?")
    args = parser.parse_args()
    collection = chromadb.PersistentClient(path=str(CHROMA_PATH)).get_collection(COLLECTION_NAME)
    model = SentenceTransformer(MODEL_NAME)
    query = model.encode([args.question], normalize_embeddings=True).tolist()
    result = collection.query(query_embeddings=query, n_results=3, include=["documents", "metadatas", "distances"])
    for rank, (document, metadata, distance) in enumerate(zip(result["documents"][0], result["metadatas"][0], result["distances"][0]), start=1):
        print(f"#{rank}  distance={distance:.4f}  page={metadata['page_number']}  {metadata['document_name']}")
        print(document[:500].replace("\n", " "))
        print()


if __name__ == "__main__":
    main()
