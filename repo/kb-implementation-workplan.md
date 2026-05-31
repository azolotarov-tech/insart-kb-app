# INSART Knowledge Base — Implementation Workplan

**Project goal:** Build an internal, Git-based Knowledge Base with semantic search, a web portal, and HTML/PDF export capabilities.

**Stack:** Markdown + Git → MkDocs (static site) → Qdrant + OpenAI embeddings (semantic search) → FastAPI (search API) → WeasyPrint/Pandoc (exports) → Hosted on internal infra (Docker / AWS ECS).

---

## Summary Timeline

| Phase | Work | Duration |
|---|---|---|
| 1 | Foundation — Repo, structure, templates | Week 1–2 |
| 2 | Static site — MkDocs portal | Week 2–3 |
| 3 | Semantic search — Qdrant + embeddings | Week 3–5 |
| 4 | Web search portal — UI | Week 5–6 |
| 5 | Export pipeline — HTML & PDF | Week 6–7 |
| 6 | Deployment & access control | Week 7–8 |
| 7 | Content population sprint | Week 8–12 (ongoing) |

---

## Phase 1 — Foundation

**Goal:** Establish the repository, folder structure, templates, and contribution guidelines. This phase is complete when any team member can open the repo and understand how to add a document.

**Tasks:**

- [ ] Create private GitLab (or GitHub) repository `insart-kb`
- [ ] Implement the full folder structure per `kb-structure.md`
- [ ] Commit all three document templates (`use-case`, `best-practice`, `expert-profile`)
- [ ] Write `CONTRIBUTING.md` — naming conventions, YAML frontmatter rules, review process
- [ ] Write `README.md` — what the KB is, how to navigate it, who to contact
- [ ] Set up branch protection: `main` requires at least one review before merge
- [ ] Create a helper script `scripts/new-doc.sh` to scaffold a new doc from a template

**Deliverables:** Empty but correctly structured repo with templates and docs.

---

## Phase 2 — Static Site (MkDocs)

**Goal:** The repo content renders as a browsable internal website with navigation, search, and a clean theme.

**Tasks:**

- [ ] Install and configure MkDocs with the `Material for MkDocs` theme
- [ ] Configure `mkdocs.yml` — nav tree, site name, theme colours (INSART brand)
- [ ] Add built-in full-text search (MkDocs built-in, as a baseline before semantic search)
- [ ] Set up CI/CD pipeline (`deploy-site.yml`) to auto-build and deploy on push to `main`
- [ ] Deploy to internal server (e.g. Nginx on VPS, or AWS S3 + CloudFront)
- [ ] Validate navigation renders correctly with placeholder content

**Notes:** MkDocs Material's built-in search is keyword-based and works out of the box. It is a useful starting point and remains available even after semantic search is added.

**Deliverables:** Browsable internal site at `kb.insart.com` (or internal URL).

---

## Phase 3 — Semantic Search

**Goal:** Engineers and sales staff can search the KB using natural language queries (e.g. "compliance platform with Strapi CMS") and get ranked, relevant results.

### 3a — Embedding & Indexing

- [ ] Choose embedding model:
  - **Recommended:** `text-embedding-3-small` (OpenAI) — high quality, low cost, no local GPU needed
  - **Alternative:** `all-MiniLM-L6-v2` (sentence-transformers, local) — fully self-hosted, free
- [ ] Deploy Qdrant vector database on internal infra (Docker container)
- [ ] Write `search/indexer.py`:
  - Parse all `docs/**/*.md` files
  - Extract YAML frontmatter (title, type, domain, tags, technologies)
  - Chunk content (e.g. per section / 512 tokens)
  - Generate embeddings
  - Upsert vectors into Qdrant with metadata payload
- [ ] Write CI job `reindex.yml` — re-runs indexer automatically when `docs/` changes on `main`
- [ ] Test indexer on 3–5 sample documents

### 3b — Search API

- [ ] Write `search/api.py` (FastAPI):
  - `GET /search?q=...&type=...&domain=...&limit=10`
  - Embeds query, queries Qdrant, returns ranked results with title, excerpt, URL, tags
  - Optional filters: `type` (use-case / best-practice), `domain`, `technologies`
- [ ] Containerise with Docker
- [ ] Deploy alongside MkDocs site
- [ ] Write basic API tests

**Deliverables:** Working `/search` endpoint returning semantically ranked results.

---

## Phase 4 — Web Search Portal

**Goal:** A fast, clean internal web UI where anyone (engineers, sales, PM) can search the KB without touching Markdown or Git.

**Tasks:**

- [ ] Build single-page search UI (`web/index.html` + `app.js`):
  - Search bar with real-time results (debounced)
  - Filter chips: Content type / Domain / Technology
  - Result cards: title, domain badge, expert tags, excerpt, links (View doc / Export HTML / Export PDF)
- [ ] Add INSART branding (logo, brand colours)
- [ ] Integrate with the FastAPI `/search` endpoint
- [ ] Deploy as part of the same internal site
- [ ] Test with non-technical users (sales / PM) for UX feedback

**UX Notes for mixed audience:** The portal is the primary entry point for non-engineers. Keep it minimal — one search bar, instant results. The "View in KB" link opens the MkDocs page; export buttons trigger the pipeline from Phase 5.

**Deliverables:** Live search portal accessible at the internal KB URL.

---

## Phase 5 — Export Pipeline

**Goal:** Any use case or best practice can be exported as a branded HTML file or PDF with one click (or one script call).

**Tasks:**

- [ ] Create INSART brand HTML/CSS export template (`export/templates/insart-export.html`)
  - INSART logo, colour scheme, typography
  - Sections: cover, problem, solution, tech stack, outcomes
- [ ] Write `export/to_html.py` — converts an MD file to standalone branded HTML (Jinja2 + Pandoc or Python-Markdown)
- [ ] Write `export/to_pdf.py` — converts branded HTML to PDF (WeasyPrint recommended; Pandoc + LaTeX as alternative)
- [ ] Wire export buttons in the web portal to trigger on-demand export
- [ ] Validate output quality on the Smart Grant CMS example doc
- [ ] Add a "direct link to doc" feature (shareable permalink to the MkDocs page)

**Deliverables:** Export buttons in portal produce clean, branded HTML and PDF files.

---

## Phase 6 — Deployment & Access Control

**Goal:** The KB is securely accessible only to INSART staff, with simple authentication.

**Tasks:**

- [ ] Choose auth method:
  - **Option A (Recommended):** SSO via Google Workspace (all INSART staff have `@insart.com` accounts) using OAuth2 proxy (e.g. `oauth2-proxy` in front of Nginx)
  - **Option B:** HTTP Basic Auth + VPN — simpler, no external dependency
- [ ] Configure Nginx reverse proxy with auth
- [ ] Set up HTTPS (Let's Encrypt)
- [ ] Document how to access the KB (internal onboarding note)
- [ ] Set up basic monitoring / uptime alerting

**Deliverables:** KB accessible at `kb.insart.com` (internal), login required.

---

## Phase 7 — Content Population

**Goal:** The KB contains at least 10 published use cases and 5 best-practice guides by the end of the sprint.

### Content Sprint Strategy

Rather than writing everything from scratch, use **existing INSART artefacts** as source material:

| Source | Content Type | Action |
|---|---|---|
| Old client presentations (.pptx) | Use Cases | Extract key sections, reformat into template |
| GitLab repositories | Best Practices | Ask tech leads to document patterns they built |
| Proposal documents | Use Cases + Proposal Toolkit | Anonymise and restructure |
| Interview notes / retrospectives | Lessons Learned | Extract into use case "Lessons" section |

### Suggested Population Order

1. **Week 8–9:** Use Cases (start with 5 most referenced in proposals)
2. **Week 9–10:** Expert Profiles (one per senior engineer / architect)
3. **Week 10–11:** Best Practices (start with most reused patterns: auth, CI/CD, AI integration)
4. **Week 11–12:** Domain Reference & Proposal Toolkit

### Contribution Process

```
Author writes draft (from template)
  → Opens Merge/Pull Request
  → Peer review (1 reviewer)
  → Merged to main
  → Auto-deployed + auto-indexed
```

### Content Quality Checklist (per document)

- [ ] YAML frontmatter complete (all required fields filled)
- [ ] Title is clear and searchable
- [ ] Problem section written for non-technical audience
- [ ] Business outcome includes at least one quantified metric
- [ ] Tags cover the key technologies and domain
- [ ] Expert(s) tagged

---

## Technology Decisions Summary

| Component | Chosen Technology | Reason |
|---|---|---|
| Content format | Markdown | Portable, Git-friendly, easy to write |
| Static site | MkDocs Material | Best Markdown rendering, built-in search baseline |
| Vector DB | Qdrant | Open source, self-hosted, Docker-friendly, fast |
| Embeddings | OpenAI text-embedding-3-small | High quality, low cost; swap for local model if needed |
| Search API | FastAPI (Python) | Lightweight, async, easy to deploy |
| PDF export | WeasyPrint | Pure Python, CSS-controlled layout, no LaTeX needed |
| HTML export | Jinja2 + Python-Markdown | Full control over branded output |
| Auth | Google OAuth2 proxy | Uses existing @insart.com accounts |
| Hosting | Internal VPS or AWS ECS | Keeps client data confidential |

---

## Open Questions to Resolve Before Starting

1. **Confidentiality level of use cases** — Can case content include real client names, or should everything be anonymised by default?
2. **Who owns the KB?** — Who is the internal maintainer / reviewer for merged content?
3. **OpenAI API key** — If using OpenAI embeddings, an API key is needed. Alternatively, use a local model (no external dependency).
4. **Hosting infra** — Does INSART have a spare VPS or existing AWS account for this service?
5. **GitLab vs GitHub** — Which is preferred for the repo? (GitLab is more common internally per the example doc.)

---

## Success Metrics

| Metric | Target |
|---|---|
| Published use cases | ≥ 10 at launch |
| Published best practices | ≥ 5 at launch |
| Search result quality | Relevant result in top 3 for 8/10 test queries |
| Time to find a relevant case | < 2 minutes for sales team |
| Export quality | PDF/HTML approved by a sales team member |
| Uptime | ≥ 99% (internal SLA) |
