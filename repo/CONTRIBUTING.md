# Contributing to the INSART Knowledge Base

## Before you start

- Every document must use the correct `_template.md` for its type
- Every document must have complete YAML frontmatter
- Use the decision tree below if you're unsure where a document belongs

## Where does my document go?

```
New document?
│
├── Client delivery story?          → docs/use-cases/{domain}/
├── Reusable technical pattern?     → docs/best-practices/{category}/
├── Team member profile?            → docs/experts/
├── Domain glossary / reference?    → docs/domains/{domain}/
└── Proposal or RFP snippet?        → docs/proposal-toolkit/
```

## Naming conventions

| Element | Rule | Example |
|---|---|---|
| File names | `kebab-case.md` | `smart-grant-cms.md` |
| Folder names | `kebab-case` | `wealth-management/` |
| Template files | Prefix `_` | `_template.md` |
| Index pages | `_index.md` | `use-cases/_index.md` |

## Required YAML frontmatter

Every file must start with this block (all fields required):

```yaml
---
title: ""
type: use-case          # use-case | best-practice | expert | domain | proposal
status: draft           # draft | review | published
date: ""                # e.g. 2024-Q2
domain: ""              # e.g. RegTech, Payments, Lending
technologies: []
experts: []             # @FirstnameSurname
tags: []
client: ""              # use-cases only — real name or "Confidential"
---
```

## Review process

1. Create a branch: `git checkout -b docs/your-case-name`
2. Add your document from the template
3. Open a Pull Request with a short description
4. One peer review required before merge
5. Merged to `main` → auto-deployed + auto-indexed

## Quality checklist

Before marking a document `status: published`:

- [ ] All YAML frontmatter fields are filled in
- [ ] Title is clear and searchable (think: what would someone type to find this?)
- [ ] Problem/context section is written for a non-technical reader
- [ ] Business outcome includes at least one quantified metric
- [ ] Expert(s) are tagged
- [ ] Tags cover key technologies and domain terms
- [ ] No client-confidential information included without approval
