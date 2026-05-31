import base64
import html as html_lib
import json
import os
import re
import time
import urllib.request

from flask import Flask, render_template, abort, request, jsonify
import yaml
import markdown as md_lib


GITHUB_REPO = "azolotarov-tech/insart-knowledge-base"
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

app = Flask(__name__)


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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
