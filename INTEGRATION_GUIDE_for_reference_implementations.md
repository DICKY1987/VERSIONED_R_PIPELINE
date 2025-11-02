# Integration Guide: Reference Implementations → Production System

## Overview
You've received high-quality reference implementations for:
1. **State Machine** (state_machine.py)
2. **Task Scheduler** (task_scheduler.py)  
3. **Context Broker** (context_broker.py)

This guide shows how to integrate them with your existing system components.

---

## Phase 1: Immediate Integration (Week 1)

### Step 1: Create Core Directory Structure
```bash
# Add these to your existing repo structure
mkdir -p core/{state_machine,scheduler,context}
mkdir -p tests/unit/{state_machine,scheduler,context}
mkdir -p schemas/contracts
```

### Step 2: Copy Reference Implementations
```bash
# Core modules
cp state_machine.py core/state_machine/base.py
cp task_scheduler.py core/scheduler/dag.py
cp context_broker.py core/context/broker.py

# Tests
cp test_state_machine.py tests/unit/state_machine/
cp test_toposort.py tests/unit/scheduler/

# Schemas
cp execution_state_machine.schema.json schemas/contracts/
cp context_broker.schema.json schemas/contracts/
```

### Step 3: Extend State Machine for Pipeline Integration
Create `core/state_machine/pipeline.py`:

```python
"""
Extended state machine with Workflow.docx integration.
Adds: OpenTelemetry, ULID, ledger logging, checkpoints.
"""
from core.state_machine.base import ExecutionStateMachine, IllegalTransition
import ulid
from opentelemetry import trace
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional

class PipelineTaskExecution(ExecutionStateMachine):
    """
    Production state machine for Workflow.docx tasks.
    
    Integrates with:
    - OpenTelemetry (trace_id)
    - ULID generation
    - JSONL ledger (Workflow.docx Step 12)
    - Git checkpoints (Workflow.docx Step 6/7)
    - Retry policy (EXECUTION_STATE_MACHINE_CONTRACT.yaml)
    """
    
    def __init__(
        self,
        task_id: str,
        states: Dict,
        initial_state: str,
        run_id: str,
        max_attempts: int = 3
    ):
        super().__init__(states, initial_state)
        self.task_id = task_id
        self.run_id = run_id
        self.trace_id = str(ulid.new())
        self.attempt = 0
        self.max_attempts = max_attempts
        self.run_path = Path(f".runs/{run_id}")
        
        # Initialize OpenTelemetry tracer
        self.tracer = trace.get_tracer(__name__)
        
    def transition(self, new_state: str, context: Optional[Dict[str, Any]] = None) -> None:
        """
        State transition with full audit trail.
        
        Logs to:
        1. JSONL ledger (.runs/{run_id}/logs/run.jsonl)
        2. OpenTelemetry spans
        3. Console (structured)
        """
        old_state = self.state
        context = context or {}
        
        # Validate transition
        if not self.can_transition(new_state):
            raise IllegalTransition(
                f"Task {self.task_id}: {old_state} -> {new_state} not allowed"
            )
        
        # Execute entry actions
        with self.tracer.start_as_current_span(f"transition_{self.task_id}") as span:
            span.set_attribute("task.id", self.task_id)
            span.set_attribute("transition.from", old_state)
            span.set_attribute("transition.to", new_state)
            span.set_attribute("trace.id", self.trace_id)
            
            if new_state == "RUNNING":
                self._on_enter_running()
            elif new_state == "COMPLETED":
                self._on_enter_completed(context)
            elif new_state == "FAILED":
                self._on_enter_failed(context)
        
        # Perform transition
        self.state = new_state
        
        # Log to ledger
        self._log_transition(old_state, new_state, context)
    
    def _on_enter_running(self):
        """Entry action: Start execution span"""
        print(f"[{self.task_id}] Starting execution (attempt {self.attempt + 1}/{self.max_attempts})")
        self.attempt += 1
    
    def _on_enter_completed(self, context: Dict):
        """Entry action: Create checkpoint, release resources"""
        # Create Git checkpoint (Workflow.docx Step 6/7)
        checkpoint_data = {
            "task_id": self.task_id,
            "run_id": self.run_id,
            "trace_id": self.trace_id,
            "state": "COMPLETED",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "outputs": context.get("outputs", {})
        }
        
        checkpoint_path = self.run_path / "checkpoints" / f"{self.task_id}.json"
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        checkpoint_path.write_text(json.dumps(checkpoint_data, indent=2))
        
        print(f"[{self.task_id}] ✓ Completed. Checkpoint: {checkpoint_path}")
    
    def _on_enter_failed(self, context: Dict):
        """Entry action: Log failure, evaluate retry"""
        error = context.get("error", "Unknown error")
        print(f"[{self.task_id}] ✗ Failed: {error}")
        
        # Check if retry allowed
        if self.attempt < self.max_attempts:
            print(f"[{self.task_id}] Retry {self.attempt}/{self.max_attempts}")
            # Don't auto-retry here - let orchestrator decide
        else:
            print(f"[{self.task_id}] Maximum retries exceeded. Marking as terminal failure.")
    
    def _log_transition(self, old_state: str, new_state: str, context: Dict):
        """Write transition to JSONL ledger"""
        log_entry = {
            "event": "state_transition",
            "task_id": self.task_id,
            "run_id": self.run_id,
            "trace_id": self.trace_id,
            "old_state": old_state,
            "new_state": new_state,
            "attempt": self.attempt,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "context": context
        }
        
        # Append to run.jsonl (Workflow.docx Step 12)
        ledger_path = self.run_path / "logs" / "run.jsonl"
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        
        with ledger_path.open("a") as f:
            f.write(json.dumps(log_entry) + "\n")
    
    def can_retry(self) -> bool:
        """Check if task can be retried"""
        return (
            self.state == "FAILED" and
            self.attempt < self.max_attempts
        )
```

### Step 4: Create Workflow Scheduler
Create `core/scheduler/workflow.py`:

```python
"""
Workflow Scheduler: Maps Workflow.docx 12 steps to task DAG.
Uses task_scheduler.topo_sort for deterministic execution order.
"""
from core.scheduler.dag import topo_sort, CycleError
from core.state_machine.pipeline import PipelineTaskExecution
from typing import List, Dict, Callable
from pathlib import Path
import json

class WorkflowScheduler:
    """
    Orchestrates Workflow.docx 12-step pipeline.
    
    Maps workflow steps → task DAG → deterministic execution.
    """
    
    # Workflow.docx step definitions
    WORKFLOW_STEPS = {
        "step_00_preflight": {
            "tasks": ["task_001_preflight"],
            "checkpoint": "checkpoint(preflight)",
            "parallel": False
        },
        "step_01_run_init": {
            "tasks": ["task_002_run_init"],
            "checkpoint": "checkpoint(run-init)",
            "parallel": False
        },
        "step_02_planning": {
            "tasks": ["task_003_planning"],
            "checkpoint": "checkpoint(plan-complete)",
            "parallel": False
        },
        "step_03_worktrees": {
            "tasks": ["task_004_worktree_a", "task_005_worktree_b"],
            "checkpoint": None,  # No checkpoint until all worktrees ready
            "parallel": True
        },
        "step_04_execute": {
            "tasks": ["task_006_execute_a", "task_007_execute_b"],
            "checkpoint": None,
            "parallel": True
        },
        "step_05_code_gate": {
            "tasks": ["task_008_gate_a", "task_009_gate_b"],
            "checkpoint": None,
            "parallel": True
        },
        "step_06_consume": {
            "tasks": ["task_010_consume_a", "task_011_consume_b"],
            "checkpoint": "checkpoint(codegate)",
            "parallel": True
        },
        "step_07_validate": {
            "tasks": ["task_012_validate_a", "task_013_validate_b"],
            "checkpoint": "checkpoint(validate-pass)",
            "parallel": True
        },
        "step_08_merge_prep": {
            "tasks": ["task_014_merge_prep"],
            "checkpoint": None,
            "parallel": False
        },
        "step_09_merge": {
            "tasks": ["task_015_merge"],
            "checkpoint": "checkpoint(integration-complete)",
            "parallel": False
        },
        "step_10_pr_ci": {
            "tasks": ["task_016_pr_ci"],
            "checkpoint": None,
            "parallel": False
        },
        "step_11_ship": {
            "tasks": ["task_017_ship"],
            "checkpoint": "checkpoint(ship-complete)",
            "parallel": False
        },
        "step_12_archive": {
            "tasks": ["task_018_archive"],
            "checkpoint": None,
            "parallel": False
        }
    }
    
    def __init__(self, run_id: str, task_implementations: Dict[str, Callable]):
        self.run_id = run_id
        self.task_implementations = task_implementations
        self.tasks = self._build_task_graph()
        
    def _build_task_graph(self) -> List[dict]:
        """Build task DAG from workflow step definitions"""
        tasks = []
        prev_step_tasks = []
        
        for step_id, step_config in self.WORKFLOW_STEPS.items():
            step_tasks = step_config["tasks"]
            
            for task_id in step_tasks:
                tasks.append({
                    "id": task_id,
                    "dependencies": prev_step_tasks,
                    "priority": len(tasks),  # Sequential priority by default
                    "parallel_group": step_id if step_config["parallel"] else None,
                    "checkpoint": step_config.get("checkpoint")
                })
            
            prev_step_tasks = step_tasks
        
        return tasks
    
    def execute(self) -> bool:
        """
        Execute full workflow with deterministic ordering.
        Returns True if all tasks completed successfully.
        """
        # Get deterministic execution order
        try:
            ordered_tasks = topo_sort(self.tasks)
        except CycleError as e:
            print(f"✗ Cycle detected in task graph: {e}")
            return False
        
        # Group by parallel groups (waves)
        waves = self._group_into_waves(ordered_tasks)
        
        print(f"Executing {len(ordered_tasks)} tasks in {len(waves)} waves...")
        
        # Execute wave by wave
        for wave_num, wave_tasks in enumerate(waves, 1):
            print(f"\n=== Wave {wave_num}/{len(waves)} ===")
            print(f"Tasks: {[t['id'] for t in wave_tasks]}")
            
            success = self._execute_wave(wave_tasks)
            if not success:
                print(f"✗ Wave {wave_num} failed. Aborting workflow.")
                return False
        
        print(f"\n✓ All {len(ordered_tasks)} tasks completed successfully!")
        return True
    
    def _execute_wave(self, wave_tasks: List[dict]) -> bool:
        """Execute a wave of tasks (may be parallel)"""
        if len(wave_tasks) == 1:
            # Sequential execution
            return self._execute_task(wave_tasks[0])
        else:
            # Parallel execution (simplified - would use threading/multiprocessing)
            results = []
            for task in wave_tasks:
                result = self._execute_task(task)
                results.append(result)
            return all(results)
    
    def _execute_task(self, task: dict) -> bool:
        """Execute single task with state machine"""
        task_id = task["id"]
        
        # Load state machine config
        states = self._load_state_config()
        
        # Create task execution with state machine
        exec_sm = PipelineTaskExecution(
            task_id=task_id,
            states=states,
            initial_state="PENDING",
            run_id=self.run_id,
            max_attempts=3
        )
        
        # Transition to RUNNING
        exec_sm.transition("RUNNING")
        
        try:
            # Get task implementation
            impl_func = self.task_implementations.get(task_id)
            if not impl_func:
                raise ValueError(f"No implementation for task {task_id}")
            
            # Execute task
            result = impl_func(run_id=self.run_id, task_id=task_id)
            
            # Transition to COMPLETED
            exec_sm.transition("COMPLETED", context={"outputs": result})
            
            # Create checkpoint if configured
            if task.get("checkpoint"):
                self._create_git_checkpoint(task["checkpoint"], self.run_id)
            
            return True
            
        except Exception as e:
            # Transition to FAILED
            exec_sm.transition("FAILED", context={"error": str(e)})
            
            # Check if retry is allowed
            if exec_sm.can_retry():
                print(f"[{task_id}] Retrying...")
                return self._execute_task(task)  # Retry
            else:
                return False
    
    def _group_into_waves(self, ordered_tasks: List[dict]) -> List[List[dict]]:
        """Group tasks into execution waves (parallel groups)"""
        waves = []
        current_wave = []
        current_group = None
        
        for task in ordered_tasks:
            parallel_group = task.get("parallel_group")
            
            if parallel_group == current_group:
                # Same parallel group - add to current wave
                current_wave.append(task)
            else:
                # New group - start new wave
                if current_wave:
                    waves.append(current_wave)
                current_wave = [task]
                current_group = parallel_group
        
        if current_wave:
            waves.append(current_wave)
        
        return waves
    
    def _load_state_config(self) -> Dict:
        """Load state machine configuration"""
        return {
            "PENDING": {
                "description": "Task defined but not started",
                "allowed_transitions": ["RUNNING", "SKIPPED", "CANCELLED"]
            },
            "RUNNING": {
                "description": "Task executing",
                "allowed_transitions": ["COMPLETED", "FAILED", "CANCELLED"]
            },
            "COMPLETED": {
                "description": "Task finished successfully",
                "allowed_transitions": []
            },
            "FAILED": {
                "description": "Task failed",
                "allowed_transitions": ["PENDING"]  # Allow retry
            },
            "SKIPPED": {
                "description": "Task skipped",
                "allowed_transitions": []
            },
            "CANCELLED": {
                "description": "Task cancelled",
                "allowed_transitions": []
            }
        }
    
    def _create_git_checkpoint(self, checkpoint_name: str, run_id: str):
        """Create Git checkpoint (Workflow.docx checkpoints)"""
        import subprocess
        commit_msg = f"{checkpoint_name}: {run_id}"
        subprocess.run(["git", "commit", "--allow-empty", "-m", commit_msg], check=True)
        print(f"  Checkpoint: {checkpoint_name}")
```

---

## Phase 2: Tool Integration (Week 2)

### Step 5: Integrate Context Broker with LLM Tools
Create `core/context/dispatcher.py`:

```python
"""
LLM Tool Dispatcher with Context Broker integration.
Implements Blueprint_ACMS.docx Section III.
"""
from pathlib import Path
import subprocess
import json
from typing import List, Dict, Optional

class LLMToolDispatcher:
    """
    Dispatches tasks to Aider/Claude Code with filtered context.
    
    Uses context_broker.py to:
    1. Filter files by relevance
    2. Enforce token budgets
    3. Generate stable manifest
    """
    
    def __init__(self, context_broker_script: str = "tools/context_broker.py"):
        self.broker_script = context_broker_script
    
    def dispatch_to_aider(
        self,
        task_description: str,
        target_files: List[str],
        keywords: List[str],
        max_tokens: int = 80000
    ) -> subprocess.CompletedProcess:
        """
        Call Aider with context-filtered files.
        
        Args:
            task_description: Natural language task
            target_files: Explicitly mentioned files
            keywords: Search terms for relevance
            max_tokens: Aider context budget
        """
        # Get filtered context
        manifest = self._get_context_manifest(
            target_files=target_files,
            keywords=keywords,
            max_tokens=max_tokens,
            task_type="edit"
        )
        
        # Build Aider command
        aider_cmd = [
            "aider",
            "--model", "deepseek",
            "--message", task_description
        ]
        
        # Add filtered files
        for file_info in manifest["files"]:
            aider_cmd.extend(["--read", file_info["path"]])
        
        print(f"Context: {manifest['total_files']} files, ~{manifest['total_tokens']} tokens")
        
        # Execute Aider
        result = subprocess.run(
            aider_cmd,
            capture_output=True,
            text=True,
            timeout=600
        )
        
        return result
    
    def dispatch_to_claude_code(
        self,
        task_description: str,
        target_files: List[str],
        keywords: List[str],
        max_tokens: int = 150000
    ) -> subprocess.CompletedProcess:
        """Call Claude Code with filtered context"""
        manifest = self._get_context_manifest(
            target_files=target_files,
            keywords=keywords,
            max_tokens=max_tokens,
            task_type="plan"
        )
        
        # Build Claude Code command
        claude_cmd = ["claude-code", "plan", "--no-tui"]
        
        for file_info in manifest["files"]:
            claude_cmd.extend(["--file", file_info["path"]])
        
        claude_cmd.append(task_description)
        
        print(f"Context: {manifest['total_files']} files, ~{manifest['total_tokens']} tokens")
        
        result = subprocess.run(
            claude_cmd,
            capture_output=True,
            text=True,
            timeout=300
        )
        
        return result
    
    def _get_context_manifest(
        self,
        target_files: List[str],
        keywords: List[str],
        max_tokens: int,
        task_type: str
    ) -> Dict:
        """Call context_broker.py and return manifest"""
        manifest_path = f".runs/context_{task_type}.json"
        
        cmd = [
            "python",
            self.broker_script,
            "--root", ".",
            "--out", manifest_path,
            "--task-type", task_type,
            "--keywords", *keywords
        ]
        
        for target in target_files:
            cmd.extend(["--target", target])
        
        subprocess.run(cmd, check=True)
        
        with open(manifest_path) as f:
            return json.load(f)
```

---

## Phase 3: Testing Integration (Week 3)

### Step 6: Create Integration Tests
Create `tests/integration/test_workflow_execution.py`:

```python
"""
Integration test: Full workflow execution with state machine + scheduler.
"""
import pytest
from pathlib import Path
from core.scheduler.workflow import WorkflowScheduler
import ulid

def test_minimal_workflow_execution(tmp_path):
    """Test 3-step minimal workflow"""
    run_id = str(ulid.new())
    
    # Define minimal task implementations
    def task_preflight(**kwargs):
        print("Preflight check")
        return {"status": "ok"}
    
    def task_init(**kwargs):
        print("Init run")
        return {"run_id": kwargs["run_id"]}
    
    def task_planning(**kwargs):
        print("Generate plan")
        return {"plan": "test_plan.yaml"}
    
    implementations = {
        "task_001_preflight": task_preflight,
        "task_002_run_init": task_init,
        "task_003_planning": task_planning
    }
    
    # Create scheduler with only first 3 steps
    scheduler = WorkflowScheduler(run_id, implementations)
    scheduler.tasks = scheduler.tasks[:3]  # Only preflight, init, planning
    
    # Execute workflow
    success = scheduler.execute()
    
    assert success == True
    
    # Verify ledger exists
    ledger_path = Path(f".runs/{run_id}/logs/run.jsonl")
    assert ledger_path.exists()
    
    # Verify checkpoints created
    checkpoint_path = Path(f".runs/{run_id}/checkpoints")
    assert checkpoint_path.exists()
    assert len(list(checkpoint_path.glob("*.json"))) >= 3


def test_parallel_execution():
    """Test parallel task execution"""
    # TODO: Implement after parallel execution added
    pass


def test_retry_on_failure():
    """Test retry policy when task fails"""
    # TODO: Implement
    pass
```

---

## Validation Checklist

Before considering integration complete:

- [ ] State machine integrated with OpenTelemetry
- [ ] Task scheduler generates deterministic execution order
- [ ] Workflow scheduler maps 12 steps to DAG
- [ ] Context broker filters files for Aider/Claude Code
- [ ] JSONL ledger written for all state transitions
- [ ] Git checkpoints created at required steps
- [ ] Tests pass: `pytest tests/unit tests/integration -v`
- [ ] Schemas validate: `python -m jsonschema -i execution_state_machine.example.json execution_state_machine.schema.json`

---

## Next Steps After Integration

1. **Add observability dashboard** (Jaeger UI for trace visualization)
2. **Add retry policy configuration** (externalize from hardcoded)
3. **Add resource limits** (CPU, memory quotas per task)
4. **Add context broker caching** (avoid recomputing scores)
5. **Add parallel execution** (threading/multiprocessing for worktrees)

---

## Questions?

Refer to:
- Workflow.docx for 12-step pipeline details
- EXECUTION_STATE_MACHINE_CONTRACT.yaml for state machine spec
- CONTEXT_BROKER_CONTRACT.yaml for context filtering spec
- Blueprint_ACMS.docx for LLM tool integration patterns
