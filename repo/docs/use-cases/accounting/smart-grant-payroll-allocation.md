---
title: "Smart Grant Solution - Automated Payroll Allocation"
type: use-case
status: draft
date: "2025-Q1"
domain: "Accounting"
client: "Smart Grant Solution"
technologies: [AWS, Docker, Kubernetes, GitLab CI/CD, AWS CDK, CloudFormation, Microservices, REST API, Keycloak, Amazon MQ, Amazon RDS, Redis, Amazon S3, Cognito, AWS Secrets Manager, OpenSearch, CloudWatch]
experts: [@AndriiZolotarov, @ArtemUlianko]
tags: [PayrollAllocation, Compliance, NonProfit, GrantManagement, Automation, AWS, Microservices, EKS, Keycloak, FinancialCompliance]
---

# Smart Grant Solution — Automated Payroll Allocation

> **One-liner summary** — INSART replaced a manual, Excel-based payroll cost allocation process with a fully automated compliance engine, cutting allocation time from hours to seconds and giving Smart Grant Solution a competitive feature no rival platform currently offers.

---

## Problem Overview

Smart Grant Solution is a Financial Compliance SaaS platform helping non-profit organisations manage budgets, grants, spending, and compliance. Their clients — non-profit human service organisations across the US — are required to allocate payroll expenses across multiple grants and funding sources in accordance with strict federal compliance rules.

Before INSART's engagement, this process was entirely manual: a CPA consultant would prepare cost allocation spreadsheets in Excel, pulling data from multiple sources, performing calculations by hand, and producing export files for each client. The process was slow, error-prone, and impossible to scale — and no off-the-shelf solution on the market addressed this specific compliance need. Competitors like QuickBooks, Sage, and NetSuite had not solved it either, leaving Smart Grant Solution's clients stuck with a process that consumed significant time and introduced compliance risk.

---

## Challenges Identified

| # | Challenge | Description |
|---|---|---|
| 1 | No market solution existed | No software product addressed automated payroll cost allocation for non-profit compliance, leaving the field wide open but with no established best practices to follow |
| 2 | Fully manual process | CPA consultants prepared all allocations in Excel, creating a process that was time-intensive, error-prone, and dependent on individual expertise |
| 3 | Data source variability | Client data arrived in inconsistent formats from multiple sources, making automated ingestion and reliable processing difficult to standardise |
| 4 | Complex compliance logic | Federal grant compliance rules require precise, auditable allocation calculations — heavy logic with zero tolerance for error |
| 5 | Scalability ceiling | A manual Excel process cannot scale with a growing client base without proportionally growing headcount |

---

## Solution

INSART designed and built an automated payroll allocation engine embedded within the Smart Grant platform. The core idea was to replace the CPA consultant's manual Excel workflow with a system that ingests client data, maps it against grant structures, performs compliance-validated allocations in the background, and produces export files in the required format — all without human intervention.

The solution was built on a microservices architecture deployed on AWS, enabling each part of the allocation pipeline (data ingestion, mapping, calculation, compliance check, export) to operate independently and scale as needed.

### Key Users & Roles

| Role | Responsibility |
|---|---|
| Compliance Manager | Configures grant structures and allocation rules; reviews outputs before submission |
| CPA Consultant | Validates allocation results; previously performed this work manually in Excel |
| Platform Administrator | Manages client onboarding and data source configurations |
| Non-Profit Finance Team | Receives allocation reports and uses outputs for grant reporting and audit submissions |

---

## Process / User Flow

1. **Data preparation** — Client payroll and expense data is ingested from multiple source formats into the platform, normalised into a consistent internal schema
2. **Data mapping** — The system matches client data against the grant structures and chart of accounts configured in Smart Grant, resolving which expenses belong to which funding sources
3. **Compliance check** — Before allocation runs, the engine validates the input data against compliance rules to catch issues before they propagate into results
4. **Automated allocation** — The system calculates precise expense allocations across grants in the background, completing in seconds what previously took hours of manual spreadsheet work
5. **Export preparation** — Allocation results are packaged into the export format required by the client's compliance reporting workflow, ready for submission without further manual formatting

---

## Technical Stack & Architecture

| Layer | Technology | Notes |
|---|---|---|
| Architecture | Microservices (REST APIs) | Each allocation pipeline stage is an independent service; enables targeted scaling and isolated deployments |
| DevOps | GitLab CI/CD, AWS CDK, CloudFormation | Infrastructure as code; fully automated build and deployment pipelines |
| Container Orchestration | Docker, Kubernetes (EKS) | Containerised services managed via AWS EKS for resilience and scalability |
| Identity & Access | Keycloak IAM, Amazon Cognito, AWS Secrets Manager | Role-based access control; VPN-based private access for sensitive data operations |
| Messaging | Amazon MQ | Asynchronous communication between microservices; decouples allocation pipeline stages |
| Data Layer | Amazon RDS, Redis, Amazon S3 | RDS for transactional data and audit trail; Redis for caching; S3 for document and export storage |
| Monitoring | OpenSearch, CloudWatch | Full observability across services; audit logs available for compliance review |

Key architectural decision: microservices were chosen over a monolithic approach to allow the complex allocation logic to be developed, tested, and deployed independently from the rest of the Smart Grant platform — reducing release risk and enabling the team to iterate quickly on a novel, high-uncertainty feature.

---

## Business Outcome

- **Allocation time reduced from hours to under 30 seconds** — what previously required a CPA consultant working in Excel for several hours per client is now completed automatically in the background in seconds
- **Zero manual intervention in the standard allocation flow** — the end-to-end process from data ingestion to export requires no human calculation or formatting steps
- **Compliance accuracy improved** — automated validation rules catch data issues before allocation runs, eliminating a class of human error that is hard to detect in manual spreadsheet workflows
- **Unique competitive differentiator** — Smart Grant Solution is the only platform on the market offering this capability; QuickBooks, Sage, and NetSuite have not solved this problem
- **Scalable to any client volume** — the microservices architecture allows the allocation engine to handle growing client numbers without additional operational overhead

---

## Lessons Learned

- **Embrace the unknown as a process** — this feature had no market precedent, which meant there were no best practices to follow. The team learned to treat uncertainty as a first-class concern: acknowledge gaps early, stay curious, and gather knowledge before committing to design decisions
- **Use a hypothesis-driven approach for high-uncertainty features** — when the solution space is unclear, frame development as test-and-learn cycles rather than traditional requirement-and-build. This allowed the team to validate assumptions about data normalisation and allocation logic before building the full pipeline
- **Involve the development team in discovery, not just delivery** — early engineering involvement during the problem definition phase surfaced technical constraints that would have been expensive to discover later, and led to a better architecture decision (microservices over monolith)
- **Customer availability at MVP stage is a real risk** — limited availability from client stakeholders for testing and feedback slowed hypothesis validation. This is a pattern to plan for explicitly in future projects with similar uncertainty profiles

---

## Reusable Components / Patterns

- [ ] Microservices pipeline pattern for multi-stage data processing
- [ ] Keycloak + Cognito dual IAM pattern for SaaS compliance platforms
- [ ] Amazon MQ async messaging pattern for decoupled allocation workflows

---

## Resources

| Resource | Link |
|---|---|
| Code Repository | _[To be added]_ |
| Slide Deck | Service Delivery Payroll Allocation — INSART presentation (PDF available internally) |
| Design Files | _[To be added]_ |
| Demo Video | _[To be added]_ |

---

## Experts

| Expert | Role on Project |
|---|---|
| Andrii Zolotarov | _[To be added]_ |
| Artem Ulianko | _[To be added]_ |

---

_Last updated: 2025-Q1 · Status: draft_
