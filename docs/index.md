---
doc_key: ACMS_DOCS_INDEX
semver: 1.0.0
status: active
effective_date: 2025-11-02
owner: Platform.Engineering
contract_type: intent
---

# ACMS Documentation Portal

Welcome to the documentation hub for the **Autonomous Code Modification System (ACMS)**. This site consolidates the material referenced in the executive summary and the supplemental development plan so that engineering teams and AI agents can quickly find authoritative guidance.

## How to Use This Portal

1. **Start with the Executive Summary** – Review the architectural overview, guiding principles, and eleven-phase roadmap described in `ACMS_EXECUTIVE_SUMMARY.md` to understand the broader vision.
2. **Follow the Phase Deliverables** – The supplemental development plan enumerates required artefacts for each phase. Use the navigation sidebar to open the detailed contracts and procedural guides as they are implemented.
3. **Validate Before Shipping** – Cross-check every change against the governance requirements in `VERSIONING_OPERATING_CONTRACT.md` and `ACMS_BUILD_EXECUTION_CONTRACT.yaml` to confirm front matter, versioning, and quality gates are satisfied.

## Documentation Structure

The MkDocs configuration defines the following primary sections:

- **Overview** (this page): Entry point with quick-start context, references, and navigation tips.
- **Operating Contract**: Repository-resident contract describing policies, roles, and guardrails that govern ACMS documentation.

Additional sections—such as architecture deep-dives, plugin development guides, validation checklists, and deployment runbooks—should be added as their corresponding phases are delivered. Each new page must include the canonical YAML front matter required by the Versioning Operating Contract.

## Quick Links

- [ACMS Executive Summary](../ACMS_EXECUTIVE_SUMMARY.md)
- [Build Execution Contract](../ACMS_BUILD_EXECUTION_CONTRACT.yaml)
- [Versioning Operating Contract](../VERSIONING_OPERATING_CONTRACT.md)
- [R_PIPELINE Implementation Guide](../R_PIPELINE_IMPLEMENTATION_GUIDE.md)

## Change Management

All documentation updates must:

- Increment the `semver` field according to the scope of change.
- Update the `effective_date` when the new version becomes authoritative.
- Include references to validation evidence (tests, linting, security scans) in the associated Pull Request.
- Remain deterministic—scripts that build or lint documentation should produce identical output for identical inputs.

For automated generation, use the `scripts/generate_docs.py` utility introduced in Phase 10 to orchestrate MkDocs builds within CI/CD.
