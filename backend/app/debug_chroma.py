"""Debug script: inspect ChromaDB knowledge base collection directly.

Usage:
    cd backend
    python -m app.debug_chroma                 # show collection stats
    python -m app.debug_chroma search "餐补标准"  # test search
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.services.knowledge_service import _get_collection, _get_embedding_fn, chunk_text


def main():
    col = _get_collection()
    count = col.count()
    print(f"=== ChromaDB Collection: {col.name} ===")
    print(f"Total chunks: {count}")
    print()

    if count > 0:
        print("--- Sample entries (peek 5) ---")
        peek = col.peek(limit=5)
        ids = peek.get("ids", []) or []
        docs = peek.get("documents", []) or []
        metadatas = peek.get("metadatas", []) or []
        for i, cid in enumerate(ids):
            meta = metadatas[i] if i < len(metadatas) else {}
            doc = docs[i] if i < len(docs) else ""
            print(f"  [{cid}] kb={meta.get('kb_id')} doc={meta.get('doc_id')} "
                  f"file={meta.get('filename')} len={len(doc)}")
            print(f"    text: {doc[:120]}...")
            print()
    else:
        print("Collection is EMPTY. No knowledge base has been indexed yet.")

    # Search test
    if len(sys.argv) > 1:
        query = sys.argv[1] if len(sys.argv) > 1 else sys.argv[2] if len(sys.argv) > 2 else "餐补标准"
        print(f"\n--- Search test: \"{query}\" ---")
        model = _get_embedding_fn()
        query_vec = model([query]).tolist()
        results = col.query(
            query_embeddings=query_vec,
            n_results=5,
            include=["metadatas", "documents", "distances"],
        )
        if results and results.get("ids") and results["ids"][0]:
            for i, cid in enumerate(results["ids"][0]):
                meta = results["metadatas"][0][i] if results["metadatas"] else {}
                doc = results["documents"][0][i] if results["documents"] else ""
                dist = results["distances"][0][i] if results.get("distances") else 1.0
                sim = max(0.0, 1.0 - float(dist))
                print(f"  [{cid}] sim={sim:.4f} {doc[:100]}...")
        else:
            print("  No results found.")

    # Chunk test
    if len(sys.argv) > 2 and sys.argv[1] == "chunk":
        text = sys.argv[2]
        chunks = chunk_text(text)
        print(f"\n--- Chunk test: \"{text[:50]}...\" ---")
        print(f"Input: {len(text)} chars → {len(chunks)} chunks")
        for i, c in enumerate(chunks):
            print(f"  Chunk {i}: {len(c)} chars → \"{c[:100]}...\"")


if __name__ == "__main__":
    main()
