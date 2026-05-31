import html as html_lib
import re
import subprocess
from pathlib import Path
from flask import Flask, render_template, abort, request, jsonify
import yaml
import markdown as md_lib

BASE_DIR = Path(__file__).parent
REPO_URL = "https://github.com/azolotarov-tech/insart-knowledge-base"
REPO_DIR = BASE_DIR / "repo"
DOCS_DIR = REPO_DIR / "docs"

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


# ── repo ──────────────────────────────────────────────────────────────────────

def init_repo():
    try:
        if (REPO_DIR / ".git").exists():
            subprocess.run(["git", "-C", str(REPO_DIR), "pull"], capture_output=True)
        else:
            REPO_DIR.mkdir(parents=True, exist_ok=True)
            result = subprocess.run(
                ["git", "clone", REPO_URL, str(REPO_DIR)],
                capture_output=True, text=True,
            )
            if result.returncode != 0:
                app.logger.warning("git clone failed: %s", result.stderr)
    except FileNotFoundError:
        app.logger.warning("git not available, skipping repo init (expected on Vercel)")


# ── markdown ──────────────────────────────────────────────────────────────────

def _sanitize_yaml(s):
    # Quote bare @mentions inside YAML flow sequences: [@foo, @bar] → ["@foo", "@bar"]
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


def get_meta(md_path):
    try:
        text = Path(md_path).read_text(encoding="utf-8")
        fm, _ = parse_frontmatter(text)
        return fm
    except Exception:
        return {}


def render_page(md_path):
    text = Path(md_path).read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)
    processor = md_lib.Markdown(extensions=["tables", "toc", "fenced_code"])
    html = processor.convert(body)
    # Strip leading <h1> so the template's own h1 doesn't duplicate it
    html = re.sub(r"^\s*<h1[^>]*>.*?</h1>\s*", "", html, count=1, flags=re.DOTALL | re.IGNORECASE)
    toc = [
        {"id": m.group(1), "text": html_lib.unescape(re.sub(r"<[^>]+>", "", m.group(2))).strip()}
        for m in re.finditer(
            r'<h2[^>]+\bid="([^"]+)"[^>]*>(.*?)</h2>',
            html,
            re.IGNORECASE | re.DOTALL,
        )
    ]
    return fm, html, toc


def file_title(fm, path):
    return fm.get("title") or Path(path).stem.replace("-", " ").title()


# ── nav ───────────────────────────────────────────────────────────────────────

def _iter_section_files(docs_path: Path, section_key: str):
    """Yield (url, title, subfolder_name) for every real doc in a section."""
    if not docs_path.exists():
        return
    subdirs = sorted(d for d in docs_path.iterdir() if d.is_dir())
    if subdirs:
        for sub in subdirs:
            for f in sorted(sub.glob("*.md")):
                if f.stem.startswith("_"):
                    continue
                fm = get_meta(f)
                yield f"/{section_key}/{sub.name}/{f.stem}", file_title(fm, f), sub.name
    else:
        folder_name = docs_path.name
        for f in sorted(docs_path.glob("*.md")):
            if f.stem.startswith("_"):
                continue
            fm = get_meta(f)
            yield f"/{section_key}/{folder_name}/{f.stem}", file_title(fm, f), folder_name


def build_nav(active_section=None, active_url=None):
    nav = []
    for sec in SECTIONS:
        key = sec["key"]
        docs_path = DOCS_DIR / sec["path"]
        groups_map: dict[str, list] = {}
        for url, title, sub in _iter_section_files(docs_path, key):
            groups_map.setdefault(sub, []).append({
                "url": url,
                "title": title,
                "active": url == active_url,
            })
        nav.append({
            "key": key,
            "label": sec["label"],
            "groups": [
                {"name": k.replace("-", " ").title(), "pages": v}
                for k, v in groups_map.items()
            ],
            "collapsed": key != active_section,
        })
    return nav


# ── routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def home():
    sections_data = []
    for sec in SECTIONS:
        docs_path = DOCS_DIR / sec["path"]
        count = (
            sum(1 for f in docs_path.rglob("*.md") if not f.stem.startswith("_"))
            if docs_path.exists()
            else 0
        )
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
    docs_path = DOCS_DIR / sec["path"]
    groups_map: dict[str, list] = {}
    for url, title, sub in _iter_section_files(docs_path, section):
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
    docs_root = DOCS_DIR / sec["path"]

    md_path = docs_root / subsection / f"{slug}.md"
    if not md_path.exists():
        # flat layout: subsection is actually ignored, file is at root
        md_path = docs_root / f"{slug}.md"
        if not md_path.exists():
            abort(404)

    active_url = f"/{section}/{subsection}/{slug}"
    fm, html_body, toc = render_page(md_path)
    pg_title = file_title(fm, md_path)

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
        docs_path = DOCS_DIR / sec["path"]
        if not docs_path.exists():
            continue
        for md_file in sorted(docs_path.rglob("*.md")):
            if md_file.stem.startswith("_"):
                continue
            try:
                fm, html, _ = render_page(md_file)
                plain = re.sub(r"<[^>]+>", "", html)
                t = file_title(fm, md_file)
                if ql not in t.lower() and ql not in plain.lower():
                    continue

                rel = md_file.relative_to(docs_path)
                parts = rel.parts
                if len(parts) == 1:
                    url = f'/{sec["key"]}/{docs_path.name}/{md_file.stem}'
                    crumb = sec["label"]
                else:
                    url = f'/{sec["key"]}/{parts[0]}/{md_file.stem}'
                    crumb = f'{sec["label"]} › {parts[0].replace("-", " ").title()}'

                hi = re.sub(f"(?i)({re.escape(q)})", r"<mark>\1</mark>", t)
                idx = plain.lower().find(ql)
                excerpt = (
                    plain[max(0, idx - 60): idx + 120].strip()
                    if idx >= 0
                    else plain[:180]
                )

                results.append({
                    "title": hi,
                    "crumb": crumb,
                    "url": url,
                    "excerpt": excerpt,
                })
                if len(results) >= 8:
                    return jsonify(results)
            except Exception:
                continue

    return jsonify(results)


# Run init on import so it works with both `flask run` and `python app.py`
init_repo()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
