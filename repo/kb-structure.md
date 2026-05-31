# INSART Knowledge Base — Folder & File Structure

> **Purpose:** This document defines the repository layout for the INSART internal Knowledge Base.
> All content is stored as Markdown files in a Git repository, rendered via MkDocs, and indexed for semantic search.

---

## Repository Root Layout

```
insart-kb/
├── README.md                        # KB overview and quick-start for contributors
├── CONTRIBUTING.md                  # Style guide, naming conventions, how to add a doc
├── mkdocs.yml                       # MkDocs static site configuration
│
├── docs/                            # ← ALL CONTENT LIVES HERE
│   ├── index.md                     # KB home page
│   │
│   ├── use-cases/                   # Delivery case studies (primary content)
│   │   ├── _template.md             # ← Use this to create a new case
│   │   ├── _index.md                # Category overview & navigation
│   │   ├── payments/                # Wallets, transfers, POS, payment gateways
│   │   ├── banking/                 # Digital banking, neobanking, core modernisation
│   │   ├── lending/                 # Loan origination, credit scoring, BNPL
│   │   ├── wealth-management/       # Investment platforms, robo-advisors, trading
│   │   ├── insurance/               # Underwriting engines, claims, policy management
│   │   ├── regtech/                 # KYC/AML, compliance automation, reporting
│   │   ├── accounting/              # Bookkeeping, invoicing, financial reporting tools
│   │   ├── blockchain/              # Crypto platforms, DeFi, tokenisation
│   │   ├── b2b-infrastructure/      # BaaS, embedded finance, FinTech APIs
│   │   └── other/                   # Anything that doesn't fit above
│   │
│   ├── best-practices/              # Reusable engineering patterns & guides
│   │   ├── _template.md
│   │   ├── _index.md
│   │   ├── architecture/            # Microservices, event-driven, system design
│   │   ├── ai-ml/                   # Fraud detection, credit scoring, LLM/RAG
│   │   ├── security/                # Auth, encryption, PCI-DSS, SOC2 patterns
│   │   ├── compliance/              # KYC flows, audit trails, regulatory hooks
│   │   ├── data-pipelines/          # Real-time processing, reconciliation, ETL
│   │   ├── integrations/            # Plaid, Stripe, banking APIs, open banking
│   │   ├── cloud/                   # AWS/GCP infra, IaC, cost optimisation
│   │   ├── frontend/                # React patterns, FinTech UX
│   │   └── backend/                 # Java/Node patterns, API design
│   │
│   ├── experts/                     # INSART expert profiles
│   │   ├── _template.md
│   │   └── _index.md
│   │
│   ├── domains/                     # FinTech domain reference & glossary
│   │   ├── _template.md
│   │   ├── payments/
│   │   ├── banking/
│   │   ├── lending/
│   │   ├── wealth-management/
│   │   ├── insurance/
│   │   ├── regtech/
│   │   ├── accounting/
│   │   └── blockchain/
│   │
│   └── proposal-toolkit/            # Reusable proposal sections & RFP snippets
│       ├── _template.md
│       ├── pitch-sections/
│       └── rfp-responses/
│
├── search/                          # Semantic search service
│   ├── indexer.py                   # Reads docs/, embeds, pushes to Qdrant
│   ├── api.py                       # FastAPI search endpoint
│   ├── config.py                    # Qdrant URL, embedding model config
│   └── requirements.txt
│
├── web/                             # Internal search portal (single-page app)
│   ├── index.html
│   ├── app.js
│   └── styles.css
│
├── export/                          # Export pipeline scripts
│   ├── to_html.py                   # MD → branded HTML (via Jinja2 + Pandoc)
│   ├── to_pdf.py                    # MD → branded PDF (via WeasyPrint)
│   ├── templates/
│   │   ├── insart-export.html       # HTML export template
│   │   └── insart-export.css        # INSART brand styles for exports
│   └── requirements.txt
│
├── .github/
│   └── workflows/
│       ├── deploy-site.yml          # Build & deploy MkDocs site on push to main
│       └── reindex.yml              # Re-run indexer when docs/ changes
│
└── scripts/
    └── new-doc.sh                   # Helper: scaffold a new doc from a template
```

---

## Content Folder Conventions

### Naming Rules

| Element | Convention | Example |
|---|---|---|
| Folder names | `kebab-case` | `smart-grant-cms/` |
| File names | `kebab-case.md` | `smart-grant-cms.md` |
| Template files | Prefix with underscore | `_template.md` |
| Index / overview pages | `_index.md` | `use-cases/_index.md` |

### File Placement Decision Tree

```
New document?
│
├── Is it a client delivery story?      → docs/use-cases/{domain}/
├── Is it a reusable technical pattern? → docs/best-practices/{category}/
├── Is it an expert profile?            → docs/experts/
├── Is it a domain/technology glossary? → docs/domains/{domain}/
└── Is it a proposal or RFP snippet?    → docs/proposal-toolkit/
```

### YAML Frontmatter (required on every doc)

Every Markdown file must start with a YAML frontmatter block so it can be indexed and filtered:

```yaml
---
title: "Human-readable title"
type: use-case          # use-case | best-practice | expert | domain | proposal
status: published       # draft | review | published
date: 2024-Q2
domain: RegTech         # primary business domain
tags: []                # searchable keywords
experts: []             # @Name of INSART expert(s)
technologies: []        # tech stack
client: ""              # (use-cases only) client name or "Confidential"
---
```

---

## Use Cases — Domain Taxonomy

Use the following domain folders under `docs/use-cases/`:

| Folder | Covers |
|---|---|
| `payments/` | Payment processing, digital wallets, money transfers, POS systems |
| `banking/` | Digital banking, neobanking, core banking modernisation |
| `lending/` | Loan origination, credit scoring, BNPL, mortgage platforms |
| `wealth-management/` | Investment platforms, robo-advisors, portfolio management, trading |
| `insurance/` | InsurTech, underwriting engines, claims management, policy platforms |
| `regtech/` | KYC/AML, compliance automation, regulatory reporting |
| `accounting/` | Bookkeeping automation, invoicing, financial reporting tools |
| `blockchain/` | Crypto platforms, DeFi, tokenisation, smart contracts |
| `b2b-infrastructure/` | BaaS, embedded finance, FinTech API platforms |
| `other/` | Anything that doesn't fit the above |

---

## Best Practices — Category Taxonomy

| Folder | Covers |
|---|---|
| `architecture/` | System design patterns, microservices, event-driven |
| `ai-ml/` | Fraud detection, credit scoring, LLM integration, RAG pipelines |
| `security/` | Auth, encryption, PCI-DSS, SOC2 compliance patterns |
| `compliance/` | KYC/AML flows, audit trails, regulatory hooks |
| `data-pipelines/` | Real-time financial data processing, reconciliation, ETL |
| `integrations/` | Plaid, Stripe, banking APIs, open banking connectors |
| `cloud/` | AWS/GCP/Azure infra, IaC, cost optimisation |
| `frontend/` | React patterns, FinTech UX, performance, accessibility |
| `backend/` | API design, Java/Node patterns, DB optimisation |
