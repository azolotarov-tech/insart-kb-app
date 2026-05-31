# INSART Knowledge Base

> Internal hub for solution delivery insights and technical best practices.

## Structure

```
docs/
├── use-cases/          # Client delivery case studies (by FinTech domain)
├── best-practices/     # Reusable engineering patterns
├── experts/            # Team profiles
├── domains/            # FinTech domain reference
└── proposal-toolkit/   # Reusable proposal sections & RFP snippets
```

## Quick start

**Finding a use case for a proposal:**
Search the KB or browse `docs/use-cases/{domain}/`.

**Adding a new use case:**
```bash
cp docs/use-cases/_template.md docs/use-cases/{domain}/your-case-name.md
# Fill in the template, then open a PR
```

**Adding a best practice:**
```bash
cp docs/best-practices/_template.md docs/best-practices/{category}/your-pattern-name.md
```

## Contribution process

1. Copy the relevant `_template.md` into the correct folder
2. Fill in all required YAML frontmatter fields
3. Open a pull request — one reviewer required before merge
4. Merged PRs are auto-deployed and auto-indexed for search

See [CONTRIBUTING.md](CONTRIBUTING.md) for full guidelines.

---

*For questions about the KB, contact the KB maintainer.*
