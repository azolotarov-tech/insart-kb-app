import base64
import hashlib
import html as html_lib
import json
import os
import re
import time
import urllib.request

from flask import Flask, render_template, abort, request, jsonify
import yaml
import markdown as md_lib

try:
    from dotenv import load_dotenv
    load_dotenv(".env")
except ImportError:
    pass


GITHUB_REPO = "vzherebetskyiInsart/insart-knowledge-base"
GITHUB_DOCS = "docs"

SECTIONS = [
    {
        "key": "engineering-handbook",
        "label": "Engineering Handbook",
        "path": "best-practices",
        "description": "Architecture patterns, coding standards, cloud, security, and technical best practices.",
    },
    {
        "key": "sales-enablement",
        "label": "Sales Enablement",
        "path": "use-cases",
        "description": "Client use cases, proposal playbooks, vertical guides, and sales collateral.",
    },
    {
        "key": "fintech-domains",
        "label": "Fintech Domains",
        "path": "domains",
        "description": "Domain knowledge across banking, payments, lending, insurance, and wealth management.",
    },
    {
        "key": "reference",
        "label": "Reference",
        "path": "experts",
        "description": "Expert profiles, reusable templates, and glossary of terms.",
    },
]

SECTION_BY_KEY = {s["key"]: s for s in SECTIONS}

UPLOAD_SUBFOLDERS = {
    "sales-enablement": ["accounting", "banking", "blockchain", "insurance", "lending", "payments", "regtech", "wealth-management"],
    "engineering-handbook": ['ai-ml', 'architecture', 'backend', 'cloud', 'compliance', 'data-pipelines', 'frontend', 'integrations', 'security'],
    "domains": ["accounting", "banking", "blockchain", "insurance", "lending", "payments", "regtech", "wealth-management"],
}

QDRANT_COLLECTION = "insart_kb"
EMBED_MODEL = "voyage-finance-2"

app = Flask(__name__)

# ── vector search clients (lazy init) ─────────────────────────────────────────

_qdrant_client = None
_voyage_client = None
_sparse_model = None


def _get_qdrant():
    global _qdrant_client
    if _qdrant_client is None:
        url = os.environ.get("QDRANT_URL")
        key = os.environ.get("QDRANT_API_KEY")
        if url and key:
            from qdrant_client import QdrantClient
            _qdrant_client = QdrantClient(url=url, api_key=key)
    return _qdrant_client


def _get_voyage():
    global _voyage_client
    if _voyage_client is None:
        key = os.environ.get("VOYAGE_API_KEY")
        if key:
            import voyageai
            _voyage_client = voyageai.Client(api_key=key)
    return _voyage_client


def _get_sparse_model():
    global _sparse_model
    if _sparse_model is None:
        try:
            from fastembed import SparseTextEmbedding
            _sparse_model = SparseTextEmbedding(model_name="Qdrant/bm25")
        except Exception as e:
            app.logger.warning("BM25 sparse model unavailable: %s", e)
    return _sparse_model


@app.context_processor
def inject_globals():
    return {"all_sections": SECTIONS}


# ── GitHub API ────────────────────────────────────────────────────────────────

_cache: dict = {}
_CACHE_TTL = 300  # seconds


def _gh_api(api_path: str):
    now = time.time()
    if api_path in _cache and now - _cache[api_path][0] < _CACHE_TTL:
        return _cache[api_path][1]

    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{api_path}"
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        req.add_header("Authorization", f"Bearer {token}")

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        _cache[api_path] = (now, data)
        return data
    except Exception as e:
        app.logger.warning("GitHub API error for %s: %s", api_path, e)
        return None


def gh_file(docs_rel: str) -> str | None:
    """Fetch file content as text. docs_rel is relative to docs/."""
    data = _gh_api(f"{GITHUB_DOCS}/{docs_rel}")
    if isinstance(data, dict) and data.get("encoding") == "base64":
        return base64.b64decode(data["content"]).decode("utf-8")
    return None


def gh_list(docs_rel: str) -> list:
    """List a directory. docs_rel is relative to docs/."""
    path = f"{GITHUB_DOCS}/{docs_rel}" if docs_rel else GITHUB_DOCS
    data = _gh_api(path)
    return data if isinstance(data, list) else []


def gh_write(repo_path: str, content: str, commit_msg: str = None):
    """Create or update a file in the GitHub repo. Returns (ok, error_str)."""
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        return False, "GITHUB_TOKEN not set"

    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{repo_path}"

    # fetch existing SHA if file already exists
    sha = None
    try:
        chk = urllib.request.Request(url)
        chk.add_header("Accept", "application/vnd.github+json")
        chk.add_header("Authorization", f"Bearer {token}")
        with urllib.request.urlopen(chk, timeout=10) as r:
            sha = json.loads(r.read()).get("sha")
    except Exception:
        pass

    payload = {
        "message": commit_msg or f"Upload {repo_path.rsplit('/', 1)[-1]} via KB web UI",
        "content": base64.b64encode(content.encode()).decode(),
    }
    if sha:
        payload["sha"] = sha

    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="PUT")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=15):
            return True, ""
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode())
            detail = body.get("message", e.reason)
        except Exception:
            detail = e.reason
        return False, f"HTTP {e.code}: {detail}"
    except Exception as e:
        return False, str(e)


# ── markdown ──────────────────────────────────────────────────────────────────

def _sanitize_yaml(s):
    def _quote_mentions(match):
        vals = [v.strip() for v in match.group(1).split(",")]
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


def render_page(text: str):
    fm, body = parse_frontmatter(text)
    processor = md_lib.Markdown(extensions=["tables", "toc", "fenced_code"])
    html = processor.convert(body)
    html = re.sub(r"^\s*<h1[^>]*>.*?</h1>\s*", "", html, count=1, flags=re.DOTALL | re.IGNORECASE)
    toc = [
        {"id": m.group(1), "text": html_lib.unescape(re.sub(r"<[^>]+>", "", m.group(2))).strip()}
        for m in re.finditer(r'<h2[^>]+\bid="([^"]+)"[^>]*>(.*?)</h2>', html, re.IGNORECASE | re.DOTALL)
    ]
    return fm, html, toc


def file_title(fm, filename: str) -> str:
    if fm.get("title"):
        return fm["title"]
    stem = filename.rsplit(".", 1)[0] if "." in filename else filename
    return stem.replace("-", " ").title()


def _plain_text(content: str) -> str:
    _, body = parse_frontmatter(content)
    processor = md_lib.Markdown(extensions=["tables", "fenced_code"])
    return re.sub(r"<[^>]+>", "", processor.convert(body)).strip()


def _path_to_id(path: str) -> int:
    return int(hashlib.md5(path.encode()).hexdigest()[:15], 16)


def _chunk_text(text, chunk_size=1000, overlap=150):
    """Split text into overlapping chunks on paragraph boundaries."""
    paragraphs = [p.strip() for p in re.split(r"\n\n+", text) if p.strip()]
    chunks = []
    current = []
    current_len = 0
    for para in paragraphs:
        if current_len + len(para) > chunk_size and current:
            chunks.append(" ".join(current))
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


def _index_doc(qc, vc, repo_path: str, content: str, sec: dict, subfolder: str, filename: str):
    """Embed a document as chunks (dense + sparse) and upsert each into Qdrant."""
    from qdrant_client.models import PointStruct, SparseVector
    fm, _ = parse_frontmatter(content)
    title = file_title(fm, filename)
    stem = filename[:-3]
    url = f"/{sec['key']}/{subfolder}/{stem}"
    text = _plain_text(content)
    if not text:
        return
    chunks = _chunk_text(text)
    dense_result = vc.embed(chunks, model=EMBED_MODEL, input_type="document")
    sm = _get_sparse_model()
    sparse_embs = list(sm.embed(chunks)) if sm else [None] * len(chunks)
    points = []
    for i, (chunk, dense_vec, sparse_emb) in enumerate(zip(chunks, dense_result.embeddings, sparse_embs)):
        vector = {"dense": dense_vec}
        if sparse_emb is not None:
            vector["sparse"] = SparseVector(
                indices=sparse_emb.indices.tolist(),
                values=sparse_emb.values.tolist(),
            )
        points.append(PointStruct(
            id=_path_to_id(f"{repo_path}::chunk::{i}"),
            vector=vector,
            payload={
                "path": repo_path,
                "section_key": sec["key"],
                "section_label": sec["label"],
                "subfolder": subfolder,
                "title": title,
                "url": url,
                "text": chunk,
            },
        ))
    qc.upsert(collection_name=QDRANT_COLLECTION, points=points)


# ── nav ───────────────────────────────────────────────────────────────────────

def _iter_section_files(section_path: str, section_key: str):
    """Yield (url, title, subfolder_name) for every real doc in a section."""
    items = gh_list(section_path)
    subdirs = sorted((i for i in items if i["type"] == "dir"), key=lambda i: i["name"])

    if subdirs:
        for sub in subdirs:
            sub_items = gh_list(f"{section_path}/{sub['name']}")
            md_files = sorted(
                (i for i in sub_items if i["type"] == "file" and i["name"].endswith(".md") and not i["name"].startswith("_")),
                key=lambda i: i["name"],
            )
            if not md_files:
                yield None, None, sub["name"]
                continue
            for f in md_files:
                stem = f["name"][:-3]
                text = gh_file(f"{section_path}/{sub['name']}/{f['name']}")
                fm, _ = parse_frontmatter(text or "")
                yield f"/{section_key}/{sub['name']}/{stem}", file_title(fm, f["name"]), sub["name"]
    else:
        for f in sorted(
            (i for i in items if i["type"] == "file" and i["name"].endswith(".md")),
            key=lambda i: i["name"],
        ):
            if f["name"].startswith("_"):
                continue
            stem = f["name"][:-3]
            text = gh_file(f"{section_path}/{f['name']}")
            fm, _ = parse_frontmatter(text or "")
            yield f"/{section_key}/{section_path}/{stem}", file_title(fm, f["name"]), section_path


def build_nav(active_section=None, active_url=None):
    nav = []
    for sec in SECTIONS:
        groups_map: dict[str, list] = {}
        for url, title, sub in _iter_section_files(sec["path"], sec["key"]):
            if url is None:
                groups_map.setdefault(sub, [])
            else:
                groups_map.setdefault(sub, []).append({
                    "url": url,
                    "title": title,
                    "active": url == active_url,
                })
        nav.append({
            "key": sec["key"],
            "label": sec["label"],
            "groups": [
                {"name": k.replace("-", " ").title(), "pages": v}
                for k, v in groups_map.items()
            ],
            "collapsed": sec["key"] != active_section,
        })
    return nav


# ── routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def home():
    sections_data = []
    for sec in SECTIONS:
        items = gh_list(sec["path"])
        count = 0
        for i in items:
            if i["type"] == "dir":
                sub_items = gh_list(f"{sec['path']}/{i['name']}")
                count += sum(
                    1 for f in sub_items
                    if f["type"] == "file" and f["name"].endswith(".md") and not f["name"].startswith("_")
                )
            elif i["type"] == "file" and i["name"].endswith(".md") and not i["name"].startswith("_"):
                count += 1
        sections_data.append({**sec, "count": count})
    return render_template(
        "home.html",
        sections=sections_data,
        nav=build_nav(),
        active_tab="home",
        title="INSART Knowledge Base",
    )


@app.route("/<section>")
def section_index(section):
    if section not in SECTION_BY_KEY:
        abort(404)
    sec = SECTION_BY_KEY[section]
    groups_map: dict[str, list] = {}
    for url, title, sub in _iter_section_files(sec["path"], section):
        if url is None:
            groups_map.setdefault(sub, [])
        else:
            groups_map.setdefault(sub, []).append({"url": url, "title": title})
    groups = [
        {"name": k.replace("-", " ").title(), "pages": v}
        for k, v in groups_map.items()
    ]
    return render_template(
        "section.html",
        sec=sec,
        section_key=section,
        groups=groups,
        nav=build_nav(active_section=section),
        active_tab=section,
        title=f"{sec['label']} — INSART KB",
    )


@app.route("/<section>/<subsection>/<slug>")
def doc_page(section, subsection, slug):
    if section not in SECTION_BY_KEY:
        abort(404)
    sec = SECTION_BY_KEY[section]

    text = gh_file(f"{sec['path']}/{subsection}/{slug}.md")
    if text is None:
        text = gh_file(f"{sec['path']}/{slug}.md")
        if text is None:
            abort(404)

    fm, html_body, toc = render_page(text)
    pg_title = file_title(fm, f"{slug}.md")
    active_url = f"/{section}/{subsection}/{slug}"

    return render_template(
        "page.html",
        fm=fm,
        title=f"{pg_title} — INSART KB",
        page_title=pg_title,
        html_body=html_body,
        toc=toc,
        sec=sec,
        section_key=section,
        subsection=subsection,
        slug=slug,
        nav=build_nav(active_section=section, active_url=active_url),
        active_tab=section,
        active_url=active_url,
    )


@app.route("/search")
def search_api():
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify([])

    ql = q.lower()
    results = []

    for sec in SECTIONS:
        items = gh_list(sec["path"])
        files_to_search = []

        for i in items:
            if i["type"] == "dir":
                sub_items = gh_list(f"{sec['path']}/{i['name']}")
                for f in sub_items:
                    if f["type"] == "file" and f["name"].endswith(".md") and not f["name"].startswith("_"):
                        files_to_search.append((f"{sec['path']}/{i['name']}/{f['name']}", i["name"]))
            elif i["type"] == "file" and i["name"].endswith(".md") and not i["name"].startswith("_"):
                files_to_search.append((f"{sec['path']}/{i['name']}", sec["path"]))

        for docs_rel, sub_name in sorted(files_to_search):
            try:
                text = gh_file(docs_rel)
                if not text:
                    continue
                fm, html, _ = render_page(text)
                plain = re.sub(r"<[^>]+>", "", html)
                filename = docs_rel.rsplit("/", 1)[-1]
                stem = filename[:-3]
                t = file_title(fm, filename)
                if ql not in t.lower() and ql not in plain.lower():
                    continue

                url = f'/{sec["key"]}/{sub_name}/{stem}'
                crumb = (
                    f'{sec["label"]} › {sub_name.replace("-", " ").title()}'
                    if sub_name != sec["path"] else sec["label"]
                )
                hi = re.sub(f"(?i)({re.escape(q)})", r"<mark>\1</mark>", t)
                idx = plain.lower().find(ql)
                excerpt = plain[max(0, idx - 60): idx + 120].strip() if idx >= 0 else plain[:180]

                results.append({"title": hi, "crumb": crumb, "url": url, "excerpt": excerpt})
                if len(results) >= 8:
                    return jsonify(results)
            except Exception:
                continue

    return jsonify(results)


def _score_to_pct(score: float, is_hybrid: bool) -> int:
    """Normalize a Qdrant score to a 0-99 integer percentage."""
    if is_hybrid:
        # RRF scores: max ≈ 2/61 ≈ 0.033 (rank-1 in both dense + sparse)
        return min(round(score / 0.033 * 100), 99)
    # Dense cosine similarity: already 0-1
    return min(round(score * 100), 99)


def _do_ask(q: str):
    """Hybrid search (BM25 + vector) + Claude synthesis. Returns (answer, sources, error)."""
    from qdrant_client.models import Prefetch, FusionQuery, Fusion, SparseVector

    qc = _get_qdrant()
    vc = _get_voyage()
    if not qc or not vc:
        return None, [], "AI search is not configured on this server."

    try:
        dense_vec = vc.embed([q], model=EMBED_MODEL, input_type="query").embeddings[0]

        sm = _get_sparse_model()
        is_hybrid = bool(sm)
        if is_hybrid:
            sparse_q = list(sm.embed([q]))[0]
            response = qc.query_points(
                collection_name=QDRANT_COLLECTION,
                prefetch=[
                    Prefetch(query=dense_vec, using="dense", limit=20),
                    Prefetch(
                        query=SparseVector(
                            indices=sparse_q.indices.tolist(),
                            values=sparse_q.values.tolist(),
                        ),
                        using="sparse",
                        limit=20,
                    ),
                ],
                query=FusionQuery(fusion=Fusion.RRF),
                limit=5,
            )
        else:
            response = qc.query_points(
                collection_name=QDRANT_COLLECTION, query=dense_vec, using="dense", limit=5
            )

        if not response or not response.points:
            return None, [], "No relevant documents found for your question."

        # build sources, deduplicating chunks from the same document
        seen_urls = set()
        sources = []
        for point in response.points:
            p = point.payload
            url = p["url"]
            if url in seen_urls:
                continue
            seen_urls.add(url)
            sub = p.get("subfolder", "")
            crumb = (
                f"{p['section_label']} › {sub.replace('-', ' ').title()}"
                if sub and sub != p.get("section_key") else p["section_label"]
            )
            sources.append({
                "title": p["title"],
                "url": url,
                "crumb": crumb,
                "excerpt": p.get("text", "")[:220],
                "full_text": p.get("text", ""),
                # "confidence": _score_to_pct(point.score, is_hybrid),
                "confidence": round(point.score, 2) * 100,
            })

        answer = None
        anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if anthropic_key:
            try:
                import anthropic as _ac
                context = "\n\n---\n\n".join(
                    f"[{s['title']}] ({s['crumb']})\n{s['full_text']}" for s in sources
                )
                msg = _ac.Anthropic(api_key=anthropic_key).messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=512,
                    messages=[{"role": "user", "content": (
                        "You are a helpful assistant for the INSART Knowledge Base. "
                        "Answer the question based only on the provided documents. "
                        "Be concise (2-4 sentences). If the answer isn't in the documents, say so.\n\n"
                        f"Documents:\n{context}\n\nQuestion: {q}"
                    )}],
                )
                answer = msg.content[0].text
            except Exception as e:
                app.logger.warning("Claude synthesis failed: %s", e)

        return answer, sources, None

    except Exception as e:
        app.logger.error("Ask error: %s", e)
        return None, [], "Search failed. Please try again."


@app.route("/api/ask")
def ask_api():
    q = request.args.get("q", "").strip()
    if len(q) < 5:
        return jsonify({"error": "Query too short."})
    answer, sources, error = _do_ask(q)
    if error and not sources:
        return jsonify({"error": error})
    return jsonify({
        "answer": answer,
        "sources": [
            {
                "title": s["title"],
                "url": s["url"],
                "crumb": s["crumb"],
                "excerpt": s["excerpt"],
                "confidence": s.get("confidence", 0),
            }
            for s in sources
        ],
    })


@app.route("/ask")
def ask_page():
    q = request.args.get("q", "").strip()
    answer, sources, error = (None, [], None)
    if len(q) >= 5:
        answer, sources, error = _do_ask(q)
    return render_template(
        "ask.html",
        q=q,
        answer=answer,
        sources=sources,
        error=error,
        nav=[],
        active_tab="ask",
        title="Ask AI — INSART KB",
    )


@app.route("/upload", methods=["GET", "POST"])
def upload_page():
    ctx = dict(sections=SECTIONS, subfolders=UPLOAD_SUBFOLDERS, nav=[], active_tab="upload", title="Upload Document — INSART KB")

    if request.method == "GET":
        return render_template("upload.html", **ctx)

    # ── POST ──────────────────────────────────────────────────────────────────
    password = request.form.get("password", "")
    upload_pw = os.environ.get("UPLOAD_PASSWORD", "")
    if not upload_pw or password != upload_pw:
        return render_template("upload.html", error="Invalid password.", **ctx)

    section_key = request.form.get("section", "")
    if section_key not in SECTION_BY_KEY:
        return render_template("upload.html", error="Invalid section.", **ctx)
    sec = SECTION_BY_KEY[section_key]

    withSubfolder = bool(UPLOAD_SUBFOLDERS.get(section_key))
    subfolder = None

    if withSubfolder:
        subfolder = request.form.get("subfolder", "")
        if subfolder not in UPLOAD_SUBFOLDERS[section_key]:
            return render_template("upload.html", error="Invalid subfolder selection.", **ctx)

    file = request.files.get("file")
    if not file or not file.filename.endswith(".md"):
        return render_template("upload.html", error="Please upload a .md file.", **ctx)

    try:
        content = file.read().decode("utf-8")
    except Exception:
        return render_template("upload.html", error="Could not read file. Ensure it is valid UTF-8.", **ctx)

    filename = os.path.basename(file.filename)
    repo_path = f"{GITHUB_DOCS}/{sec['path']}/{subfolder}/{filename}" if withSubfolder else f"{GITHUB_DOCS}/{sec['path']}/{filename}"

    ok, err = gh_write(repo_path, content)
    if not ok:
        return render_template("upload.html", error=f"GitHub write failed: {err}", **ctx)
    _cache.clear()

    qc = _get_qdrant()
    vc = _get_voyage()
    if not qc or not vc:
        return render_template("upload.html", error="Vector search is not configured on this server.", **ctx)

    try:
        _index_doc(qc, vc, repo_path, content, sec, subfolder, filename)
    except Exception as e:
        app.logger.error("Indexing failed for %s: %s", repo_path, e)
        return render_template("upload.html", error=f"GitHub upload succeeded but indexing failed: {e}", **ctx)

    return render_template(
        "upload.html",
        success=f'"{filename}" uploaded to {repo_path} and indexed for AI search.',
        **ctx,
    )


# ── Slack bot ─────────────────────────────────────────────────────────────────

try:
    from slack_bot import handler as _slack_handler

    @app.route("/slack/events", methods=["POST"])
    def slack_events():
        return _slack_handler.handle(request)

except ImportError:
    pass  # slack-bolt not installed — Slack routes disabled


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
