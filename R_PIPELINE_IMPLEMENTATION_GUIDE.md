# R_PIPELINE Implementation Guide

## Document Purpose

This guide provides the **practical methodology and step-by-step workflows** for implementing the R_PIPELINE system according to the Operating Contract. It integrates industry-standard practices (TDD, IaC, DevOps) with R_PIPELINE-specific requirements to ensure consistent, high-quality plugin development.

**Audience:** Developers, AI agents, and maintainers working on R_PIPELINE plugins and core infrastructure.

**Related Documents:**
- R_PIPELINE Operating Contract (canonical source of truth for what the system does)
- Plugin Specification Schema (JSON schema for plugin.spec.json)

---

## Table of Contents

1. [Development Philosophy & Principles](#1-development-philosophy--principles)
2. [Development Environment Setup](#2-development-environment-setup)
3. [Core Development Workflow (TDD + IaC)](#3-core-development-workflow-tdd--iac)
4. [Plugin Development Lifecycle](#4-plugin-development-lifecycle)
5. [Infrastructure as Code Requirements](#5-infrastructure-as-code-requirements)
6. [Testing Strategy](#6-testing-strategy)
7. [Observability & Tracing](#7-observability--tracing)
8. [Documentation Generation](#8-documentation-generation)
9. [CI/CD Pipeline Integration](#9-cicd-pipeline-integration)
10. [Validation & Quality Gates](#10-validation--quality-gates)
11. [Troubleshooting & Rollback](#11-troubleshooting--rollback)
12. [Appendix: Tool Reference](#appendix-tool-reference)

---

## 1. Development Philosophy & Principles

### 1.1 The R_PIPELINE Methodology Stack

R_PIPELINE integrates multiple industry-standard methodologies into a cohesive development approach:

```
┌─────────────────────────────────────────────────┐
│   Agile/DevOps (Process Layer)                  │  ← Iterative delivery, CI/CD
├─────────────────────────────────────────────────┤
│   BDD/TDD (Quality Layer)                       │  ← Tests first, behavior specs
├─────────────────────────────────────────────────┤
│   IaC/TDI (Infrastructure Layer)                │  ← Environment as code
├─────────────────────────────────────────────────┤
│   OpenTelemetry (Observability Layer)           │  ← Trace IDs, metrics, logs
├─────────────────────────────────────────────────┤
│   Docs-as-Code (Knowledge Layer)                │  ← Auto-generated documentation
└─────────────────────────────────────────────────┘
```

### 1.2 Core Principles

**Test-Driven Development (TDD)**
- **Red → Green → Refactor** cycle for all code changes
- Write failing test → implement minimum code → refactor
- Tests are "living documentation" that never go stale

**Infrastructure as Code (IaC)**
- All environment setup is versioned, reproducible code
- Infrastructure tests validate configuration correctness
- Environment is never a variable in failure diagnosis

**Test-Driven Infrastructure (TDI)**
- Write infrastructure tests before infrastructure code
- Ensures compliance-by-design
- Examples: "security policy must exist", "firewall rules enforced"

**Deterministic Behavior**
- Given same inputs + same environment → always same outputs
- No hidden state, no ambient configuration
- Every action is traceable and reversible

**Observability-First**
- Every run tagged with unique Trace ID
- All logs/metrics/spans linked to Trace ID
- Enables root cause analysis and self-healing

### 1.3 The Trust Model

```
┌─────────────────────────────────────────────────────┐
│  Plugins: Analyze & Recommend                       │
│  - Read files, detect patterns                      │
│  - Propose actions (classifications, moves, fixes)  │
│  - NEVER mutate state directly                      │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│  Core: Decide & Execute                             │
│  - Validate plugin recommendations                  │
│  - Check against policy/contract                    │
│  - Execute approved actions                         │
│  - Log everything to ledger                         │
└─────────────────────────────────────────────────────┘
```

This separation allows AI-generated plugins to be safe by design.

---

## 2. Development Environment Setup

### 2.1 Required Software

**Core Tools:**
- Git (version control)
- Python 3.10+ (for Python plugins and tooling)
- PowerShell 7+ (for PowerShell plugins)
- Visual Studio Code (recommended IDE)

**Python Toolchain:**
```bash
pip install --upgrade pip
pip install --break-system-packages \
    pytest pytest-cov pytest-testinfra \
    behave \
    black isort ruff pylint mypy pyright \
    opentelemetry-sdk opentelemetry-api \
    pulumi
```

**PowerShell Modules:**
```powershell
Install-Module -Name PSScriptAnalyzer -Scope CurrentUser -Force
Install-Module -Name Pester -MinimumVersion 5.0 -Scope CurrentUser -Force
Install-Module -Name PSRule -Scope CurrentUser -Force
```

**Infrastructure Tools:**
```bash
# Install Pulumi (Python-native IaC)
curl -fsSL https://get.pulumi.com | sh

# Install Terraform (alternative IaC)
# See: https://developer.hashicorp.com/terraform/downloads
```

**Observability Tools:**
```bash
# Install OpenTelemetry Collector (optional for local dev)
# See: https://opentelemetry.io/docs/collector/

# Jaeger (for trace visualization)
docker run -d --name jaeger \
  -p 16686:16686 \
  -p 4318:4318 \
  jaegertracing/all-in-one:latest
```

### 2.2 Repository Structure

```
R_PIPELINE/
├── core/
│   ├── OPERATING_CONTRACT.md          # System constitution
│   ├── Generate-PluginScaffold.ps1    # Plugin generator
│   ├── Validate-Plugin.ps1            # Validation tool
│   └── runner.py                      # Main pipeline orchestrator
├── infrastructure/
│   ├── pulumi/                        # IaC definitions
│   │   ├── __main__.py
│   │   ├── Pulumi.yaml
│   │   └── requirements.txt
│   └── tests/                         # Infrastructure tests
│       └── test_infrastructure.py
├── plugins/
│   └── {plugin-name}/
│       ├── plugin.spec.json           # Plugin definition (HUMAN)
│       ├── manifest.json              # Generated
│       ├── policy_snapshot.json       # Generated
│       ├── ledger_contract.json       # Generated
│       ├── README_PLUGIN.md           # Generated
│       ├── healthcheck.md             # Generated
│       ├── {plugin-name}.py           # Implementation
│       └── tests/
│           └── test_{plugin-name}.py  # Unit tests
├── .github/
│   └── workflows/
│       └── ci.yml                     # CI/CD pipeline
├── noxfile.py                         # Task automation
├── pyproject.toml                     # Python project config
└── README.md                          # Project overview
```

### 2.3 Environment Configuration

**Create `.env` file (never commit this):**
```bash
# OpenTelemetry Configuration
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
OTEL_SERVICE_NAME=r_pipeline
OTEL_LOG_LEVEL=info

# GitHub Configuration
GITHUB_TOKEN=your_token_here
GITHUB_REPO_OWNER=your_username
GITHUB_REPO_NAME=your_repo

# Development Mode
R_PIPELINE_ENV=development
R_PIPELINE_DRY_RUN=true
```

**VSCode Settings (`.vscode/settings.json`):**
```json
{
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": true,
  "python.linting.mypyEnabled": true,
  "python.formatting.provider": "black",
  "editor.formatOnSave": true,
  "python.testing.pytestEnabled": true,
  "python.testing.unittestEnabled": false,
  "[python]": {
    "editor.codeActionsOnSave": {
      "source.organizeImports": true
    }
  },
  "powershell.scriptAnalysis.enable": true,
  "powershell.codeFormatting.preset": "OTBS"
}
```

---

## 3. Core Development Workflow (TDD + IaC)

### 3.1 The Red-Green-Refactor Cycle

Every code change follows this cycle:

```
┌─────────────────────────────────────────────────┐
│ RED: Write a Failing Test                       │
│ - Define expected behavior                      │
│ - Run test → it fails (no implementation yet)   │
└─────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────┐
│ GREEN: Write Minimum Code to Pass               │
│ - Implement just enough to pass test            │
│ - Run test → it passes                          │
└─────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────┐
│ REFACTOR: Improve Code Quality                  │
│ - Clean up implementation                       │
│ - Run test → still passes                       │
└─────────────────────────────────────────────────┘
                    ↓
                 [Commit]
```

### 3.2 TDD for Application Code (Example: Python Plugin)

**Step 1: RED - Write Failing Test**

```python
# plugins/file-classifier/tests/test_file_classifier.py
import pytest
from file_classifier import classify_file

def test_classify_python_file():
    """Test that .py files are classified as 'python_module'"""
    # Arrange
    file_path = "test_script.py"
    file_content = "def hello(): pass"
    
    # Act
    result = classify_file(file_path, file_content)
    
    # Assert
    assert result["classification"] == "python_module"
    assert result["confidence"] >= 0.9
    assert result["recommended_location"] == "modules/python/"

# Run: pytest plugins/file-classifier/tests/
# Expected: FAIL (function doesn't exist yet)
```

**Step 2: GREEN - Implement Minimum Code**

```python
# plugins/file-classifier/file_classifier.py
def classify_file(file_path: str, file_content: str) -> dict:
    """Classify a file based on path and content"""
    if file_path.endswith('.py'):
        return {
            "classification": "python_module",
            "confidence": 0.95,
            "recommended_location": "modules/python/"
        }
    return {
        "classification": "unknown",
        "confidence": 0.0,
        "recommended_location": "quarantine/"
    }

# Run: pytest plugins/file-classifier/tests/
# Expected: PASS
```

**Step 3: REFACTOR - Improve Code**

```python
# plugins/file-classifier/file_classifier.py
from pathlib import Path
from typing import Dict

def classify_file(file_path: str, file_content: str) -> Dict[str, any]:
    """
    Classify a file based on path and content.
    
    Args:
        file_path: Path to the file
        file_content: Content of the file
        
    Returns:
        Classification result with confidence and recommended location
    """
    extension = Path(file_path).suffix.lower()
    
    classifiers = {
        '.py': ('python_module', 'modules/python/', 0.95),
        '.ps1': ('powershell_script', 'modules/powershell/', 0.95),
        '.md': ('documentation', 'docs/', 0.90),
    }
    
    if extension in classifiers:
        classification, location, confidence = classifiers[extension]
        return {
            "classification": classification,
            "confidence": confidence,
            "recommended_location": location
        }
    
    return {
        "classification": "unknown",
        "confidence": 0.0,
        "recommended_location": "quarantine/"
    }

# Run: pytest plugins/file-classifier/tests/
# Expected: PASS (still works after refactor)
```

### 3.3 TDD for Infrastructure (Test-Driven Infrastructure)

**Step 1: RED - Write Infrastructure Test**

```python
# infrastructure/tests/test_infrastructure.py
import pytest
import testinfra

def test_required_directories_exist(host):
    """Test that all required directories exist with correct permissions"""
    required_dirs = [
        "/opt/r_pipeline",
        "/opt/r_pipeline/plugins",
        "/opt/r_pipeline/logs",
        "/opt/r_pipeline/quarantine",
    ]
    
    for dir_path in required_dirs:
        directory = host.file(dir_path)
        assert directory.exists
        assert directory.is_directory
        assert directory.user == "r_pipeline"
        assert directory.mode == 0o755

def test_firewall_rules_configured(host):
    """Test that firewall allows only necessary ports"""
    # Check that only ports 22 (SSH) and 443 (HTTPS) are open
    iptables = host.iptables.rules('INPUT')
    
    # Should allow SSH
    assert any('22' in rule for rule in iptables)
    
    # Should NOT allow random ports
    assert not any('8080' in rule for rule in iptables)

def test_opentelemetry_collector_running(host):
    """Test that OpenTelemetry collector service is active"""
    service = host.service("otel-collector")
    assert service.is_running
    assert service.is_enabled

# Run: pytest infrastructure/tests/ --hosts=localhost
# Expected: FAIL (infrastructure not configured yet)
```

**Step 2: GREEN - Write Infrastructure Code**

```python
# infrastructure/pulumi/__main__.py
import pulumi
import pulumi_aws as aws

# Create required directories via EC2 user data
user_data = """#!/bin/bash
mkdir -p /opt/r_pipeline/{plugins,logs,quarantine}
useradd -r r_pipeline
chown -R r_pipeline:r_pipeline /opt/r_pipeline
chmod 755 /opt/r_pipeline/*
"""

# Security group with strict firewall rules
security_group = aws.ec2.SecurityGroup(
    "r-pipeline-sg",
    description="R_PIPELINE security group",
    ingress=[
        {"protocol": "tcp", "from_port": 22, "to_port": 22, "cidr_blocks": ["0.0.0.0/0"]},
        {"protocol": "tcp", "from_port": 443, "to_port": 443, "cidr_blocks": ["0.0.0.0/0"]},
    ],
    egress=[
        {"protocol": "-1", "from_port": 0, "to_port": 0, "cidr_blocks": ["0.0.0.0/0"]},
    ],
)

# Deploy infrastructure
pulumi.export("security_group_id", security_group.id)

# Run: pulumi up
# Then: pytest infrastructure/tests/ --hosts=your-server
# Expected: PASS
```

**Step 3: REFACTOR - Modularize Infrastructure**

```python
# infrastructure/pulumi/components/security.py
import pulumi_aws as aws

def create_security_group(name: str, allowed_ports: list) -> aws.ec2.SecurityGroup:
    """Create a security group with specified allowed ports"""
    ingress_rules = [
        {"protocol": "tcp", "from_port": port, "to_port": port, "cidr_blocks": ["0.0.0.0/0"]}
        for port in allowed_ports
    ]
    
    return aws.ec2.SecurityGroup(
        name,
        description=f"{name} security group",
        ingress=ingress_rules,
        egress=[
            {"protocol": "-1", "from_port": 0, "to_port": 0, "cidr_blocks": ["0.0.0.0/0"]},
        ],
    )

# infrastructure/pulumi/__main__.py
from components.security import create_security_group

security_group = create_security_group("r-pipeline-sg", [22, 443])
```

---

## 4. Plugin Development Lifecycle

### 4.1 The Complete Plugin Development Flow

```
┌─────────────────────────────────────────────────────────┐
│ 1. Define Plugin Spec (plugin.spec.json)                │
│    - Identify lifecycle event                           │
│    - Define input/output schemas                        │
│    - Specify dependencies                               │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ 2. Generate Scaffold (Generate-PluginScaffold.ps1)      │
│    - Creates directory structure                        │
│    - Generates all required artifacts                   │
│    - Creates test template                              │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ 3. Write Tests First (TDD Red Phase)                    │
│    - Write failing unit tests                           │
│    - Write failing integration tests                    │
│    - Define expected behavior                           │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ 4. Implement Logic (TDD Green Phase)                    │
│    - Write code between AUTO SECTION markers            │
│    - Minimum implementation to pass tests               │
│    - Ensure output matches schema                       │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ 5. Refactor & Improve (TDD Refactor Phase)              │
│    - Clean up code                                      │
│    - Add error handling                                 │
│    - Tests still pass                                   │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ 6. Run Validation (Validate-Plugin.ps1)                 │
│    - Check all artifacts present                        │
│    - Validate against contract                          │
│    - Run linters and formatters                         │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ 7. Local Testing (Nox Pipeline)                         │
│    - Run in isolated environment                        │
│    - Generate Trace ID                                  │
│    - Verify observability                               │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ 8. Code Review & CI (GitHub Actions)                    │
│    - Automated validation in CI                         │
│    - Peer review                                        │
│    - Merge to main                                      │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ 9. Monitor & Iterate                                    │
│    - Observe via Trace IDs                              │
│    - Collect metrics                                    │
│    - Continuous improvement                             │
└─────────────────────────────────────────────────────────┘
```

### 4.2 Step-by-Step: Creating a New Plugin

#### Step 1: Define Plugin Specification

Create `plugins/deduplicator/plugin.spec.json`:

```json
{
  "plugin_name": "deduplicator",
  "version": "1.0.0",
  "author": "your-email@example.com",
  "lifecycle_event": "FileDetected",
  "description": "Detects and resolves duplicate files",
  "language": "python",
  "entry_point": "deduplicator.py",
  "timeout_seconds": 30,
  "dependencies": {
    "powershell_modules": [],
    "python_packages": ["hashlib"]
  },
  "input_schema": {
    "type": "object",
    "properties": {
      "file_path": {"type": "string"},
      "file_hash": {"type": "string"},
      "trace_id": {"type": "string"}
    },
    "required": ["file_path", "file_hash", "trace_id"]
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "status": {"type": "string", "enum": ["success", "error"]},
      "is_duplicate": {"type": "boolean"},
      "duplicate_of": {"type": "string"},
      "recommended_action": {"type": "string"},
      "trace_id": {"type": "string"}
    },
    "required": ["status", "is_duplicate", "trace_id"]
  },
  "rollback_supported": true,
  "risk_level": "medium",
  "enabled": true
}
```

**Checklist:**
- [ ] Plugin name is unique (checked `/plugins/` directory)
- [ ] Lifecycle event exists (`FileDetected` is valid)
- [ ] Input schema includes `trace_id`
- [ ] Output schema includes all required ledger fields
- [ ] Dependencies are available

#### Step 2: Generate Plugin Scaffold

```powershell
# Run the generator
.\core\Generate-PluginScaffold.ps1 -SpecFile "plugins\deduplicator\plugin.spec.json"

# Output:
# ✓ Created directory: plugins/deduplicator/
# ✓ Generated manifest.json
# ✓ Generated policy_snapshot.json
# ✓ Generated ledger_contract.json
# ✓ Generated README_PLUGIN.md
# ✓ Generated healthcheck.md
# ✓ Created deduplicator.py with AUTO SECTION markers
# ✓ Created tests/test_deduplicator.py template
```

**Verify structure:**
```bash
tree plugins/deduplicator/
# plugins/deduplicator/
# ├── plugin.spec.json
# ├── manifest.json
# ├── policy_snapshot.json
# ├── ledger_contract.json
# ├── README_PLUGIN.md
# ├── healthcheck.md
# ├── deduplicator.py
# └── tests/
#     └── test_deduplicator.py
```

#### Step 3: Write Tests First (RED Phase)

```python
# plugins/deduplicator/tests/test_deduplicator.py
import pytest
import json
from deduplicator import detect_duplicate

def test_detect_new_file():
    """Test that new files are not marked as duplicates"""
    # Arrange
    input_data = {
        "file_path": "new_file.txt",
        "file_hash": "abc123",
        "trace_id": "test-trace-001"
    }
    
    # Act
    result = detect_duplicate(input_data)
    
    # Assert
    assert result["status"] == "success"
    assert result["is_duplicate"] == False
    assert result["trace_id"] == "test-trace-001"

def test_detect_duplicate_file():
    """Test that duplicate files are detected"""
    # Arrange - simulate existing file
    existing_file = {
        "file_path": "existing_file.txt",
        "file_hash": "xyz789",
        "trace_id": "test-trace-002"
    }
    
    duplicate_file = {
        "file_path": "duplicate_file.txt",
        "file_hash": "xyz789",  # Same hash!
        "trace_id": "test-trace-003"
    }
    
    # Act
    detect_duplicate(existing_file)  # Add to "database"
    result = detect_duplicate(duplicate_file)
    
    # Assert
    assert result["status"] == "success"
    assert result["is_duplicate"] == True
    assert result["duplicate_of"] == "existing_file.txt"
    assert result["recommended_action"] == "quarantine"

def test_error_handling():
    """Test that invalid input produces structured error"""
    # Arrange
    input_data = {
        "file_path": "test.txt",
        # Missing file_hash!
        "trace_id": "test-trace-004"
    }
    
    # Act
    result = detect_duplicate(input_data)
    
    # Assert
    assert result["status"] == "error"
    assert "error_message" in result

# Run: pytest plugins/deduplicator/tests/ -v
# Expected: ALL FAIL (no implementation yet)
```

#### Step 4: Implement Logic (GREEN Phase)

```python
# plugins/deduplicator/deduplicator.py
"""
Deduplicator Plugin - FileDetected Handler

Generated scaffold for R_PIPELINE
DO NOT EDIT outside AUTO SECTION markers
"""

# REGION: GENERATED - DO NOT EDIT
import json
import sys
from typing import Dict, Any

# File hash database (in real implementation, use persistent storage)
_hash_database = {}

# BEGIN AUTO SECTION - You can edit below this line

def detect_duplicate(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Detect if a file is a duplicate based on hash.
    
    Args:
        input_data: Dictionary with file_path, file_hash, trace_id
        
    Returns:
        Dictionary with status, is_duplicate, and other fields
    """
    try:
        # Validate required fields
        required_fields = ["file_path", "file_hash", "trace_id"]
        for field in required_fields:
            if field not in input_data:
                return {
                    "status": "error",
                    "error_message": f"Missing required field: {field}",
                    "trace_id": input_data.get("trace_id", "unknown")
                }
        
        file_path = input_data["file_path"]
        file_hash = input_data["file_hash"]
        trace_id = input_data["trace_id"]
        
        # Check if hash exists in database
        if file_hash in _hash_database:
            return {
                "status": "success",
                "is_duplicate": True,
                "duplicate_of": _hash_database[file_hash],
                "recommended_action": "quarantine",
                "trace_id": trace_id
            }
        
        # Not a duplicate - add to database
        _hash_database[file_hash] = file_path
        
        return {
            "status": "success",
            "is_duplicate": False,
            "duplicate_of": "",
            "recommended_action": "proceed",
            "trace_id": trace_id
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error_message": str(e),
            "trace_id": input_data.get("trace_id", "unknown")
        }

# END AUTO SECTION - You can edit above this line

# Main execution
if __name__ == "__main__":
    input_json = sys.stdin.read()
    input_data = json.loads(input_json)
    result = detect_duplicate(input_data)
    print(json.dumps(result, indent=2))

# ENDREGION: GENERATED
```

**Run tests:**
```bash
pytest plugins/deduplicator/tests/ -v
# Expected: ALL PASS
```

#### Step 5: Refactor & Improve

```python
# plugins/deduplicator/deduplicator.py (improved version)

# BEGIN AUTO SECTION

from pathlib import Path
from typing import Dict, Any, Set
import logging

# Configure logging
logger = logging.getLogger(__name__)

class DuplicateDetector:
    """Manages duplicate file detection with persistent storage"""
    
    def __init__(self, storage_path: str = "/opt/r_pipeline/data/hashes.json"):
        self.storage_path = Path(storage_path)
        self._hash_database: Dict[str, str] = {}
        self._load_database()
    
    def _load_database(self):
        """Load hash database from persistent storage"""
        if self.storage_path.exists():
            try:
                import json
                with open(self.storage_path, 'r') as f:
                    self._hash_database = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load hash database: {e}")
    
    def _save_database(self):
        """Save hash database to persistent storage"""
        try:
            import json
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.storage_path, 'w') as f:
                json.dump(self._hash_database, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save hash database: {e}")
    
    def check_duplicate(self, file_path: str, file_hash: str) -> tuple[bool, str]:
        """
        Check if file is a duplicate.
        
        Returns:
            (is_duplicate, duplicate_of_path)
        """
        if file_hash in self._hash_database:
            return (True, self._hash_database[file_hash])
        
        # Not a duplicate - register it
        self._hash_database[file_hash] = file_path
        self._save_database()
        return (False, "")

# Singleton instance
_detector = DuplicateDetector()

def detect_duplicate(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Detect if a file is a duplicate based on hash.
    
    Args:
        input_data: Dictionary with file_path, file_hash, trace_id
        
    Returns:
        Dictionary with status, is_duplicate, and other required fields
    """
    try:
        # Validate input schema
        required_fields = ["file_path", "file_hash", "trace_id"]
        missing_fields = [f for f in required_fields if f not in input_data]
        
        if missing_fields:
            return {
                "status": "error",
                "error_message": f"Missing required fields: {', '.join(missing_fields)}",
                "trace_id": input_data.get("trace_id", "unknown")
            }
        
        file_path = input_data["file_path"]
        file_hash = input_data["file_hash"]
        trace_id = input_data["trace_id"]
        
        # Log operation with trace ID
        logger.info(f"[{trace_id}] Checking duplicate for: {file_path}")
        
        # Check for duplicate
        is_duplicate, duplicate_of = _detector.check_duplicate(file_path, file_hash)
        
        result = {
            "status": "success",
            "is_duplicate": is_duplicate,
            "duplicate_of": duplicate_of,
            "recommended_action": "quarantine" if is_duplicate else "proceed",
            "trace_id": trace_id
        }
        
        logger.info(f"[{trace_id}] Result: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Error in detect_duplicate: {e}", exc_info=True)
        return {
            "status": "error",
            "error_message": str(e),
            "trace_id": input_data.get("trace_id", "unknown")
        }

# END AUTO SECTION
```

**Run tests again:**
```bash
pytest plugins/deduplicator/tests/ -v --cov=plugins/deduplicator
# Expected: ALL PASS with >80% coverage
```

#### Step 6: Run Validation

```powershell
.\core\Validate-Plugin.ps1 -PluginPath "plugins\deduplicator"

# Output:
# ✓ plugin.spec.json exists and is valid JSON
# ✓ All required artifacts present (8/8)
# ✓ manifest.json matches spec
# ✓ Input schema valid
# ✓ Output schema includes required ledger fields
# ✓ Handler file has correct structure
# ✓ Tests exist and pass
# ✓ Code coverage >80%
# ✓ Linting passed (Ruff, Pylint)
# ✓ Type checking passed (mypy)
#
# VALIDATION: PASS
# Plugin is ready for deployment
```

#### Step 7: Local Testing with Nox

```python
# noxfile.py (project root)
import nox

@nox.session(python=["3.10", "3.11"])
def test_plugin(session):
    """Run plugin tests in isolated environment"""
    session.install("-r", "requirements.txt")
    session.run("pytest", "plugins/deduplicator/tests/", "-v", "--cov")

@nox.session
def lint_plugin(session):
    """Run linters on plugin"""
    session.install("ruff", "pylint", "mypy")
    session.run("ruff", "check", "plugins/deduplicator/")
    session.run("pylint", "plugins/deduplicator/deduplicator.py")
    session.run("mypy", "plugins/deduplicator/deduplicator.py")
```

```bash
# Run all sessions
nox

# Run specific session
nox -s test_plugin

# Output:
# nox > Running session test_plugin-3.10
# nox > Creating virtual environment (virtualenv) using python3.10 in .nox/test_plugin-3-10
# nox > pytest plugins/deduplicator/tests/ -v --cov
# ======================== test session starts =========================
# collected 3 items
# 
# plugins/deduplicator/tests/test_deduplicator.py::test_detect_new_file PASSED
# plugins/deduplicator/tests/test_deduplicator.py::test_detect_duplicate_file PASSED
# plugins/deduplicator/tests/test_deduplicator.py::test_error_handling PASSED
# 
# ========================= 3 passed in 0.12s ==========================
```

#### Step 8: Commit & Push for CI

```bash
# Stage changes
git add plugins/deduplicator/

# Commit with trace reference
git commit -m "Add deduplicator plugin

- Detects duplicate files by hash
- Recommends quarantine for duplicates
- 100% test coverage
- All validations pass

Implements: FileDetected lifecycle event
Trace: trace-2025-001"

# Push to feature branch
git push origin feature/deduplicator

# Open Pull Request
# CI will automatically run all validations
```

---

## 5. Infrastructure as Code Requirements

### 5.1 Infrastructure Testing Strategy

All infrastructure must be validated before deployment:

```python
# infrastructure/tests/test_r_pipeline_infrastructure.py
import pytest
import testinfra

@pytest.fixture(scope='module')
def host(request):
    """Fixture for testinfra host"""
    return testinfra.get_host('local://')

class TestDirectoryStructure:
    """Test required directory structure"""
    
    def test_base_directory_exists(self, host):
        base_dir = host.file("/opt/r_pipeline")
        assert base_dir.exists
        assert base_dir.is_directory
        assert base_dir.user == "r_pipeline"
        assert base_dir.group == "r_pipeline"
        assert base_dir.mode == 0o755
    
    def test_plugin_directory_exists(self, host):
        plugin_dir = host.file("/opt/r_pipeline/plugins")
        assert plugin_dir.exists
        assert plugin_dir.is_directory
    
    def test_log_directory_writable(self, host):
        log_dir = host.file("/opt/r_pipeline/logs")
        assert log_dir.exists
        assert log_dir.is_directory
        assert log_dir.mode == 0o755

class TestSystemServices:
    """Test required system services"""
    
    def test_otel_collector_installed(self, host):
        otel = host.file("/usr/local/bin/otelcol")
        assert otel.exists
        assert otel.is_file
        assert otel.mode == 0o755
    
    def test_otel_service_running(self, host):
        service = host.service("otel-collector")
        assert service.is_running
        assert service.is_enabled
    
    def test_otel_listening_on_port(self, host):
        socket = host.socket("tcp://0.0.0.0:4318")
        assert socket.is_listening

class TestSecurityConfiguration:
    """Test security requirements"""
    
    def test_firewall_rules_restrictive(self, host):
        iptables = host.iptables.rules('INPUT')
        
        # Should allow SSH (22)
        assert any('dport 22' in rule for rule in iptables)
        
        # Should NOT allow unrestricted access
        assert not any('0.0.0.0/0' in rule and 'ACCEPT' in rule for rule in iptables)
    
    def test_selinux_enforcing(self, host):
        selinux = host.command("getenforce")
        assert selinux.stdout.strip() == "Enforcing"
    
    def test_ssh_password_auth_disabled(self, host):
        sshd_config = host.file("/etc/ssh/sshd_config")
        assert "PasswordAuthentication no" in sshd_config.content_string

class TestPythonEnvironment:
    """Test Python environment setup"""
    
    def test_python_version(self, host):
        python = host.command("python3 --version")
        assert python.rc == 0
        version = python.stdout.strip()
        # Ensure Python 3.10+
        assert "Python 3.1" in version
    
    def test_required_packages_installed(self, host):
        packages = [
            "pytest",
            "opentelemetry-sdk",
            "black",
            "ruff"
        ]
        for package in packages:
            pip_show = host.command(f"pip3 show {package}")
            assert pip_show.rc == 0, f"Package {package} not installed"

# Run: pytest infrastructure/tests/ -v --hosts=localhost
```

### 5.2 Pulumi Infrastructure Definition

```python
# infrastructure/pulumi/__main__.py
"""
R_PIPELINE Infrastructure Definition
"""
import pulumi
import pulumi_aws as aws
import pulumi_command as command

# Configuration
config = pulumi.Config()
environment = config.require("environment")  # dev, staging, prod

# User data script for instance initialization
user_data_script = """#!/bin/bash
set -e

# Create r_pipeline user
useradd -r -s /bin/bash r_pipeline

# Create directory structure
mkdir -p /opt/r_pipeline/{plugins,logs,quarantine,data}
chown -R r_pipeline:r_pipeline /opt/r_pipeline
chmod 755 /opt/r_pipeline/*

# Install Python 3.10
yum install -y python310 python310-pip

# Install OpenTelemetry Collector
curl -L -o /tmp/otelcol.tar.gz https://github.com/open-telemetry/opentelemetry-collector-releases/releases/download/v0.90.0/otelcol_0.90.0_linux_amd64.tar.gz
tar -xzf /tmp/otelcol.tar.gz -C /usr/local/bin/
chmod +x /usr/local/bin/otelcol

# Create systemd service for OpenTelemetry
cat > /etc/systemd/system/otel-collector.service <<'EOF'
[Unit]
Description=OpenTelemetry Collector
After=network.target

[Service]
Type=simple
User=r_pipeline
ExecStart=/usr/local/bin/otelcol --config=/opt/r_pipeline/otel-config.yaml
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
systemctl daemon-reload
systemctl enable otel-collector
systemctl start otel-collector

echo "R_PIPELINE infrastructure initialized"
"""

# Security Group
security_group = aws.ec2.SecurityGroup(
    f"r-pipeline-sg-{environment}",
    description=f"R_PIPELINE security group for {environment}",
    ingress=[
        # SSH access (restricted to specific IPs in production)
        aws.ec2.SecurityGroupIngressArgs(
            protocol="tcp",
            from_port=22,
            to_port=22,
            cidr_blocks=["10.0.0.0/8"] if environment == "prod" else ["0.0.0.0/0"]
        ),
        # HTTPS for API (if needed)
        aws.ec2.SecurityGroupIngressArgs(
            protocol="tcp",
            from_port=443,
            to_port=443,
            cidr_blocks=["0.0.0.0/0"]
        ),
    ],
    egress=[
        # Allow all outbound (for package installation, etc.)
        aws.ec2.SecurityGroupEgressArgs(
            protocol="-1",
            from_port=0,
            to_port=0,
            cidr_blocks=["0.0.0.0/0"]
        )
    ],
    tags={"Environment": environment, "ManagedBy": "Pulumi"}
)

# EC2 Instance
instance = aws.ec2.Instance(
    f"r-pipeline-instance-{environment}",
    instance_type="t3.medium" if environment == "prod" else "t3.small",
    ami="ami-0abcdef1234567890",  # Amazon Linux 2 AMI (update for your region)
    vpc_security_group_ids=[security_group.id],
    user_data=user_data_script,
    tags={"Name": f"R_PIPELINE-{environment}", "Environment": environment}
)

# Outputs
pulumi.export("instance_id", instance.id)
pulumi.export("instance_public_ip", instance.public_ip)
pulumi.export("security_group_id", security_group.id)
```

### 5.3 Infrastructure Deployment Workflow

```bash
# 1. Write infrastructure tests FIRST (TDD)
cat > infrastructure/tests/test_new_feature.py << 'EOF'
def test_new_s3_bucket_exists(host):
    # Test will fail until infrastructure is created
    pass
EOF

# Run tests (they fail)
pytest infrastructure/tests/ -v
# FAIL

# 2. Write Pulumi code to create infrastructure
cat >> infrastructure/pulumi/__main__.py << 'EOF'
# Create S3 bucket for logs
log_bucket = aws.s3.Bucket(
    "r-pipeline-logs",
    acl="private",
    versioning=aws.s3.BucketVersioningArgs(enabled=True)
)
EOF

# 3. Preview changes
pulumi preview

# 4. Apply changes
pulumi up

# 5. Run tests again (they pass)
pytest infrastructure/tests/ --hosts=your-server -v
# PASS

# 6. Commit infrastructure as code
git add infrastructure/
git commit -m "Add S3 bucket for log storage"
```

---

## 6. Testing Strategy

### 6.1 Testing Pyramid

```
                    ┌─────────────┐
                    │   Manual    │  ← Exploratory, UAT
                    │  Testing    │
                    └─────────────┘
                 ┌───────────────────┐
                 │   Integration     │  ← API, E2E tests
                 │      Tests        │
                 └───────────────────┘
            ┌───────────────────────────┐
            │      Unit Tests           │  ← Function-level
            │   (Largest Volume)        │
            └───────────────────────────┘
```

### 6.2 Unit Testing Guidelines

**For Python Plugins:**

```python
# plugins/example/tests/test_example.py
import pytest
from unittest.mock import Mock, patch
from example import process_file

class TestProcessFile:
    """Unit tests for process_file function"""
    
    def test_valid_input_produces_valid_output(self):
        """Happy path test"""
        input_data = {
            "file_path": "test.txt",
            "content": "hello",
            "trace_id": "test-001"
        }
        
        result = process_file(input_data)
        
        assert result["status"] == "success"
        assert result["trace_id"] == "test-001"
    
    def test_missing_required_field_returns_error(self):
        """Error handling test"""
        input_data = {
            "file_path": "test.txt",
            # Missing 'content'!
            "trace_id": "test-002"
        }
        
        result = process_file(input_data)
        
        assert result["status"] == "error"
        assert "content" in result["error_message"].lower()
    
    @patch('example.external_api_call')
    def test_external_api_called_correctly(self, mock_api):
        """Test external dependencies are called correctly"""
        mock_api.return_value = {"api_status": "ok"}
        
        input_data = {
            "file_path": "test.txt",
            "content": "data",
            "trace_id": "test-003"
        }
        
        result = process_file(input_data)
        
        # Verify API was called
        mock_api.assert_called_once()
        assert result["status"] == "success"
    
    def test_timeout_handled_gracefully(self):
        """Test that timeouts don't crash the plugin"""
        with patch('example.slow_operation', side_effect=TimeoutError):
            input_data = {
                "file_path": "test.txt",
                "content": "data",
                "trace_id": "test-004"
            }
            
            result = process_file(input_data)
            
            assert result["status"] == "error"
            assert "timeout" in result["error_message"].lower()
```

**For PowerShell Plugins:**

```powershell
# plugins/example/tests/test_example.ps1
Describe "Process-File" {
    Context "Valid Input" {
        It "Should return success status" {
            $input = @{
                FilePath = "test.txt"
                Content = "hello"
                TraceId = "test-001"
            }
            
            $result = Process-File -InputData $input
            
            $result.status | Should -Be "success"
            $result.trace_id | Should -Be "test-001"
        }
    }
    
    Context "Error Handling" {
        It "Should handle missing required fields" {
            $input = @{
                FilePath = "test.txt"
                # Missing Content!
                TraceId = "test-002"
            }
            
            $result = Process-File -InputData $input
            
            $result.status | Should -Be "error"
            $result.error_message | Should -Match "content"
        }
    }
    
    Context "External Dependencies" {
        It "Should call external API correctly" {
            Mock Invoke-ExternalAPI { return @{ api_status = "ok" } }
            
            $input = @{
                FilePath = "test.txt"
                Content = "data"
                TraceId = "test-003"
            }
            
            $result = Process-File -InputData $input
            
            Assert-MockCalled Invoke-ExternalAPI -Times 1
            $result.status | Should -Be "success"
        }
    }
}

# Run: Invoke-Pester -Path plugins/example/tests/
```

### 6.3 Integration Testing

```python
# tests/integration/test_plugin_integration.py
import pytest
import json
import subprocess
from pathlib import Path

class TestPluginIntegration:
    """Integration tests for plugin execution in R_PIPELINE"""
    
    def test_deduplicator_integration(self):
        """Test deduplicator plugin in full pipeline"""
        # Create test file
        test_file = Path("/tmp/test_dup.txt")
        test_file.write_text("duplicate content")
        
        # Run pipeline with deduplicator plugin
        result = subprocess.run(
            ["python3", "core/runner.py", "--file", str(test_file)],
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        
        # Parse output
        output = json.loads(result.stdout)
        
        # Verify deduplicator was invoked
        assert "deduplicator" in output["plugins_executed"]
        assert output["status"] == "success"
    
    def test_multi_plugin_execution_order(self):
        """Test that plugins execute in correct lifecycle order"""
        # This would test:
        # 1. FileDetected plugins run first
        # 2. PreMerge plugins run before merge
        # 3. PostMerge plugins run after merge
        pass
    
    def test_trace_id_propagation(self):
        """Test that trace ID is propagated through all plugins"""
        result = subprocess.run(
            ["python3", "core/runner.py", "--trace-id", "test-trace-999"],
            capture_output=True,
            text=True
        )
        
        output = json.loads(result.stdout)
        
        # Every plugin should have received the same trace ID
        for plugin_result in output["plugin_results"]:
            assert plugin_result["trace_id"] == "test-trace-999"
```

### 6.4 Behavior-Driven Development (BDD) Tests

```gherkin
# features/file_deduplication.feature
Feature: File Deduplication
  As a developer
  I want duplicate files to be detected automatically
  So that I don't commit the same file twice

  Scenario: New file is not marked as duplicate
    Given a new file "example.txt" with content "hello world"
    When I run the deduplicator plugin
    Then the file should not be marked as duplicate
    And the file should be allowed to proceed

  Scenario: Duplicate file is detected
    Given an existing file "original.txt" with hash "abc123"
    And a new file "duplicate.txt" with the same hash "abc123"
    When I run the deduplicator plugin on "duplicate.txt"
    Then the file should be marked as duplicate
    And the recommended action should be "quarantine"
    And the duplicate_of field should be "original.txt"

  Scenario: Plugin respects timeout
    Given a file that takes 60 seconds to process
    And the plugin timeout is set to 30 seconds
    When I run the deduplicator plugin
    Then the plugin should timeout gracefully
    And return an error status
```

```python
# features/steps/deduplication_steps.py
from behave import given, when, then
from deduplicator import detect_duplicate

@given('a new file "{filename}" with content "{content}"')
def step_new_file(context, filename, content):
    context.file = {
        "file_path": filename,
        "file_hash": hash(content),
        "trace_id": "bdd-test-001"
    }

@when('I run the deduplicator plugin')
def step_run_deduplicator(context):
    context.result = detect_duplicate(context.file)

@then('the file should not be marked as duplicate')
def step_not_duplicate(context):
    assert context.result["is_duplicate"] == False
```

```bash
# Run BDD tests
behave features/
```

---

## 7. Observability & Tracing

### 7.1 OpenTelemetry Integration

Every plugin execution must be instrumented with OpenTelemetry:

```python
# core/otel_config.py
"""OpenTelemetry configuration for R_PIPELINE"""
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
import os

def setup_opentelemetry():
    """Initialize OpenTelemetry for R_PIPELINE"""
    
    # Create resource with service information
    resource = Resource.create({
        "service.name": "r_pipeline",
        "service.version": "1.0.0",
        "deployment.environment": os.getenv("R_PIPELINE_ENV", "development")
    })
    
    # Create tracer provider
    provider = TracerProvider(resource=resource)
    
    # Configure OTLP exporter
    otlp_exporter = OTLPSpanExporter(
        endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318/v1/traces")
    )
    
    # Add span processor
    provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
    
    # Set global tracer provider
    trace.set_tracer_provider(provider)
    
    return trace.get_tracer(__name__)

# Global tracer
tracer = setup_opentelemetry()
```

### 7.2 Instrumenting Plugin Code

```python
# plugins/deduplicator/deduplicator.py
from opentelemetry import trace
import logging

# Get tracer
tracer = trace.get_tracer(__name__)
logger = logging.getLogger(__name__)

def detect_duplicate(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """Detect duplicates with OpenTelemetry tracing"""
    
    # Extract trace ID from input
    trace_id = input_data.get("trace_id", "unknown")
    
    # Create span for this operation
    with tracer.start_as_current_span(
        "detect_duplicate",
        attributes={
            "plugin.name": "deduplicator",
            "plugin.version": "1.0.0",
            "trace.id": trace_id,
            "file.path": input_data.get("file_path", ""),
        }
    ) as span:
        try:
            # Your plugin logic here
            logger.info(f"[{trace_id}] Starting duplicate detection")
            
            # Add events to span
            span.add_event("Checking hash database")
            
            # ... duplicate detection logic ...
            
            span.add_event("Duplicate check complete", {
                "is_duplicate": is_duplicate
            })
            
            # Set span status
            span.set_status(trace.Status(trace.StatusCode.OK))
            
            result = {
                "status": "success",
                "is_duplicate": is_duplicate,
                "trace_id": trace_id
            }
            
            # Add result to span attributes
            span.set_attributes({
                "result.status": "success",
                "result.is_duplicate": is_duplicate
            })
            
            return result
            
        except Exception as e:
            # Record exception in span
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            
            logger.error(f"[{trace_id}] Error: {e}", exc_info=True)
            
            return {
                "status": "error",
                "error_message": str(e),
                "trace_id": trace_id
            }
```

### 7.3 Trace ID Propagation

```python
# core/runner.py
"""Main pipeline runner with trace ID propagation"""
import uuid
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

def run_pipeline(file_path: str, trace_id: str = None):
    """
    Run R_PIPELINE with trace ID propagation.
    
    Args:
        file_path: Path to file being processed
        trace_id: Optional trace ID (generated if not provided)
    """
    
    # Generate trace ID if not provided
    if not trace_id:
        trace_id = f"trace-{uuid.uuid4()}"
    
    # Create root span for entire pipeline run
    with tracer.start_as_current_span(
        "pipeline_run",
        attributes={
            "trace.id": trace_id,
            "file.path": file_path
        }
    ) as root_span:
        
        print(f"[{trace_id}] Starting pipeline for: {file_path}")
        
        # Execute lifecycle: FileDetected
        with tracer.start_as_current_span("lifecycle.file_detected") as span:
            detected_plugins = execute_lifecycle_plugins(
                "FileDetected",
                {"file_path": file_path, "trace_id": trace_id}
            )
            span.set_attribute("plugins.count", len(detected_plugins))
        
        # Execute lifecycle: PreMerge
        with tracer.start_as_current_span("lifecycle.pre_merge") as span:
            premerge_plugins = execute_lifecycle_plugins(
                "PreMerge",
                {"file_path": file_path, "trace_id": trace_id}
            )
            span.set_attribute("plugins.count", len(premerge_plugins))
        
        # ... more lifecycle events ...
        
        print(f"[{trace_id}] Pipeline complete")
        root_span.set_status(trace.Status(trace.StatusCode.OK))

def execute_lifecycle_plugins(event: str, input_data: dict):
    """Execute all plugins for a lifecycle event"""
    results = []
    
    for plugin in get_plugins_for_event(event):
        # Each plugin gets the same trace_id
        result = plugin.execute(input_data)
        results.append(result)
    
    return results
```

### 7.4 Viewing Traces in Jaeger

```bash
# Start Jaeger (if not already running)
docker run -d --name jaeger \
  -e COLLECTOR_OTLP_ENABLED=true \
  -p 16686:16686 \
  -p 4318:4318 \
  jaegertracing/all-in-one:latest

# Run pipeline
python core/runner.py --file test.txt

# View traces at http://localhost:16686
# Search for service: "r_pipeline"
# Find your trace ID and see:
# - All plugin executions
# - Duration of each operation
# - Any errors or exceptions
# - Custom attributes and events
```

---

## 8. Documentation Generation

### 8.1 The Documentation-as-Code Pattern

R_PIPELINE uses a "single source of truth" pattern for documentation:

```
plugin.spec.json (HUMAN WRITES THIS)
        ↓
Generate-PluginScaffold.ps1
        ↓
┌───────────────────────────────────────┐
│ manifest.json                         │  ← Machine-readable metadata
│ policy_snapshot.json                  │  ← Security/policy info
│ ledger_contract.json                  │  ← Required log fields
│ README_PLUGIN.md                      │  ← Human-readable docs
│ healthcheck.md                        │  ← Monitoring guide
└───────────────────────────────────────┘
```

### 8.2 Documentation Generator Implementation

```python
# core/generate_plugin_docs.py
"""Generate plugin documentation from spec"""
import json
from pathlib import Path
from typing import Dict
import datetime

def generate_plugin_documentation(spec_path: Path):
    """
    Generate all documentation artifacts from plugin.spec.json
    
    Args:
        spec_path: Path to plugin.spec.json
    """
    # Load spec
    with open(spec_path) as f:
        spec = json.load(f)
    
    plugin_dir = spec_path.parent
    
    # Generate each artifact
    generate_manifest(spec, plugin_dir)
    generate_policy_snapshot(spec, plugin_dir)
    generate_ledger_contract(spec, plugin_dir)
    generate_readme(spec, plugin_dir)
    generate_healthcheck(spec, plugin_dir)
    
    print(f"✓ Generated all documentation for {spec['plugin_name']}")

def generate_manifest(spec: Dict, plugin_dir: Path):
    """Generate manifest.json"""
    manifest = {
        "plugin_name": spec["plugin_name"],
        "version": spec["version"],
        "author": spec["author"],
        "lifecycle_event": spec["lifecycle_event"],
        "entry_point": spec["entry_point"],
        "enabled": spec["enabled"],
        "generated_at": datetime.datetime.utcnow().isoformat(),
        "contract_version": "1.0.0"
    }
    
    with open(plugin_dir / "manifest.json", 'w') as f:
        json.dump(manifest, f, indent=2)

def generate_readme(spec: Dict, plugin_dir: Path):
    """Generate README_PLUGIN.md"""
    readme = f"""# {spec['plugin_name']}

> Version: {spec['version']}  
> Lifecycle Event: {spec['lifecycle_event']}  
> Author: {spec['author']}

## Description

{spec['description']}

## Input Schema

```json
{json.dumps(spec['input_schema'], indent=2)}
```

## Output Schema

```json
{json.dumps(spec['output_schema'], indent=2)}
```

## Dependencies

### Python Packages
{chr(10).join(f"- {pkg}" for pkg in spec['dependencies'].get('python_packages', []))}

### PowerShell Modules
{chr(10).join(f"- {mod}" for mod in spec['dependencies'].get('powershell_modules', []))}

## Configuration

- **Timeout**: {spec['timeout_seconds']} seconds
- **Risk Level**: {spec['risk_level']}
- **Rollback Supported**: {'Yes' if spec['rollback_supported'] else 'No'}

## Usage

This plugin is automatically invoked during the `{spec['lifecycle_event']}` lifecycle event.

## Testing

```bash
pytest plugins/{spec['plugin_name']}/tests/ -v
```

## Validation

```bash
./core/Validate-Plugin.ps1 -PluginPath "plugins/{spec['plugin_name']}"
```

---

*This document was auto-generated from plugin.spec.json on {datetime.datetime.utcnow().isoformat()}*
"""
    
    with open(plugin_dir / "README_PLUGIN.md", 'w') as f:
        f.write(readme)

def generate_healthcheck(spec: Dict, plugin_dir: Path):
    """Generate healthcheck.md"""
    healthcheck = f"""# Healthcheck: {spec['plugin_name']}

## Monitoring Guidelines

### Expected Behavior

- **Execution Time**: Should complete within {spec['timeout_seconds']} seconds
- **Success Rate**: Should maintain >99% success rate
- **Error Patterns**: Structured errors with trace IDs

### Metrics to Monitor

```
r_pipeline_plugin_execution_duration_seconds{{plugin="{spec['plugin_name']}"}}
r_pipeline_plugin_execution_total{{plugin="{spec['plugin_name']}", status="success"}}
r_pipeline_plugin_execution_total{{plugin="{spec['plugin_name']}", status="error"}}
```

### Alerting Thresholds

| Metric | Threshold | Action |
|--------|-----------|--------|
| Execution Duration | > {spec['timeout_seconds']}s | Investigate slow performance |
| Error Rate | > 1% | Check recent code changes |
| Not Executed | > 1 hour | Verify plugin is enabled |

### Manual Health Check

```bash
# Test plugin in isolation
python plugins/{spec['plugin_name']}/{spec['entry_point']} << 'EOF'
{{
  "file_path": "test.txt",
  "trace_id": "health-check-001"
}}
EOF
```

Expected output: `{{"status": "success", ...}}`

### Common Issues

1. **Timeout Errors**
   - Check for slow external API calls
   - Verify database connection pools

2. **Missing Dependencies**
   - Ensure all packages installed: `pip install -r requirements.txt`

3. **Permission Errors**
   - Verify plugin runs as `r_pipeline` user

---

*Auto-generated healthcheck documentation*
"""
    
    with open(plugin_dir / "healthcheck.md", 'w') as f:
        f.write(healthcheck)
```

### 8.3 Using MkDocs for Project Documentation

```yaml
# mkdocs.yml (project root)
site_name: R_PIPELINE Documentation
site_description: Documentation for R_PIPELINE Autonomous System
site_author: Your Team

theme:
  name: material
  palette:
    primary: indigo
    accent: indigo
  features:
    - navigation.tabs
    - navigation.sections
    - toc.integrate

nav:
  - Home: index.md
  - Operating Contract: OPERATING_CONTRACT.md
  - Implementation Guide: IMPLEMENTATION_GUIDE.md
  - Plugins:
      - Overview: plugins/index.md
      - Deduplicator: plugins/deduplicator/README_PLUGIN.md
      - File Classifier: plugins/file-classifier/README_PLUGIN.md
  - API Reference: api/index.md
  - Troubleshooting: troubleshooting.md

plugins:
  - search
  - mkdocstrings:
      handlers:
        python:
          options:
            docstring_style: google

markdown_extensions:
  - admonition
  - codehilite
  - toc:
      permalink: true
  - pymdownx.highlight
  - pymdownx.superfences
```

```bash
# Install MkDocs
pip install mkdocs mkdocs-material mkdocstrings

# Build documentation
mkdocs build

# Serve locally
mkdocs serve
# View at http://127.0.0.1:8000

# Deploy to GitHub Pages
mkdocs gh-deploy
```

---

## 9. CI/CD Pipeline Integration

### 9.1 GitHub Actions Workflow

```yaml
# .github/workflows/ci.yml
name: R_PIPELINE CI/CD

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]

env:
  PYTHON_VERSION: '3.10'
  OTEL_EXPORTER_OTLP_ENDPOINT: http://localhost:4318

jobs:
  validate-infrastructure:
    name: Validate Infrastructure (TDI)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      
      - name: Install Dependencies
        run: |
          pip install --upgrade pip
          pip install pytest pytest-testinfra pulumi
      
      - name: Run Infrastructure Tests
        run: |
          pytest infrastructure/tests/ -v --tb=short
      
      - name: Pulumi Preview
        uses: pulumi/actions@v4
        with:
          command: preview
          work-dir: infrastructure/pulumi
        env:
          PULUMI_ACCESS_TOKEN: ${{ secrets.PULUMI_ACCESS_TOKEN }}

  lint-and-format:
    name: Lint & Format Check
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      
      - name: Install Linters
        run: |
          pip install ruff black isort mypy pylint
      
      - name: Run Ruff
        run: ruff check . --output-format=github
      
      - name: Check Black Formatting
        run: black --check .
      
      - name: Check Import Sorting
        run: isort --check-only .
      
      - name: Run MyPy
        run: mypy core/ plugins/
      
      - name: Run Pylint
        run: pylint core/ plugins/ --output-format=colorized

  test-plugins:
    name: Test Plugins (TDD)
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.10', '3.11']
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Python ${{ matrix.python-version }}
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}
      
      - name: Install Dependencies
        run: |
          pip install --upgrade pip
          pip install -r requirements.txt
          pip install pytest pytest-cov
      
      - name: Run Unit Tests
        run: |
          pytest plugins/ -v --cov=plugins --cov-report=xml --cov-report=term
      
      - name: Upload Coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml
          flags: unittests

  validate-plugins:
    name: Validate Plugin Contracts
    runs-on: ubuntu-latest
    needs: [lint-and-format, test-plugins]
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup PowerShell
        uses: actions/setup-powershell@v1
      
      - name: Run Plugin Validation
        shell: pwsh
        run: |
          $plugins = Get-ChildItem -Path plugins -Directory
          foreach ($plugin in $plugins) {
            Write-Host "Validating $($plugin.Name)..."
            .\core\Validate-Plugin.ps1 -PluginPath $plugin.FullName
          }

  integration-tests:
    name: Integration Tests
    runs-on: ubuntu-latest
    needs: [validate-plugins]
    services:
      jaeger:
        image: jaegertracing/all-in-one:latest
        ports:
          - 16686:16686
          - 4318:4318
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      
      - name: Install Dependencies
        run: |
          pip install -r requirements.txt
          pip install opentelemetry-sdk opentelemetry-exporter-otlp
      
      - name: Run Integration Tests
        run: |
          pytest tests/integration/ -v --tb=short
        env:
          OTEL_EXPORTER_OTLP_ENDPOINT: http://localhost:4318

  build-docs:
    name: Build Documentation
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      
      - name: Install MkDocs
        run: |
          pip install mkdocs mkdocs-material mkdocstrings
      
      - name: Build Documentation
        run: mkdocs build --strict
      
      - name: Deploy to GitHub Pages
        if: github.ref == 'refs/heads/main'
        run: mkdocs gh-deploy --force

  deploy:
    name: Deploy to Production
    runs-on: ubuntu-latest
    needs: [validate-infrastructure, integration-tests]
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v3
      
      - name: Deploy Infrastructure
        uses: pulumi/actions@v4
        with:
          command: up
          work-dir: infrastructure/pulumi
          stack-name: production
        env:
          PULUMI_ACCESS_TOKEN: ${{ secrets.PULUMI_ACCESS_TOKEN }}
      
      - name: Deploy Application
        run: |
          # Your deployment script here
          echo "Deploying R_PIPELINE to production..."
```

### 9.2 Pre-commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json
      - id: check-added-large-files

  - repo: https://github.com/psf/black
    rev: 23.7.0
    hooks:
      - id: black
        language_version: python3.10

  - repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
      - id: isort

  - repo: https://github.com/charliermarsh/ruff-pre-commit
    rev: v0.0.285
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]

  - repo: local
    hooks:
      - id: validate-plugins
        name: Validate Plugin Contracts
        entry: pwsh -File core/Validate-Plugin.ps1
        language: system
        pass_filenames: false
        always_run: true
```

```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

---

## 10. Validation & Quality Gates

### 10.1 Plugin Validation Checklist

The `Validate-Plugin.ps1` script enforces these requirements:

```powershell
# core/Validate-Plugin.ps1
param(
    [Parameter(Mandatory=$true)]
    [string]$PluginPath
)

$ErrorActionPreference = "Stop"
$validationPassed = $true

Write-Host "`n=== Validating Plugin: $PluginPath ===" -ForegroundColor Cyan

# 1. Check plugin.spec.json exists and is valid
Write-Host "`nChecking plugin.spec.json..." -ForegroundColor Yellow
if (-not (Test-Path "$PluginPath/plugin.spec.json")) {
    Write-Host "✗ plugin.spec.json not found" -ForegroundColor Red
    $validationPassed = $false
} else {
    try {
        $spec = Get-Content "$PluginPath/plugin.spec.json" | ConvertFrom-Json
        Write-Host "✓ plugin.spec.json valid" -ForegroundColor Green
    } catch {
        Write-Host "✗ plugin.spec.json invalid JSON" -ForegroundColor Red
        $validationPassed = $false
    }
}

# 2. Check required artifacts exist
Write-Host "`nChecking required artifacts..." -ForegroundColor Yellow
$requiredFiles = @(
    "manifest.json",
    "policy_snapshot.json",
    "ledger_contract.json",
    "README_PLUGIN.md",
    "healthcheck.md",
    "$($spec.entry_point)",
    "tests/test_$($spec.plugin_name).py"
)

foreach ($file in $requiredFiles) {
    if (Test-Path "$PluginPath/$file") {
        Write-Host "✓ $file exists" -ForegroundColor Green
    } else {
        Write-Host "✗ $file missing" -ForegroundColor Red
        $validationPassed = $false
    }
}

# 3. Validate input/output schemas
Write-Host "`nValidating schemas..." -ForegroundColor Yellow
if ($spec.input_schema -and $spec.output_schema) {
    # Check that trace_id is in input schema
    if ($spec.input_schema.required -contains "trace_id") {
        Write-Host "✓ Input schema includes trace_id" -ForegroundColor Green
    } else {
        Write-Host "✗ Input schema missing trace_id" -ForegroundColor Red
        $validationPassed = $false
    }
    
    # Check that output schema includes required fields
    $requiredOutputFields = @("status", "trace_id")
    foreach ($field in $requiredOutputFields) {
        if ($spec.output_schema.required -contains $field) {
            Write-Host "✓ Output schema includes $field" -ForegroundColor Green
        } else {
            Write-Host "✗ Output schema missing $field" -ForegroundColor Red
            $validationPassed = $false
        }
    }
} else {
    Write-Host "✗ Schemas not defined" -ForegroundColor Red
    $validationPassed = $false
}

# 4. Run tests
Write-Host "`nRunning tests..." -ForegroundColor Yellow
if ($spec.language -eq "python") {
    try {
        $testResult = pytest "$PluginPath/tests/" -v --tb=short 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✓ All tests passed" -ForegroundColor Green
        } else {
            Write-Host "✗ Tests failed" -ForegroundColor Red
            Write-Host $testResult
            $validationPassed = $false
        }
    } catch {
        Write-Host "✗ Failed to run tests: $_" -ForegroundColor Red
        $validationPassed = $false
    }
}

# 5. Check code coverage
Write-Host "`nChecking code coverage..." -ForegroundColor Yellow
$coverageResult = pytest "$PluginPath/tests/" --cov="$PluginPath" --cov-report=term-missing 2>&1
if ($coverageResult -match "(\d+)%") {
    $coverage = [int]$matches[1]
    if ($coverage -ge 80) {
        Write-Host "✓ Code coverage: $coverage% (>= 80%)" -ForegroundColor Green
    } else {
        Write-Host "✗ Code coverage: $coverage% (< 80%)" -ForegroundColor Red
        $validationPassed = $false
    }
}

# 6. Run linters
Write-Host "`nRunning linters..." -ForegroundColor Yellow
if ($spec.language -eq "python") {
    # Ruff
    $ruffResult = ruff check "$PluginPath/" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ Ruff passed" -ForegroundColor Green
    } else {
        Write-Host "✗ Ruff found issues" -ForegroundColor Red
        Write-Host $ruffResult
        $validationPassed = $false
    }
    
    # MyPy
    $mypyResult = mypy "$PluginPath/$($spec.entry_point)" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ MyPy passed" -ForegroundColor Green
    } else {
        Write-Host "✗ MyPy found issues" -ForegroundColor Red
        Write-Host $mypyResult
        $validationPassed = $false
    }
}

# Final result
Write-Host "`n=== Validation Result ===" -ForegroundColor Cyan
if ($validationPassed) {
    Write-Host "✓ VALIDATION PASSED" -ForegroundColor Green
    Write-Host "Plugin is ready for deployment" -ForegroundColor Green
    exit 0
} else {
    Write-Host "✗ VALIDATION FAILED" -ForegroundColor Red
    Write-Host "Fix the issues above before deploying" -ForegroundColor Red
    exit 1
}
```

### 10.2 Quality Gate Enforcement

```python
# core/quality_gates.py
"""Quality gates for R_PIPELINE"""
from typing import Dict, List
import subprocess
import json

class QualityGate:
    """Base class for quality gates"""
    
    def check(self, plugin_path: str) -> tuple[bool, str]:
        """
        Check if quality gate passes.
        
        Returns:
            (passed, message)
        """
        raise NotImplementedError

class TestCoverageGate(QualityGate):
    """Enforce minimum test coverage"""
    
    def __init__(self, minimum_coverage: int = 80):
        self.minimum_coverage = minimum_coverage
    
    def check(self, plugin_path: str) -> tuple[bool, str]:
        result = subprocess.run(
            ["pytest", f"{plugin_path}/tests/", "--cov", plugin_path, 
             "--cov-report=json"],
            capture_output=True,
            text=True
        )
        
        with open("coverage.json") as f:
            coverage_data = json.load(f)
        
        total_coverage = coverage_data["totals"]["percent_covered"]
        
        if total_coverage >= self.minimum_coverage:
            return (True, f"Coverage: {total_coverage:.1f}%")
        else:
            return (False, f"Coverage {total_coverage:.1f}% < {self.minimum_coverage}%")

class SecurityScanGate(QualityGate):
    """Scan for security issues"""
    
    def check(self, plugin_path: str) -> tuple[bool, str]:
        # Run Bandit security scanner
        result = subprocess.run(
            ["bandit", "-r", plugin_path, "-f", "json"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            return (True, "No security issues found")
        else:
            issues = json.loads(result.stdout)
            return (False, f"Found {len(issues['results'])} security issues")

class ContractComplianceGate(QualityGate):
    """Verify compliance with Operating Contract"""
    
    def check(self, plugin_path: str) -> tuple[bool, str]:
        # Load spec
        with open(f"{plugin_path}/plugin.spec.json") as f:
            spec = json.load(f)
        
        # Check required fields
        required = ["plugin_name", "version", "lifecycle_event", 
                   "input_schema", "output_schema"]
        missing = [f for f in required if f not in spec]
        
        if missing:
            return (False, f"Missing fields: {', '.join(missing)}")
        
        # Check trace_id in schemas
        if "trace_id" not in spec["input_schema"].get("required", []):
            return (False, "Input schema must require trace_id")
        
        if "trace_id" not in spec["output_schema"].get("required", []):
            return (False, "Output schema must require trace_id")
        
        return (True, "Contract compliant")

def run_quality_gates(plugin_path: str) -> bool:
    """
    Run all quality gates and return overall result.
    
    Returns:
        True if all gates pass
    """
    gates = [
        TestCoverageGate(minimum_coverage=80),
        SecurityScanGate(),
        ContractComplianceGate()
    ]
    
    print(f"\n=== Running Quality Gates for {plugin_path} ===\n")
    
    all_passed = True
    for gate in gates:
        gate_name = gate.__class__.__name__
        passed, message = gate.check(plugin_path)
        
        status = "✓" if passed else "✗"
        color = "\033[92m" if passed else "\033[91m"
        print(f"{color}{status} {gate_name}: {message}\033[0m")
        
        if not passed:
            all_passed = False
    
    print(f"\n{'='*50}")
    if all_passed:
        print("\033[92m✓ ALL QUALITY GATES PASSED\033[0m")
    else:
        print("\033[91m✗ SOME QUALITY GATES FAILED\033[0m")
    
    return all_passed
```

---

## 11. Troubleshooting & Rollback

### 11.1 Common Issues and Solutions

**Issue: Plugin times out**

```bash
# Check plugin execution time
grep "duration_seconds" /opt/r_pipeline/logs/plugin_metrics.log | \
  grep "plugin=\"deduplicator\""

# Solution: Increase timeout in plugin.spec.json
{
  "timeout_seconds": 60  # Increase from 30
}

# Regenerate artifacts
.\core\Generate-PluginScaffold.ps1 -SpecFile "plugins/deduplicator/plugin.spec.json" -Force
```

**Issue: Tests fail after refactoring**

```bash
# Run tests with verbose output
pytest plugins/my-plugin/tests/ -vv --tb=long

# Run specific failing test
pytest plugins/my-plugin/tests/test_my_plugin.py::test_specific_case -vv

# Check if test environment is clean
pytest plugins/my-plugin/tests/ --setup-show

# Solution: Fix the code or update the test
# Remember: Tests define behavior, so change code first
```

**Issue: Trace IDs not appearing in logs**

```bash
# Check OpenTelemetry configuration
echo $OTEL_EXPORTER_OTLP_ENDPOINT

# Verify collector is running
systemctl status otel-collector

# Check for traces in Jaeger
curl http://localhost:16686/api/traces?service=r_pipeline

# Solution: Verify tracer is initialized
# In your plugin:
from opentelemetry import trace
tracer = trace.get_tracer(__name__)
# Use tracer.start_as_current_span(...)
```

### 11.2 Rollback Procedures

**Rollback a Plugin Deployment**

```bash
# 1. Disable the plugin
cd plugins/problematic-plugin
vim plugin.spec.json
# Set: "enabled": false

# 2. Regenerate manifest
../../core/Generate-PluginScaffold.ps1 -SpecFile plugin.spec.json -Force

# 3. Commit and push
git add .
git commit -m "Disable problematic-plugin due to timeout issues"
git push

# 4. Verify plugin is disabled
grep "enabled" plugins/problematic-plugin/manifest.json
```

**Rollback Infrastructure Changes**

```bash
# Using Pulumi
cd infrastructure/pulumi

# View previous state
pulumi stack history

# Rollback to specific version
pulumi stack select production
pulumi stack import --file backup-state-20250131.json

# Or: Restore from git
git checkout HEAD~1 infrastructure/
pulumi up

# Run infrastructure tests to verify
pytest infrastructure/tests/ --hosts=production-server
```

**Emergency Rollback (Complete System)**

```bash
# 1. Stop the pipeline
systemctl stop r_pipeline

# 2. Restore from last known good state
git checkout tags/v1.0.5  # Last stable version

# 3. Redeploy infrastructure
cd infrastructure/pulumi
pulumi up --yes

# 4. Restart pipeline
systemctl start r_pipeline

# 5. Monitor logs
tail -f /opt/r_pipeline/logs/pipeline.log

# 6. Check traces in Jaeger
# http://localhost:16686
```

### 11.3 Debugging with Trace IDs

```bash
# Find all operations for a specific trace ID
grep "trace-2025-123" /opt/r_pipeline/logs/*.log

# View trace in Jaeger
curl -s "http://localhost:16686/api/traces/trace-2025-123" | jq

# Find failed operations
curl -s "http://localhost:16686/api/traces?service=r_pipeline&tag=error:true" | \
  jq '.data[].spans[] | select(.status.code == 2) | .operationName'

# Correlate with plugin execution
grep "trace-2025-123" /opt/r_pipeline/logs/plugin_execution.log | \
  jq '. | select(.status == "error")'
```

---

## Appendix: Tool Reference

### Python Toolchain

| Tool | Purpose | Command |
|------|---------|---------|
| **pytest** | Unit testing framework | `pytest tests/ -v` |
| **pytest-cov** | Code coverage | `pytest --cov=plugins --cov-report=html` |
| **pytest-testinfra** | Infrastructure testing | `pytest infrastructure/tests/ --hosts=localhost` |
| **black** | Code formatter | `black .` |
| **isort** | Import sorter | `isort .` |
| **ruff** | Fast linter | `ruff check . --fix` |
| **mypy** | Static type checker | `mypy core/ plugins/` |
| **pylint** | Code analysis | `pylint core/ plugins/` |
| **behave** | BDD testing | `behave features/` |
| **bandit** | Security scanner | `bandit -r plugins/` |

### PowerShell Toolchain

| Tool | Purpose | Command |
|------|---------|---------|
| **PSScriptAnalyzer** | Linter | `Invoke-ScriptAnalyzer -Path . -Recurse` |
| **Pester** | Testing framework | `Invoke-Pester -Path tests/` |
| **PSRule** | Policy validation | `Invoke-PSRule -Path .` |

### Infrastructure Tools

| Tool | Purpose | Command |
|------|---------|---------|
| **Pulumi** | IaC (Python) | `pulumi up` |
| **Terraform** | IaC (HCL) | `terraform apply` |
| **Ansible** | Configuration management | `ansible-playbook playbook.yml` |

### Observability Tools

| Tool | Purpose | URL |
|------|---------|-----|
| **Jaeger** | Trace visualization | http://localhost:16686 |
| **Prometheus** | Metrics collection | http://localhost:9090 |
| **Grafana** | Dashboards | http://localhost:3000 |

### Documentation Tools

| Tool | Purpose | Command |
|------|---------|---------|
| **MkDocs** | Static site generator | `mkdocs serve` |
| **Sphinx** | Python doc generator | `sphinx-build -b html docs/ _build/` |
| **Doxygen** | Code documentation | `doxygen Doxyfile` |

---

## Summary

This Implementation Guide provides the practical methodology for developing R_PIPELINE plugins and infrastructure following TDD, IaC, and DevOps principles. Key takeaways:

1. **Always write tests first** (Red → Green → Refactor)
2. **Infrastructure is code** (version it, test it, deploy it)
3. **Every operation has a Trace ID** (observability is mandatory)
4. **Documentation is generated** (single source of truth)
5. **Quality gates are enforced** (no deployment without validation)
6. **Rollback is always possible** (deterministic, traceable, reversible)

Follow this guide to ensure consistent, high-quality development that aligns with the R_PIPELINE Operating Contract.

---

**Document Version:** 1.0.0  
**Last Updated:** 2025-10-31  
**Next Review:** 2025-11-30
