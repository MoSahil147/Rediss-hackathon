import os
import json
from typing import List

import chromadb
from sentence_transformers import SentenceTransformer

from redis_rag_setup import (
    upsert_invoice,
    upsert_do,
)


def fetch_chroma_collection(name: str):
    client = chromadb.PersistentClient(path="./chroma_storage")
    return client.get_or_create_collection(name)


def migrate_collection(name: str, kind: str) -> int:
    collection = fetch_chroma_collection(name)
    results = collection.get()
    ids: List[str] = results.get("ids", [])
    docs: List[str] = results.get("documents", [])
    metas: List[dict] = results.get("metadatas", [])
    embeds = results.get("embeddings", None)

    migrated = 0
    for i, doc_id in enumerate(ids):
        content = docs[i] if i < len(docs) else ""
        meta = metas[i] if i < len(metas) else {}
        embedding = embeds[i] if embeds and i < len(embeds) else None
        if kind == "invoice":
            upsert_invoice(doc_id, content, meta, embedding)
        else:
            upsert_do(doc_id, content, meta, embedding)
        migrated += 1
    return migrated


def main():
    total = 0
    inv = migrate_collection("invoices", kind="invoice")
    total += inv
    print(f"Migrated {inv} records from 'invoices' to Redis.")

    do = migrate_collection("dorag", kind="do")
    total += do
    print(f"Migrated {do} records from 'dorag' to Redis.")

    print(f"Done. Total migrated: {total}")


if __name__ == "__main__":
    main()


