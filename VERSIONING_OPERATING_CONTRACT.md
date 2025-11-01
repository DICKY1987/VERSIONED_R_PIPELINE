---
doc_key: VERSIONING_OC
semver: 1.0.0
status: active
effective_date: 2025-11-01
supersedes_version: null
owner: Platform.Engineering
contract_type: policy
---

# Versioning Operating Contract

**This document governs how all governance documents, policies, plans, and contracts are versioned, reviewed, and enforced in this repository.**

## Table of Contents

1. [First Principles](#first-principles)
2. [Canonical Front-Matter Schema](#canonical-front-matter-schema)
3. [Semantic Versioning Rules](#semantic-versioning-rules)
4. [Contract Type Definitions](#contract-type-definitions)
5. [Enforcement Architecture](#enforcement-architecture)
6. [Developer Workflow](#developer-workflow)
7. [Governance and Authority](#governance-and-authority)
8. [Audit Trail and Rollback](#audit-trail-and-rollback)
9. [Bootstrap Instructions](#bootstrap-instructions)
10. [Change Log](#change-log)

---

## First Principles

**Docs are code. Plans are code.**

This means:

1. **They live in the repository** — All governance documents, policies, and plans are versioned alongside code.
2. **They're edited with commits and PRs** — No offline Word docs. No email attachments. Changes go through the same review process as code.
3. **They are versioned, reviewed, and tagged** — Every meaningful change gets a version bump and an immutable git tag.
4. **They enable audit and rollback** — You can answer "what rules were in force on date X?" and reproduce any historical state.

**If you don't do this, the rest of this contract doesn't matter.**

---

## Canonical Front-Matter Schema

Every document in `/docs` and `/plans` **MUST** include the following YAML front matter at the top of the file:

```yaml
---
doc_key: OC_CORE              # Stable identifier (no dates, no version)
semver: 1.3.0                 # Required: MAJOR.MINOR.PATCH
status: active                # active | deprecated | frozen
effective_date: 2025-10-28    # When this version takes effect (YYYY-MM-DD)
supersedes_version: 1.2.2     # Previous semver (omit for brand-new docs)
owner: Platform.Engineering   # CODEOWNERS team/role
contract_type: policy         # policy | intent | execution_contract
---
```

### Field Definitions

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `doc_key` | **Yes** | String | Permanent identifier. Never changes. Used in git tags. No spaces, no special chars except underscore/hyphen. Examples: `OC_CORE`, `PIPELINE_POLICY`, `R_PIPELINE_PHASE_01` |
| `semver` | **Yes** | SemVer | Current version in MAJOR.MINOR.PATCH format. Must increase monotonically. |
| `status` | **Yes** | Enum | Lifecycle state: `active` (in force), `deprecated` (superseded but retained), `frozen` (immutable historical snapshot) |
| `effective_date` | **Yes** | Date | Date when this version becomes authoritative (YYYY-MM-DD format) |
| `supersedes_version` | No | SemVer | The `semver` this version replaces. Omit for new documents. Enables ancestry validation. |
| `owner` | **Yes** | String | CODEOWNERS team/role responsible for approvals. Must match entry in `.github/CODEOWNERS` |
| `contract_type` | **Yes** | Enum | Document classification: `policy`, `intent`, or `execution_contract` (see [Contract Types](#contract-type-definitions)) |

### Validation Rules

- **doc_key**: Must be unique across the repository. Must be tag-safe (alphanumeric, underscore, hyphen only).
- **semver**: Must parse as valid Semantic Version. Must be greater than previous version when updating.
- **status**: Must be one of `active`, `deprecated`, or `frozen`.
- **effective_date**: Must be valid ISO 8601 date (YYYY-MM-DD). Should increase or stay same on updates.
- **supersedes_version**: If present, must match the previous document's `semver` exactly.
- **owner**: Must correspond to a team defined in `.github/CODEOWNERS`.
- **contract_type**: Must be one of `policy`, `intent`, or `execution_contract`.

**Enforcement**: The `.github/workflows/docs-guard.yml` workflow validates all of these rules automatically on every PR.

---

## Semantic Versioning Rules

We use **Semantic Versioning 2.0.0** (https://semver.org) for all governance documents.

### Version Format

```
MAJOR.MINOR.PATCH
```

- **MAJOR** version: Incompatible or breaking changes
- **MINOR** version: New functionality, backward-compatible additions
- **PATCH** version: Backward-compatible clarifications, fixes, editorial changes

### When to Bump Each Level

#### MAJOR (X.0.0)

**Breaking changes that invalidate previous behavior or requirements.**

Examples:
- "All code edits MUST now go through Pipeline Runner. Direct pushes to main are banned."
- "Remove human approval gate; agent auto-merges to main."
- "Change security verification from optional to mandatory."
- "Restructure entire workflow from 3 phases to 5 phases."

**Rule**: If someone following version N would be non-compliant under version N+1, it's MAJOR.

#### MINOR (0.X.0)

**New capabilities, new rules, new steps — but previous workflows still valid.**

Examples:
- "Add an Observability Gate to deployment pipeline (optional for now)."
- "Introduce new logging requirement for audit trail."
- "Add Phase 4 to roadmap without changing Phases 1-3."
- "Expand allowed programming languages from Python to Python+Rust."

**Rule**: If version N users can continue as-is and version N+1 just offers more, it's MINOR.

#### PATCH (0.0.X)

**Clarifications, typos, better wording, formatting — no behavioral change.**

Examples:
- Fix typo: "verfication" → "verification"
- Clarify ambiguous wording: "deploy nightly" → "deploy nightly at 02:00 UTC"
- Reformat tables for readability
- Add examples to existing rule without changing the rule
- Update broken links

**Rule**: If the requirements are unchanged and you're just making the doc clearer, it's PATCH.

### Mapping Conventional Commits to SemVer

When using Conventional Commits in PR titles:

| Commit Type | Version Bump | Example |
|-------------|--------------|---------|
| `fix:` | PATCH | `fix: Clarify IaC retention policy wording` |
| `docs:` | PATCH | `docs: Fix broken links in pipeline guide` |
| `feat:` | MINOR | `feat: Add observability gate to deployment` |
| `feat!:` | MAJOR | `feat!: Require pipeline runner for all edits` |
| `BREAKING CHANGE:` in body | MAJOR | Any commit with "BREAKING CHANGE:" in the message body |

**Enforcement**: The `.github/workflows/docs-guard.yml` workflow checks that your version bump matches your commit type.

---

## Contract Type Definitions

The `contract_type` field determines special validation rules and lifecycle expectations.

### 1. `policy` — General Governance Documents

**Examples**: Operating Contracts, Pipeline Policies, Security Standards, Code Review Guidelines

**Characteristics**:
- Core rules that govern how work is done
- Changes require broad review and approval
- Expected to be relatively stable (MINOR/PATCH more common than MAJOR)

**Versioning Rules**:
- **MAJOR**: Breaking changes to requirements or process
- **MINOR**: New capabilities, additional rules (backward compatible)
- **PATCH**: Clarifications, typos, formatting

**Approval Requirements**:
- PATCH: Any team member (automatic if tests pass)
- MINOR: Owner review required
- MAJOR: Owner + Compliance review required

---

### 2. `intent` — Mutable Planning Documents

**Examples**: Project Plans, Roadmaps, Strategy Documents, Research Notes

**Characteristics**:
- Allowed to evolve rapidly
- Represents current thinking, not frozen commitments
- Used for exploration and iteration
- MINOR bumps are normal and expected

**Versioning Rules**:
- **MAJOR**: Complete pivot in direction or cancellation
- **MINOR**: Scope additions, timeline shifts, reprioritization (common)
- **PATCH**: Editorial improvements, formatting, clarifications

**Approval Requirements**:
- PATCH: Any team member
- MINOR: Owner review (lightweight)
- MAJOR: Owner + stakeholder review

**Note**: Intent documents should be paired with Execution Contracts when work begins.

---

### 3. `execution_contract` — Frozen Phase Commitments

**Examples**: Sprint Commitments, Phase Execution Contracts, Release Scope Documents

**Characteristics**:
- Represents a firm commitment for a specific phase/sprint/release
- Scope is locked once the phase begins
- Changes require explicit rebaseline (MAJOR bump)
- **MINOR bumps are explicitly disallowed** (no silent scope creep)

**Versioning Rules**:
- **MAJOR ONLY**: Scope rebaseline, requirement changes (requires explicit approval and phase reset)
- **PATCH ONLY**: Editorial clarifications, formatting (meaning unchanged)
- **MINOR BLOCKED**: Not allowed. Any scope change is MAJOR.

**Approval Requirements**:
- PATCH: Owner review
- MAJOR: Owner + PMO + Compliance review, plus PR label `contract-rebaseline`

**Enforcement**: The `.github/workflows/docs-guard.yml` workflow explicitly rejects MINOR bumps to execution contracts.

**Git Tag Convention**: When freezing an execution contract, create a tag like:
```bash
git tag -a plan-R_PIPELINE-PHASE01-v1.0.0 -m "Phase 01 execution contract baseline"
```

---

## Enforcement Architecture

This versioning system is enforced through **four layers of automated and human controls**. Together, they make it practically impossible to skip a versioning step.

### Layer 1: Pre-Merge Validation (GitHub Actions)

**Workflow**: `.github/workflows/docs-guard.yml`

**Runs on**: Every PR that touches files in `/docs/**/*.md` or `/plans/**/*.md`

**What it checks**:
- ✅ All required front-matter fields are present and well-formed
- ✅ `semver` increases monotonically from previous version
- ✅ PR intent (BREAKING/feat/fix) matches bump size
- ✅ MINOR bumps to execution contracts are blocked
- ✅ `effective_date` is updated for MAJOR/MINOR changes (warning)
- ✅ `supersedes_version` points to the actual prior version
- ✅ `doc_key` is stable and tag-safe
- ✅ `status` is valid enum value
- ✅ `owner` matches CODEOWNERS entry

**Result**: If validation fails, the PR cannot be merged. Status check appears as "required" in GitHub.

**Example error messages**:
```
docs/standards/OC_CORE.md: semver must increase (old 1.3.0 -> new 1.3.0).
docs/standards/OC_CORE.md: PR suggests BREAKING change but bump is minor. Require MAJOR.
plans/R_PIPELINE/PHASE_01_EXECUTION_CONTRACT.md: execution_contract changes must be MAJOR or PATCH, not MINOR.
```

---

### Layer 2: Human Review (CODEOWNERS)

**File**: `.github/CODEOWNERS`

**Example configuration**:
```
# General documentation
/docs/**                                @team-docs

# Governance policies
/docs/standards/**                      @team-compliance

# Execution contracts
/plans/**/EXECUTION_CONTRACT.md         @team-compliance @team-pmo

# Versioning contract (this document)
/docs/standards/VERSIONING_OC.md        @team-compliance @platform-engineering
```

**Enforcement via Branch Protection**:
- "Require review from Code Owners" enabled on `main` branch
- MINOR/MAJOR bumps require explicit owner approval
- Execution contract changes require multi-team signoff

**Authority Levels**:
- **PATCH**: Any team member can approve (if automated tests pass)
- **MINOR**: Document owner must approve
- **MAJOR**: Owner + Compliance must approve
- **Execution Contract (any)**: Owner + PMO must approve, plus `contract-rebaseline` label

---

### Layer 3: Post-Merge Tagging (GitHub Actions)

**Workflow**: `.github/workflows/doc-tags.yml`

**Runs on**: Every push to `main` that touches files in `/docs/**/*.md` or `/plans/**/*.md`

**What it does**:
1. Extracts `doc_key` and `semver` from changed documents
2. Creates annotated git tag: `docs-{doc_key}-{semver}`
3. Pushes tags to remote

**Example tags created**:
```bash
docs-OC_CORE-1.3.0
docs-PIPELINE_POLICY-2.1.2
docs-R_PIPELINE_PHASE_01-1.0.0
```

**Why this matters**:
- Each document gets its own immutable snapshot
- You can checkout a specific policy version: `git checkout docs-OC_CORE-1.3.0`
- Enables precise audit trails and rollback
- Tags are signed and tamper-evident

---

### Layer 4: Runtime Validation (Pipeline Code)

**Function**: `Get-ActivePolicyVersions` (or equivalent in your language)

**Purpose**: Extract current document versions and log them with every pipeline run.

**Example Implementation (PowerShell)**:
```powershell
function Get-DocSemVer {
  param([string]$Path)
  $content = Get-Content -Raw -LiteralPath $Path
  if ($content -match '---\s*(.*?)---'s) {
    $yaml = $Matches[1]
    if ($yaml -match '(?m)^\s*semver:\s*([0-9]+\.[0-9]+\.[0-9]+)') { 
      return $Matches[1] 
    }
  }
  return $null
}

function Get-ActivePolicyVersions {
  return @{
    OC_CORE = Get-DocSemVer "docs/standards/OC_CORE.md"
    PIPELINE_POLICY = Get-DocSemVer "docs/standards/PIPELINE_POLICY.md"
    R_PIPELINE_PHASE_01 = Get-DocSemVer "plans/R_PIPELINE/PHASE_01_EXECUTION_CONTRACT.md"
  }
}

# Usage in pipeline startup
$runLedger = @{
  run_id = "2025-10-28T14-22-07Z_ULID01Q3..."
  repo_commit = (git rev-parse HEAD)
  policy_versions = Get-ActivePolicyVersions
  timestamp = Get-Date -Format "o"
}

# Serialize to ledger/log
$runLedger | ConvertTo-Json | Out-File "ledger/$($runLedger.run_id).json"
```

**Ledger Entry Example**:
```json
{
  "run_id": "2025-10-28T14-22-07Z_ULID01Q3...",
  "repo_commit": "d4e9c8a7f6b5c4d3e2f1a0b9c8d7e6f5a4b3c2d1",
  "policy_versions": {
    "OC_CORE": "1.3.0",
    "PIPELINE_POLICY": "2.1.2",
    "R_PIPELINE_PHASE_01": "1.0.0"
  },
  "timestamp": "2025-10-28T14:22:07-05:00"
}
```

**Why this matters**:
- Every run is tied to exact policy versions
- Enables forensic analysis: "What rules were in force for run X?"
- Supports compliance: "We followed v1.3.0 of the safety policy at execution time"
- Detects "rogue runs" using outdated policy versions

---

## Developer Workflow

**This section describes the step-by-step process for updating any governance document.**

### Prerequisites

Before you begin:
- [ ] You have a GitHub account with write access to the repository
- [ ] You have cloned the repository locally
- [ ] You understand which `contract_type` your document is
- [ ] You know the appropriate version bump level (MAJOR/MINOR/PATCH)

---

### Step 1: Make Your Changes

1. **Create a feature branch**:
   ```bash
   git checkout main
   git pull origin main
   git checkout -b docs/update-oc-core
   ```

2. **Open the document** (e.g., `docs/standards/OC_CORE.md`)

3. **Make your content changes** in the document body

4. **Update the front matter**:
   ```yaml
   ---
   doc_key: OC_CORE              # ← DO NOT CHANGE
   semver: 1.4.0                 # ← BUMP from 1.3.0
   status: active                # ← Usually stays the same
   effective_date: 2025-11-01    # ← UPDATE if meaning changed
   supersedes_version: 1.3.0     # ← SET to previous semver
   owner: Platform.Engineering   # ← Usually stays the same
   contract_type: policy         # ← DO NOT CHANGE
   ---
   ```

5. **Update the "Change Log (recent)" section** at the bottom of the document:
   ```markdown
   ## Change Log (recent)
   
   - **1.4.0** — 2025-11-01 — Added mandatory code review requirement
   - 1.3.0 — 2025-10-28 — Added Observability Gate to deployment pipeline
   - 1.2.2 — 2025-10-27 — Clarified retention policy language
   ```
   
   **Keep only the last 3 entries**. Remove older ones (they're preserved in git history).

---

### Step 2: Commit and Push

1. **Stage your changes**:
   ```bash
   git add docs/standards/OC_CORE.md
   ```

2. **Commit with a Conventional Commit message**:
   ```bash
   # For PATCH changes:
   git commit -m "fix: Clarify IaC retention policy wording"
   
   # For MINOR changes:
   git commit -m "feat: Add observability gate to deployment pipeline"
   
   # For MAJOR changes:
   git commit -m "feat!: Require pipeline runner for all code edits"
   # or include BREAKING CHANGE: in the commit body
   ```

3. **Push to remote**:
   ```bash
   git push origin docs/update-oc-core
   ```

---

### Step 3: Create Pull Request

1. **Open a PR on GitHub** from your branch to `main`

2. **Set the PR title** using Conventional Commit format:
   ```
   feat: Add mandatory code review requirement to OC_CORE
   ```
   
   **Important**: When squash-merging, GitHub uses the PR title as the commit message. The automated tooling parses this to validate your version bump.

3. **Fill out the PR template checklist**:
   ```markdown
   ### Versioning checklist
   - [x] Updated front matter: doc_key, semver, status, effective_date
   - [x] If MAJOR/MINOR, updated supersedes_version
   - [x] Execution Contract? → MAJOR for scope changes; PATCH only for editorial
   - [x] Kept only last 3 entries in "Change Log (recent)"
   ```

4. **Add labels** (if required):
   - For execution contracts: `contract-rebaseline` (if MAJOR)
   - For urgent changes: `priority-high`

---

### Step 4: Automated Validation

GitHub Actions automatically runs `.github/workflows/docs-guard.yml`:

**✅ If validation passes**:
- Green checkmark appears on the PR
- Status: "All checks have passed"
- You can proceed to review

**❌ If validation fails**:
- Red X appears on the PR
- Click "Details" to see error messages
- Common errors:
  ```
  docs/standards/OC_CORE.md: semver must increase (old 1.3.0 -> new 1.3.0).
  → Fix: You forgot to bump the version. Update to 1.3.1 or higher.
  
  docs/standards/OC_CORE.md: PR suggests BREAKING change but bump is minor.
  → Fix: Your PR title has "feat!" but you only bumped MINOR. Change to MAJOR.
  
  docs/standards/OC_CORE.md: invalid supersedes_version '1.2.0'.
  → Fix: The previous version was 1.3.0, not 1.2.0. Update supersedes_version.
  ```

**Fix errors and push updates**:
```bash
# Make corrections
git add docs/standards/OC_CORE.md
git commit -m "fix: Correct version bump to MAJOR"
git push origin docs/update-oc-core
```

The validation will re-run automatically.

---

### Step 5: Human Approval

**CODEOWNERS are automatically requested** based on the changed files.

**Approval requirements** (enforced by branch protection):

| Change Type | Approvers Needed | Timeline |
|-------------|------------------|----------|
| PATCH | Any team member | Usually same-day |
| MINOR | Document owner | 1-2 days |
| MAJOR | Owner + Compliance | 2-5 days |
| Execution Contract | Owner + PMO | 3-5 days, requires meeting |

**What reviewers check**:
- ✅ Version bump is appropriate for the change
- ✅ Content changes are correct and clear
- ✅ No unintended side effects or conflicts
- ✅ Effective date is reasonable
- ✅ Change log entry is accurate

**If changes are requested**:
1. Make the requested changes
2. Commit and push updates
3. Re-request review

---

### Step 6: Merge

Once all checks pass and approvals are granted:

1. **Merge the PR** (use "Squash and merge" if enabled)
2. **GitHub Actions automatically**:
   - Runs `.github/workflows/doc-tags.yml`
   - Creates git tag: `docs-OC_CORE-1.4.0`
   - Pushes tag to remote
3. **Versioned docs are published** (if configured with MkDocs/Docusaurus)

**Verify the tag was created**:
```bash
git fetch --tags
git tag -l 'docs-OC_CORE-*'
# Output:
# docs-OC_CORE-1.0.0
# docs-OC_CORE-1.1.0
# docs-OC_CORE-1.2.0
# docs-OC_CORE-1.3.0
# docs-OC_CORE-1.4.0  ← New tag
```

---

### Step 7: Communication

**For MAJOR or significant MINOR changes**:

1. **Announce the change** in team channels:
   ```
   📢 OC_CORE updated to v1.4.0
   
   What changed: All code edits now require mandatory code review
   Effective: 2025-11-01
   Link: https://github.com/org/repo/blob/docs-OC_CORE-1.4.0/docs/standards/OC_CORE.md
   Migration guide: [link if applicable]
   ```

2. **Update any related documentation** that references the old version

3. **Schedule training** if the change requires new skills/tools

---

## Governance and Authority

This section defines **who can approve what** and how exceptions are handled.

### Version Bump Authority Matrix

| Bump Type | Contract Type | Approvers Required | Additional Requirements |
|-----------|---------------|-------------------|------------------------|
| **PATCH** | policy | Any team member | Automated tests pass |
| **PATCH** | intent | Any team member | Owner notification (async) |
| **PATCH** | execution_contract | Owner | None |
| **MINOR** | policy | Owner | None |
| **MINOR** | intent | Owner | Lightweight review |
| **MINOR** | execution_contract | **BLOCKED** | Not allowed by design |
| **MAJOR** | policy | Owner + Compliance | Impact assessment required |
| **MAJOR** | intent | Owner + Stakeholder | Justification in PR description |
| **MAJOR** | execution_contract | Owner + PMO + Compliance | PR label `contract-rebaseline`, phase reset required |

### Role Definitions

| Role | Responsibilities | Examples |
|------|------------------|----------|
| **Owner** | Defined in `owner:` front matter field. Responsible for document accuracy and approvals. | `Platform.Engineering`, `Security.Team`, `Product.PMO` |
| **Compliance** | Reviews changes for regulatory, audit, and governance implications. | `@team-compliance` in CODEOWNERS |
| **PMO** | Reviews execution contracts for schedule, scope, and resource impacts. | `@team-pmo` in CODEOWNERS |
| **Team Member** | Anyone with write access to the repository. Can propose changes and approve PATCH updates. | All developers |

### Exception Process

**When to request an exception**:
- Emergency hotfix requires bypassing normal approval process
- Critical security issue requires immediate policy change
- External audit deadline cannot wait for normal review cycle

**How to request an exception**:

1. **Create an exception request** in the PR description:
   ```markdown
   ## EXCEPTION REQUEST
   
   **Reason**: Critical security vulnerability requires immediate policy update
   **Risk**: Bypassing normal 5-day review for MAJOR change
   **Mitigation**: Post-hoc review scheduled for 2025-11-05
   **Approver**: @security-lead
   ```

2. **Tag the appropriate exception approver**:
   - Security exceptions: `@security-lead`
   - Compliance exceptions: `@compliance-officer`
   - PMO exceptions: `@pmo-director`

3. **Document the exception** in the change log:
   ```markdown
   - **1.5.0** — 2025-11-02 — [EXCEPTION] Emergency security policy update (approved by @security-lead)
   ```

**Exception approvers** have the authority to override normal approval requirements but must:
- Document the decision in writing
- Schedule post-hoc review
- Report exceptions in quarterly governance review

---

## Audit Trail and Rollback

This section explains how to use the versioning system for audit, compliance, and rollback scenarios.

### Audit Scenarios

#### 1. "What policy was in force on date X?"

**Command**:
```bash
# Find all docs tags created before the date
git tag -l 'docs-*' --sort=-creatordate --format='%(creatordate:short) %(refname:short)' \
  | awk '$1 <= "2025-10-28"' \
  | head -20
```

**Output**:
```
2025-10-28 docs-OC_CORE-1.3.0
2025-10-27 docs-PIPELINE_POLICY-2.1.2
2025-10-26 docs-OC_CORE-1.2.2
...
```

**To view the exact document state**:
```bash
git show docs-OC_CORE-1.3.0:docs/standards/OC_CORE.md
```

---

#### 2. "What versions did Run X use?"

**Query your ledger**:
```powershell
# PowerShell example
Get-Content "ledger/2025-10-28T14-22-07Z_ULID01Q3.json" | ConvertFrom-Json | 
  Select-Object -ExpandProperty policy_versions

# Output:
# OC_CORE          : 1.3.0
# PIPELINE_POLICY  : 2.1.2
# R_PIPELINE_PHASE_01 : 1.0.0
```

**Reproduce the exact environment**:
```bash
# Checkout the commit and policy versions used in that run
git checkout d4e9c8a7f6b5c4d3e2f1a0b9c8d7e6f5a4b3c2d1
git checkout docs-OC_CORE-1.3.0 -- docs/standards/OC_CORE.md
git checkout docs-PIPELINE_POLICY-2.1.2 -- docs/standards/PIPELINE_POLICY.md
git checkout docs-R_PIPELINE_PHASE_01-1.0.0 -- plans/R_PIPELINE/PHASE_01_EXECUTION_CONTRACT.md
```

---

#### 3. "Show me all MAJOR changes in the last 6 months"

**Command**:
```bash
# List tags with major version bumps
git tag -l 'docs-*' --sort=-creatordate --format='%(creatordate:short) %(refname:short)' \
  | grep -E 'docs-.*-[0-9]+\.0\.0' \
  | head -20
```

**Or, query git log for MAJOR changes**:
```bash
git log --since="6 months ago" --grep="feat!" --grep="BREAKING CHANGE" --oneline -- docs/ plans/
```

---

#### 4. "What changed between version 1.2.0 and 1.4.0?"

**Command**:
```bash
# Show diff between two versions
git diff docs-OC_CORE-1.2.0..docs-OC_CORE-1.4.0 -- docs/standards/OC_CORE.md
```

**Or, view the changelog**:
```bash
# Extract changelog entries between versions
git show docs-OC_CORE-1.4.0:docs/standards/OC_CORE.md | grep -A 10 "## Change Log"
```

---

### Rollback Procedures

#### Scenario 1: Rollback a Bad Policy Change (Same Day)

**Situation**: You merged a MAJOR change today and discovered a critical flaw.

**Steps**:

1. **Revert the merge commit**:
   ```bash
   git revert <merge-commit-sha>
   git push origin main
   ```

2. **This automatically**:
   - Restores the previous document content
   - Creates a new commit (revert is not a silent edit)

3. **Update front matter** in the reverted document:
   ```yaml
   semver: 1.4.1                 # ← PATCH bump (revert is a fix)
   effective_date: 2025-11-01    # ← Today
   supersedes_version: 1.4.0     # ← The broken version
   ```

4. **Add to changelog**:
   ```markdown
   - **1.4.1** — 2025-11-01 — Reverted v1.4.0 due to critical flaw in requirement 3.2
   ```

5. **Create PR** with title: `fix: Revert OC_CORE v1.4.0 due to requirement error`

6. **Fast-track approval** (use exception process if needed)

---

#### Scenario 2: Restore to a Known-Good Baseline

**Situation**: Current policy version is broken. You want to restore to a specific older version.

**Steps**:

1. **Checkout the known-good version**:
   ```bash
   git checkout docs-OC_CORE-1.2.2 -- docs/standards/OC_CORE.md
   ```

2. **Update front matter** (this is a new MAJOR version):
   ```yaml
   semver: 2.0.0                 # ← MAJOR bump (rollback with breaking change)
   effective_date: 2025-11-02    # ← Today
   supersedes_version: 1.4.0     # ← Last version before rollback
   ```

3. **Add prominent notice** at the top of the document:
   ```markdown
   > **ROLLBACK NOTICE**: This version (2.0.0) restores the baseline from v1.2.2 
   > due to issues with v1.3.0-1.4.0. See rollback decision in PR #456.
   ```

4. **Add to changelog**:
   ```markdown
   - **2.0.0** — 2025-11-02 — [ROLLBACK] Restored baseline from v1.2.2, superseding v1.3.0-1.4.0
   ```

5. **Create PR** with title: `feat!: Rollback OC_CORE to v1.2.2 baseline`

6. **Include rollback decision document** in the PR description:
   ```markdown
   ## Rollback Decision
   
   **Versions affected**: 1.3.0, 1.3.1, 1.4.0
   **Root cause**: Incompatible requirement changes broke 3 production pipelines
   **Decision**: Restore to last known-good baseline (v1.2.2)
   **Impact**: Teams using v1.3.0+ must revert to v1.2.2 workflows
   **Migration**: [Link to migration guide]
   **Approval**: @compliance-officer, @platform-lead
   ```

7. **Communicate widely** (Slack, email, team meetings)

---

#### Scenario 3: Fork and Fix (Parallel Versions)

**Situation**: You need to maintain two policy versions temporarily (e.g., during a phased migration).

**This is NOT RECOMMENDED** but sometimes necessary for large organizations.

**Steps**:

1. **Create a maintenance branch** from the old version:
   ```bash
   git checkout docs-OC_CORE-1.2.2
   git checkout -b maintenance/oc-core-1.2.x
   git push origin maintenance/oc-core-1.2.x
   ```

2. **Apply fixes** to the maintenance branch as PATCH updates (1.2.3, 1.2.4, etc.)

3. **Continue forward development** on `main` (1.3.0, 1.4.0, etc.)

4. **Tag both versions** appropriately:
   ```bash
   # On maintenance branch
   docs-OC_CORE-1.2.3
   
   # On main branch
   docs-OC_CORE-1.4.0
   ```

5. **Document the fork** in both versions:
   ```markdown
   > **MAINTENANCE BRANCH**: This is the 1.2.x maintenance line. 
   > For the latest version, see main branch v1.4.0+.
   ```

6. **Set end-of-life date** for the maintenance branch:
   ```yaml
   status: deprecated
   effective_date: 2025-10-01
   deprecated_date: 2026-01-01  # ← When support ends
   ```

---

### Compliance Reporting

**Quarterly Governance Report** (generated automatically):

```bash
# Run this script quarterly
./scripts/generate-governance-report.sh 2025-Q4
```

**Report includes**:
- Total documents under version control
- Version bump statistics (MAJOR/MINOR/PATCH breakdown)
- Execution contract rebaselines (count and justifications)
- Exception requests (approved/denied, reason)
- Rollbacks (count, root causes)
- Average approval times (PATCH/MINOR/MAJOR)
- Compliance violations (if any)

**Output**: PDF report in `/reports/governance/2025-Q4-report.pdf`

---

## Bootstrap Instructions

**This section helps you set up the versioning system in a new repository or migrate an existing one.**

### Prerequisites Checklist

Before you begin, ensure:
- [ ] You have admin access to the GitHub repository
- [ ] You can create workflows in `.github/workflows/`
- [ ] You can configure branch protection rules
- [ ] You can create CODEOWNERS file
- [ ] You have Python 3.12+ available (for validation scripts)

---

### Step 1: Add GitHub Actions Workflows

Create the following workflow files:

#### A. `.github/workflows/docs-guard.yml`

<details>
<summary>Click to expand full workflow YAML</summary>

```yaml
name: Docs guard (front-matter + SemVer rules)
on:
  pull_request:
    types: [opened, edited, synchronize, reopened]
    paths:
      - 'docs/**/*.md'
      - 'plans/**/*.md'

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }

      - name: Set Python
        uses: actions/setup-python@v5
        with: { python-version: '3.12' }

      - name: Install deps
        run: pip install python-frontmatter pyyaml semver

      - name: Validate changed docs
        env:
          PR_TITLE: ${{ github.event.pull_request.title }}
          BASE_SHA: ${{ github.event.pull_request.base.sha }}
          HEAD_SHA: ${{ github.event.pull_request.head.sha }}
        run: |
          python - << 'PY'
          import os, subprocess, sys, json, re
          import frontmatter, yaml, semver

          def shell(cmd):
            return subprocess.check_output(cmd, shell=True, text=True).strip()

          base = os.environ["BASE_SHA"]
          head = os.environ["HEAD_SHA"]
          pr_title = os.environ.get("PR_TITLE","")
          files = shell(f"git diff --name-only {base} {head} -- 'docs/**/*.md' 'plans/**/*.md'").splitlines()
          if not files:
            sys.exit(0)

          # Determine semantic intent from PR title (squash-merge friendly)
          title = pr_title.lower()
          wants_major = "breaking change" in title or re.match(r'^(breaking|feat!)', title)
          wants_minor = (title.startswith("feat") and not wants_major)

          errors = []
          warnings = []

          for f in files:
            # Load old/new versions of the file to compare semver
            try:
              old_blob = shell(f"git show {base}:{f}")
              new_blob = shell(f"git show {head}:{f}")
            except subprocess.CalledProcessError:
              # New file?
              old_blob = ""
              new_blob = open(f, "r", encoding="utf-8").read()

            def parse(blob):
              if not blob:
                return None, None
              post = frontmatter.loads(blob)
              fm = post.metadata or {}
              dk = fm.get("doc_key")
              sv = fm.get("semver")
              ed = fm.get("effective_date")
              st = fm.get("status")
              ct = fm.get("contract_type")
              ssv = fm.get("supersedes_version")
              return {"doc_key":dk,"semver":sv,"effective_date":ed,"status":st,"contract_type":ct,"supersedes_version":ssv}, post.content

            old, _ = parse(old_blob)
            new, _ = parse(new_blob)

            if not new or not new.get("doc_key") or not new.get("semver"):
              errors.append(f"{f}: missing required front matter fields (doc_key, semver).")
              continue

            # Validate semver string
            try:
              new_v = semver.Version.parse(str(new["semver"]))
            except Exception:
              errors.append(f"{f}: invalid semver '{new.get('semver')}'.")
              continue

            # If old exists, compare versions
            if old and old.get("semver"):
              try:
                old_v = semver.Version.parse(str(old["semver"]))
              except Exception:
                errors.append(f"{f}: invalid previous semver '{old.get('semver')}'.")
                continue

              if new_v <= old_v:
                errors.append(f"{f}: semver must increase (old {old_v} -> new {new_v}).")

              # Enforce intent vs bump size
              bump = "patch"
              if new_v.major > old_v.major: bump = "major"
              elif new_v.minor > old_v.minor: bump = "minor"

              if wants_major and bump != "major":
                errors.append(f"{f}: PR suggests BREAKING change but bump is {bump}. Require MAJOR.")
              if wants_minor and bump == "patch":
                errors.append(f"{f}: PR suggests a feature but bump is PATCH. Require MINOR or MAJOR.")

              # For execution_contracts: disallow silent MINOR
              if (new.get("contract_type") == "execution_contract") and bump == "minor":
                errors.append(f"{f}: execution_contract changes must be MAJOR (scope change) or PATCH (editorial), not MINOR.")

              # Effective date monotonicity (warn if unchanged)
              if old.get("effective_date") == new.get("effective_date") and bump in ("minor","major"):
                warnings.append(f"{f}: consider updating effective_date for {bump} changes.")

              # Supersedes consistency
              ssv = new.get("supersedes_version")
              if ssv:
                try:
                  svp = semver.Version.parse(str(ssv))
                  if not (svp == old_v):
                    warnings.append(f"{f}: supersedes_version '{ssv}' doesn't match prior version '{old_v}'.")
                except Exception:
                  errors.append(f"{f}: invalid supersedes_version '{ssv}'.")
            else:
              # New document — require at least 1.0.0
              if new_v < semver.Version.parse("1.0.0"):
                errors.append(f"{f}: new docs should start at 1.0.0 or higher.")

            # Basic field sanity
            if new.get("status") not in (None,"active","deprecated","frozen"):
              errors.append(f"{f}: status must be active|deprecated|frozen.")

          for w in warnings:
            print(f"::warning::{w}")
          if errors:
            for e in errors:
              print(f"::error::{e}")
            sys.exit(1)
          PY
```

</details>

---

#### B. `.github/workflows/doc-tags.yml`

<details>
<summary>Click to expand full workflow YAML</summary>

```yaml
name: Per-doc tags
on:
  push:
    branches: [main]
    paths:
      - 'docs/**/*.md'
      - 'plans/**/*.md'

jobs:
  tag:
    runs-on: ubuntu-latest
    permissions:
      contents: write   # needed to push tags
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }

      - name: Set Python
        uses: actions/setup-python@v5
        with: { python-version: '3.12' }

      - name: Install deps
        run: pip install python-frontmatter pyyaml

      - name: Tag changed docs
        env:
          BEFORE: ${{ github.event.before }}
          AFTER: ${{ github.sha }}
        run: |
          python - << 'PY'
          import os, subprocess, frontmatter, re, sys

          def sh(c):
            return subprocess.check_output(c, shell=True, text=True).strip()

          before = os.environ["BEFORE"]
          after  = os.environ["AFTER"]
          files = sh(f"git diff --name-only {before} {after} -- 'docs/**/*.md' 'plans/**/*.md'").splitlines()
          if not files: sys.exit(0)

          created = []
          for f in files:
            try:
              text = open(f, "r", encoding="utf-8").read()
            except:
              # deleted or moved out; skip
              continue
            post = frontmatter.loads(text)
            meta = post.metadata or {}
            dk = meta.get("doc_key")
            sv = meta.get("semver")
            if not dk or not sv:
              print(f"Skipping {f}: missing doc_key/semver")
              continue
            tag = f"docs-{dk}-{sv}"
            # Create annotated tag if it doesn't exist
            existing = sh("git tag --list '"+tag+"'")
            if not existing:
              sh(f"git tag -a {tag} -m 'Snapshot {dk} v{sv} from {after[:7]}'")
              created.append(tag)

          if created:
            print("Creating tags:", created)
            sh("git push --tags")
          PY
```

</details>

---

### Step 2: Configure Branch Protection

1. **Navigate to**: Repository Settings → Branches → Branch protection rules

2. **Add rule for `main` branch**:
   - ☑️ Require a pull request before merging
   - ☑️ Require approvals (1 minimum)
   - ☑️ Dismiss stale pull request approvals when new commits are pushed
   - ☑️ Require review from Code Owners
   - ☑️ Require status checks to pass before merging
     - Add required check: `validate` (from docs-guard.yml)
   - ☑️ Require conversation resolution before merging
   - ☑️ Do not allow bypassing the above settings
   - ☑️ (Optional) Require signed commits

3. **Enable Merge Queue** (Settings → General → Pull Requests):
   - ☑️ Enable merge queue
   - Set merge method: Squash and merge
   - Default to pull request title for squash merge commits

---

### Step 3: Add CODEOWNERS

Create `.github/CODEOWNERS`:

```
# Default owner for everything
* @default-team

# Documentation
/docs/**                                @team-docs

# Governance policies
/docs/standards/**                      @team-compliance

# Plans and roadmaps
/plans/**                               @team-pmo

# Execution contracts (require multi-approval)
/plans/**/EXECUTION_CONTRACT.md         @team-compliance @team-pmo

# Versioning contract (this file is critical)
/docs/standards/VERSIONING_OC.md        @team-compliance @platform-engineering

# Example for specific high-stakes documents
/docs/standards/OC_CORE.md              @team-compliance @platform-engineering
/docs/standards/PIPELINE_POLICY.md      @team-compliance @platform-engineering
```

**Adjust team names** to match your organization's GitHub teams.

---

### Step 4: Add Pull Request Template

Create `.github/pull_request_template.md`:

```markdown
## Description

<!-- Briefly describe what changed and why -->

## Versioning Checklist

- [ ] Updated front matter: `doc_key`, `semver`, `status`, `effective_date`
- [ ] If MAJOR/MINOR, updated `supersedes_version`
- [ ] Execution Contract? → MAJOR for scope changes; PATCH only for editorial
- [ ] Kept only last 3 entries in "Change Log (recent)"
- [ ] PR title follows Conventional Commits (`feat:`, `fix:`, `feat!:`)

## Impact Assessment

<!-- For MAJOR changes, describe the impact on existing processes/workflows -->

## Related Issues

<!-- Link to issues, tickets, or discussions -->

Closes #
```

---

### Step 5: Migrate Existing Documents

For each existing document that should be version-controlled:

1. **Add front matter** at the top:
   ```yaml
   ---
   doc_key: OC_CORE              # Choose a stable identifier
   semver: 1.0.0                 # Start at 1.0.0 (grandfather clause)
   status: active
   effective_date: 2025-11-01    # Today's date
   supersedes_version: null      # No previous version
   owner: Platform.Engineering   # Assign appropriate owner
   contract_type: policy         # Choose appropriate type
   ---
   ```

2. **Add a simple change log section** at the bottom:
   ```markdown
   ## Change Log (recent)
   
   - **1.0.0** — 2025-11-01 — Initial version under version control
   ```

3. **Create a PR** for the migration:
   ```bash
   git checkout -b docs/migrate-oc-core
   git add docs/standards/OC_CORE.md
   git commit -m "feat: Add version control to OC_CORE"
   git push origin docs/migrate-oc-core
   ```

4. **Fast-track approval** (one-time exception for migration)

5. **Repeat** for all critical documents

**Pro tip**: Migrate documents incrementally, starting with the most critical policies.

---

### Step 6: Add Runtime Version Extraction

Add this function to your pipeline startup code:

**PowerShell Example**:
```powershell
# Save as: scripts/Get-DocVersions.ps1

function Get-DocSemVer {
  param([string]$Path)
  $content = Get-Content -Raw -LiteralPath $Path
  if ($content -match '---\s*(.*?)---'s) {
    $yaml = $Matches[1]
    if ($yaml -match '(?m)^\s*semver:\s*([0-9]+\.[0-9]+\.[0-9]+)') { 
      return $Matches[1] 
    }
  }
  return $null
}

function Get-ActivePolicyVersions {
  return @{
    OC_CORE = Get-DocSemVer "docs/standards/OC_CORE.md"
    PIPELINE_POLICY = Get-DocSemVer "docs/standards/PIPELINE_POLICY.md"
    R_PIPELINE_PHASE_01 = Get-DocSemVer "plans/R_PIPELINE/PHASE_01_EXECUTION_CONTRACT.md"
  }
}

# Usage in your pipeline
$runLedger = @{
  run_id = New-Ulid  # or your ID generation
  repo_commit = git rev-parse HEAD
  policy_versions = Get-ActivePolicyVersions
  timestamp = Get-Date -Format "o"
}

# Serialize to ledger
New-Item -ItemType Directory -Force -Path "ledger"
$runLedger | ConvertTo-Json -Depth 10 | 
  Out-File "ledger/$($runLedger.run_id).json"
```

**Python Example**:
```python
# Save as: scripts/get_doc_versions.py

import re
import json
from pathlib import Path
from datetime import datetime

def get_doc_semver(path: str) -> str | None:
    """Extract semver from document front matter."""
    content = Path(path).read_text(encoding='utf-8')
    match = re.search(r'---\s*(.*?)---', content, re.DOTALL)
    if match:
        yaml_content = match.group(1)
        semver_match = re.search(r'^\s*semver:\s*([0-9]+\.[0-9]+\.[0-9]+)', 
                                 yaml_content, re.MULTILINE)
        if semver_match:
            return semver_match.group(1)
    return None

def get_active_policy_versions() -> dict:
    """Get current versions of all policy documents."""
    return {
        "OC_CORE": get_doc_semver("docs/standards/OC_CORE.md"),
        "PIPELINE_POLICY": get_doc_semver("docs/standards/PIPELINE_POLICY.md"),
        "R_PIPELINE_PHASE_01": get_doc_semver("plans/R_PIPELINE/PHASE_01_EXECUTION_CONTRACT.md"),
    }

# Usage in your pipeline
if __name__ == "__main__":
    import subprocess
    
    run_ledger = {
        "run_id": "2025-11-01T12-00-00Z_ULID...",
        "repo_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip(),
        "policy_versions": get_active_policy_versions(),
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    
    # Serialize to ledger
    ledger_path = Path("ledger") / f"{run_ledger['run_id']}.json"
    ledger_path.parent.mkdir(exist_ok=True)
    ledger_path.write_text(json.dumps(run_ledger, indent=2))
```

---

### Step 7: Optional Enhancements

#### A. Versioned Documentation Publishing

**If using MkDocs + mike**:

1. Install dependencies:
   ```bash
   pip install mkdocs-material mike
   ```

2. Add workflow `.github/workflows/docs-publish.yml`:
   ```yaml
   name: Publish docs (mike)
   on:
     push:
       tags: ['v*.*.*', 'docs-*']
   
   jobs:
     publish:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4
         - uses: actions/setup-python@v5
         - run: pip install mkdocs-material mike
         - name: Deploy versioned docs
           run: |
             VER="${GITHUB_REF_NAME}"
             git config user.name "docs-bot"
             git config user.email "docs-bot@users.noreply.github.com"
             mike deploy --push --update-aliases "$VER" latest
   ```

3. Configure `mkdocs.yml` with your site structure

---

#### B. Changelog Automation

**Auto-generate changelogs from git history**:

```bash
# scripts/generate-changelog.sh
#!/bin/bash

DOC_KEY=$1  # e.g., OC_CORE
SINCE_TAG=$2  # e.g., docs-OC_CORE-1.0.0
UNTIL_TAG=$3  # e.g., docs-OC_CORE-2.0.0

git log "${SINCE_TAG}..${UNTIL_TAG}" \
  --pretty=format:"- %s (%h, %ad)" \
  --date=short \
  -- "docs/standards/${DOC_KEY}.md" \
  > "docs/changelogs/${DOC_KEY}_${SINCE_TAG}_to_${UNTIL_TAG}.md"
```

---

#### C. Semantic PR Title Validation

**Add workflow to validate PR titles**:

```yaml
# .github/workflows/pr-title-check.yml
name: PR title check
on:
  pull_request:
    types: [opened, edited, synchronize]

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: amannn/action-semantic-pull-request@v5
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

This enforces Conventional Commit format in PR titles.

---

### Step 8: Train Your Team

**Create a quickstart guide** (`docs/guides/VERSIONING_QUICKSTART.md`):

```markdown
# Versioning Quickstart (5 minutes)

## When updating a document:

1. **Bump the version** in the front matter based on your change:
   - Typo/clarification → PATCH (1.2.2 → 1.2.3)
   - New requirement/feature → MINOR (1.2.3 → 1.3.0)
   - Breaking change → MAJOR (1.3.0 → 2.0.0)

2. **Update `effective_date`** if the meaning changed

3. **Set `supersedes_version`** to the old version

4. **Update "Change Log (recent)"** (keep last 3 entries)

5. **Create PR** with Conventional Commit title:
   - `fix: Clarify wording in section 3`
   - `feat: Add new deployment requirement`
   - `feat!: Remove manual approval step`

6. **Wait for approval** based on change type:
   - PATCH: 1 approver (same day)
   - MINOR: Owner review (1-2 days)
   - MAJOR: Owner + Compliance (3-5 days)

7. **Merge** → tag created automatically!

## Need help?
- Read the full contract: `docs/standards/VERSIONING_OC.md`
- Ask in #docs-help Slack channel
- DM @docs-team
```

**Run a team training session**:
- Demo the PR workflow
- Show example errors and how to fix them
- Practice with a test document
- Answer questions

---

## Change Log (recent)

- **1.0.0** — 2025-11-01 — Initial versioning operating contract

---

## Appendix A: Complete Workflow Files

### docs-guard.yml (Full Source)

See [Step 1A](#a-githubworkflowsdocs-guardyml) above for the complete workflow.

### doc-tags.yml (Full Source)

See [Step 1B](#b-githubworkflowsdoc-tagsyml) above for the complete workflow.

---

## Appendix B: Runtime Integration Examples

### PowerShell Integration

See [Step 6](#step-6-add-runtime-version-extraction) above for the complete PowerShell implementation.

### Python Integration

See [Step 6](#step-6-add-runtime-version-extraction) above for the complete Python implementation.

### Bash Integration

```bash
#!/bin/bash
# scripts/get-doc-versions.sh

get_doc_semver() {
  local file=$1
  grep -A 5 '^---$' "$file" | grep 'semver:' | sed 's/semver: *//' | xargs
}

cat << EOF
{
  "OC_CORE": "$(get_doc_semver docs/standards/OC_CORE.md)",
  "PIPELINE_POLICY": "$(get_doc_semver docs/standards/PIPELINE_POLICY.md)",
  "R_PIPELINE_PHASE_01": "$(get_doc_semver plans/R_PIPELINE/PHASE_01_EXECUTION_CONTRACT.md)"
}
EOF
```

---

## Appendix C: Troubleshooting Common Issues

### Issue 1: "semver must increase" Error

**Problem**: You forgot to bump the version number.

**Solution**:
```yaml
# Change this:
semver: 1.3.0

# To this (based on your change type):
semver: 1.3.1  # PATCH
semver: 1.4.0  # MINOR
semver: 2.0.0  # MAJOR
```

---

### Issue 2: "PR suggests BREAKING change but bump is minor"

**Problem**: Your PR title says `feat!:` but you only bumped MINOR.

**Solution**: Either:
- Change your version to MAJOR (X.0.0), OR
- Remove the `!` from your PR title if it's not actually breaking

---

### Issue 3: "supersedes_version doesn't match prior version"

**Problem**: You set `supersedes_version: 1.2.0` but the previous version was `1.3.0`.

**Solution**:
```yaml
# Check git history for the actual previous version:
git log --oneline -- docs/standards/OC_CORE.md | head -5

# Then set supersedes_version correctly:
supersedes_version: 1.3.0  # Must match the previous semver exactly
```

---

### Issue 4: "execution_contract changes must be MAJOR or PATCH, not MINOR"

**Problem**: You tried to do a MINOR bump on an execution contract.

**Solution**: Execution contracts only allow:
- **MAJOR** (scope change, requires rebaseline)
- **PATCH** (editorial only, meaning unchanged)

If you need to add scope, bump to MAJOR and add the `contract-rebaseline` label.

---

### Issue 5: Tags Not Being Created

**Problem**: You merged a PR but the git tag wasn't created.

**Diagnosis**:
```bash
# Check if the workflow ran
gh run list --workflow=doc-tags.yml --limit 5

# Check if the tag exists locally but wasn't pushed
git tag -l 'docs-*' | grep OC_CORE
```

**Solution**:
- Ensure the workflow has `contents: write` permission
- Check GitHub Actions logs for errors
- Manually create the tag if needed:
  ```bash
  git tag -a docs-OC_CORE-1.4.0 -m "Manual tag creation"
  git push origin docs-OC_CORE-1.4.0
  ```

---

## Document Metadata

This document is self-governing and follows its own rules.

- **Version**: 1.0.0
- **Git Tag**: `docs-VERSIONING_OC-1.0.0`
- **Effective Date**: 2025-11-01
- **Last Updated**: 2025-11-01
- **Next Review**: 2026-02-01 (quarterly)

---

**END OF DOCUMENT**
