"""
Run this script to rebuild the full Qdrant vector index from scratch.

    python index.py

Reads QDRANT_URL, QDRANT_API_KEY, VOYAGE_API_KEY, GITHUB_TOKEN from .env
(or from the environment directly).
"""

import base64
import hashlib
import json
import os
import re
import urllib.request

try:
    from dotenv import load_dotenv
    load_dotenv(".env")
except ImportError:
    pass

import voyageai
import yaml
import markdown as md_lib
from fastembed import SparseTextEmbedding
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, SparseVectorParams, SparseIndexParams,
    PointStruct, SparseVector,
)


GITHUB_REPO = "vzherebetskyiInsart/insart-knowledge-base"
GITHUB_DOCS = "docs"
QDRANT_COLLECTION = "insart_kb"
EMBED_MODEL = "voyage-finance-2"
EMBED_BATCH = 20

SECTIONS = [
    {"key": "engineering-handbook", "label": "Engineering Handbook", "path": "best-practices"},
    {"key": "sales-enablement",     "label": "Sales Enablement",     "path": "use-cases"},
    {"key": "fintech-domains",      "label": "Fintech Domains",      "path": "domains"},
    {"key": "reference",            "label": "Reference",            "path": "experts"},
]


# ── GitHub helpers ────────────────────────────────────────────────────────────

def _gh_request(api_path):
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{api_path}"
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            remaining = resp.headers.get("X-RateLimit-Remaining")
            if remaining is not None and int(remaining) <= 5:
                print(f"  ! GitHub rate limit warning: {remaining} requests remaining")
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        remaining = e.headers.get("X-RateLimit-Remaining", "?")
        if e.code in (403, 429) and remaining == "0":
            reset_ts = e.headers.get("X-RateLimit-Reset", "")
            reset_msg = f" Resets at Unix timestamp {reset_ts}." if reset_ts else ""
            raise SystemExit(
                f"\nGitHub rate limit exceeded (no GITHUB_TOKEN set).{reset_msg}\n"
                "Set GITHUB_TOKEN in .env and retry."
            )
        raise


def gh_list(docs_rel):
    path = f"{GITHUB_DOCS}/{docs_rel}" if docs_rel else GITHUB_DOCS
    data = _gh_request(path)
    return data if isinstance(data, list) else []


def gh_file(docs_rel):
    data = _gh_request(f"{GITHUB_DOCS}/{docs_rel}")
    if isinstance(data, dict) and data.get("encoding") == "base64":
        return base64.b64decode(data["content"]).decode("utf-8")
    return None


# ── text helpers ──────────────────────────────────────────────────────────────

def _sanitize_yaml(s):
    def _quote_mentions(m):
        vals = [v.strip() for v in m.group(1).split(",")]
        quoted = ", ".join(f'"@{v.lstrip("@")}"' for v in vals if v)
        return f"[{quoted}]"
    return re.sub(r"\[(@[^\]]*)\]", _quote_mentions, s)


def parse_frontmatter(text):
    m = re.match(r"^---[ \t]*\r?\n(.*?)\r?\n---[ \t]*\r?\n", text, re.DOTALL)
    if m:
        try:
            fm = yaml.safe_load(_sanitize_yaml(m.group(1))) or {}
        except Exception:
            fm = {}
        return fm, text[m.end():]
    return {}, text


def file_title(fm, filename):
    if fm.get("title"):
        return fm["title"]
    stem = filename.rsplit(".", 1)[0] if "." in filename else filename
    return stem.replace("-", " ").title()


def plain_text(content):
    fm, body = parse_frontmatter(content)
    processor = md_lib.Markdown(extensions=["tables", "fenced_code"])
    html = processor.convert(body)
    return re.sub(r"<[^>]+>", "", html).strip()


def path_to_id(path):
    return int(hashlib.md5(path.encode()).hexdigest()[:15], 16)


def chunk_text(text, chunk_size=1000, overlap=150):
    """Split text into overlapping chunks on paragraph boundaries."""
    paragraphs = [p.strip() for p in re.split(r"\n\n+", text) if p.strip()]
    chunks = []
    current = []
    current_len = 0
    for para in paragraphs:
        if current_len + len(para) > chunk_size and current:
            chunks.append(" ".join(current))
            # keep last paragraph as overlap for the next chunk
            overlap_paras = []
            overlap_len = 0
            for p in reversed(current):
                if overlap_len + len(p) <= overlap:
                    overlap_paras.insert(0, p)
                    overlap_len += len(p)
                else:
                    break
            current = overlap_paras
            current_len = overlap_len
        current.append(para)
        current_len += len(para)
    if current:
        chunks.append(" ".join(current))
    return chunks if chunks else [text[:chunk_size]]


# ── document collection ───────────────────────────────────────────────────────

def collect_docs():
    docs = []
    for sec in SECTIONS:
        items = gh_list(sec["path"])
        for item in items:
            if item["type"] == "dir":
                sub_items = gh_list(f"{sec['path']}/{item['name']}")
                for f in sub_items:
                    if f["type"] == "file" and f["name"].endswith(".md") and not f["name"].startswith("_"):
                        docs.append({
                            "gh_path": f"{sec['path']}/{item['name']}/{f['name']}",
                            "section": sec,
                            "subfolder": item["name"],
                            "filename": f["name"],
                        })
            elif item["type"] == "file" and item["name"].endswith(".md") and not item["name"].startswith("_"):
                docs.append({
                    "gh_path": f"{sec['path']}/{item['name']}",
                    "section": sec,
                    "subfolder": sec["path"],
                    "filename": item["name"],
                })
    return docs


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    qdrant_url = os.environ.get("QDRANT_URL")
    qdrant_key = os.environ.get("QDRANT_API_KEY")
    voyage_key = os.environ.get("VOYAGE_API_KEY")

    if not all([qdrant_url, qdrant_key, voyage_key]):
        raise SystemExit("Missing env vars. Set QDRANT_URL, QDRANT_API_KEY, VOYAGE_API_KEY.")

    vc = voyageai.Client(api_key=voyage_key)
    qc = QdrantClient(url=qdrant_url, api_key=qdrant_key)

    # collect all docs
    print("Collecting documents from GitHub...")
    doc_refs = collect_docs()
    print(f"  Found {len(doc_refs)} documents")

    # fetch content
    print("Fetching document content...")
    docs = []
    for ref in doc_refs:
        try:
            content = gh_file(ref["gh_path"])
            if not content:
                continue
            sec = ref["section"]
            fm, _ = parse_frontmatter(content)
            title = file_title(fm, ref["filename"])
            stem = ref["filename"][:-3]
            subfolder = ref["subfolder"]
            url = f"/{sec['key']}/{subfolder}/{stem}"
            text = plain_text(content)
            if not text:
                continue
            chunks = chunk_text(text)
            for i, chunk in enumerate(chunks):
                docs.append({
                    "id": path_to_id(f"{ref['gh_path']}::chunk::{i}"),
                    "text": chunk,
                    "payload": {
                        "path": ref["gh_path"],
                        "section_key": sec["key"],
                        "section_label": sec["label"],
                        "subfolder": subfolder,
                        "title": title,
                        "url": url,
                        "text": chunk,
                    },
                })
            print(f"  + {title} ({len(chunks)} chunk{'s' if len(chunks) != 1 else ''})")
        except Exception as e:
            print(f"  ! Skipped {ref['gh_path']}: {e}")

    if not docs:
        raise SystemExit("No documents fetched. Check GITHUB_TOKEN and repo access.")

    # load BM25 sparse model (local, no API key needed)
    print("\nLoading BM25 sparse model...")
    sparse_model = SparseTextEmbedding(model_name="Qdrant/bm25")
    print("  Ready")

    # detect dense embedding dimension
    print(f"\nDetecting embedding dimension for {EMBED_MODEL}...")
    test = vc.embed(["test"], model=EMBED_MODEL, input_type="document")
    dim = len(test.embeddings[0])
    print(f"  Dimension: {dim}")

    # recreate collection with named dense + sparse vectors
    print(f"\nRecreating Qdrant collection '{QDRANT_COLLECTION}'...")
    existing = [c.name for c in qc.get_collections().collections]
    if QDRANT_COLLECTION in existing:
        qc.delete_collection(QDRANT_COLLECTION)
    qc.create_collection(
        collection_name=QDRANT_COLLECTION,
        vectors_config={"dense": VectorParams(size=dim, distance=Distance.COSINE)},
        sparse_vectors_config={"sparse": SparseVectorParams(index=SparseIndexParams(on_disk=False))},
    )

    # generate BM25 sparse embeddings for all chunks (fast, local)
    all_texts = [d["text"] for d in docs]
    print(f"\nGenerating BM25 sparse embeddings for {len(docs)} chunks...")
    sparse_embs = list(sparse_model.embed(all_texts))
    print("  Done")

    # embed with VoyageAI in batches and upsert
    print(f"\nEmbedding with VoyageAI and indexing...")
    points = []
    for i in range(0, len(docs), EMBED_BATCH):
        batch = docs[i : i + EMBED_BATCH]
        result = vc.embed([d["text"] for d in batch], model=EMBED_MODEL, input_type="document")
        for j, (doc, dense_vec) in enumerate(zip(batch, result.embeddings)):
            sparse_emb = sparse_embs[i + j]
            points.append(PointStruct(
                id=doc["id"],
                vector={
                    "dense": dense_vec,
                    "sparse": SparseVector(
                        indices=sparse_emb.indices.tolist(),
                        values=sparse_emb.values.tolist(),
                    ),
                },
                payload=doc["payload"],
            ))
        print(f"  Embedded {min(i + EMBED_BATCH, len(docs))}/{len(docs)}")

    qc.upsert(collection_name=QDRANT_COLLECTION, points=points)
    print(f"\nDone! Indexed {len(points)} chunks (dense + sparse) into '{QDRANT_COLLECTION}'.")


if __name__ == "__main__":
    main()
