# Process Toolkit (Python) – Draft v0

> Python 3.11 equivalents of the PowerShell **generator** and **validator** that enforce the Operating Contract. Drop these files in your repo and they’ll work side‑by‑side with the PS versions.

---

## Repo layout & deps

```
/scripts/
  generate_plugin_scaffold.py
  validate_plugin.py
  requirements.txt
/plugins/
  path-classifier/
    plugin.spec.json          # human-authored
    manifest.json             # generated
    policy_snapshot.json      # generated
    ledger_contract.json      # generated
    handler.py                # generated stub; edit only AUTO region
    README_PLUGIN.md          # generated
    healthcheck.md            # generated
/core/
  OPERATING_CONTRACT.md      # already in canvas
```

**requirements.txt**
```
PyYAML==6.0.2
```

Create a venv (optional):
```
python -m venv .venv
. .venv/Scripts/activate  # Windows
pip install -r scripts/requirements.txt
```

---

## scripts/generate_plugin_scaffold.py

```python
#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path
from datetime import datetime, timezone
import yaml

CONTRACT_DEFAULT = Path('./core/OPERATING_CONTRACT.md')

REQ_FILES = [
    'manifest.json',
    'policy_snapshot.json',
    'ledger_contract.json',
    'handler.py',
    'README_PLUGIN.md',
    'healthcheck.md',
]

YAML_BLOCKS = {
    'events': r"```yaml\s*lifecycle_events:(.*?)```",
    'actions': r"```yaml\s*allowed_actions_contract:(.*?)```",
}

FRONT_MATTER_RE = re.compile(r"^---\n(.*?)\n---", re.S)

HANDLER_TEMPLATE = '''
"""
Plugin handler for {name} ({version}).
Only edit code between BEGIN/END AUTO SECTION markers.
Contract version at generation: {contract_version}
"""
from __future__ import annotations
from typing import Any, Dict, List

# BEGIN AUTO SECTION

def handle(event: dict) -> List[Dict[str, Any]]:
    """Return a list of proposals: {{"action": <str>, "payload": <dict>}}.
    Event example for FileDetected:
        {{"name": "FileDetected", "inputs": {{"path": "README.md", "size": 12, "sha256": "deadbeef", "mime": "text/markdown"}}}}
    """
    if event.get('name') == 'FileDetected':
        inp = event.get('inputs', {})
        path = inp.get('path', '')
        mime = inp.get('mime')
        proposals = []
        if path.startswith('src/'):
            proposals.append({
                'action': 'propose_move',
                'payload': {'from': path, 'to': path, 'rationale': 'already under src'}
            })
        elif mime == 'text/x-python':
            filename = Path(path).name
            proposals.append({
                'action': 'propose_move',
                'payload': {'from': path, 'to': f'src/{filename}', 'rationale': 'python source -> src'}
            })
        else:
            proposals.append({
                'action': 'propose_quarantine',
                'payload': {'path': path, 'reason_code': 'unknown_type', 'note': 'default quarantine'}
            })
        return proposals
    return []

# END AUTO SECTION
'''

def read_text(path: Path) -> str:
    return path.read_text(encoding='utf-8')

def extract_yaml_block(md: str, which: str) -> dict:
    m = re.search(YAML_BLOCKS[which], md, re.S)
    if not m:
        raise ValueError(f"Cannot find YAML block: {which}")
    block = m.group(1)
    # reintroduce the key so safe_load gets a mapping
    key = 'lifecycle_events' if which == 'events' else 'allowed_actions_contract'
    y = yaml.safe_load(f"{key}:{block}")
    return y

def parse_front_matter(md: str) -> dict:
    m = FRONT_MATTER_RE.search(md)
    if not m:
        return {}
    return yaml.safe_load(m.group(1)) or {}

def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()

def kebab_ok(name: str) -> bool:
    return re.fullmatch(r"[a-z0-9-]+", name) is not None

def semver_ok(ver: str) -> bool:
    return re.fullmatch(r"\d+\.\d+\.\d+", ver) is not None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-s', '--spec', required=True, help='Path to plugin.spec.json')
    ap.add_argument('-c', '--contract', default=str(CONTRACT_DEFAULT), help='Path to OPERATING_CONTRACT.md')
    args = ap.parse_args()

    spec_path = Path(args.spec)
    plug_dir = spec_path.parent
    plug_dir.mkdir(parents=True, exist_ok=True)

    spec = json.loads(read_text(spec_path))
    for k in ('name','version','handles_event'):
        if k not in spec:
            sys.exit(f"Spec missing required field: {k}")
    if not kebab_ok(spec['name']):
        sys.exit('spec.name must be kebab-case [a-z0-9-]+')
    if not semver_ok(spec['version']):
        sys.exit('spec.version must be SemVer X.Y.Z')

    contract_md = read_text(Path(args.contract))
    fm = parse_front_matter(contract_md)
    contract_version = fm.get('contract_version', '0.0.0')

    events = extract_yaml_block(contract_md, 'events')['lifecycle_events']
    allowed_events = [e['name'] for e in events]
    if spec['handles_event'] not in allowed_events:
        sys.exit(f"handles_event '{spec['handles_event']}' not allowed by contract")

    actions = extract_yaml_block(contract_md, 'actions')['allowed_actions_contract']
    allowed_action_names = list(actions.keys())

    # manifest.json
    manifest = {
        'name': spec['name'],
        'version': spec['version'],
        'handles_event': spec['handles_event'],
        'generated_at': iso_now(),
        'contract_version': str(contract_version),
    }
    (plug_dir / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')

    # policy_snapshot.json
    policy_snapshot = {
        'policy': spec.get('policy', {}),
        'contract_allowed_actions': allowed_action_names,
        'contract_allowed_events': allowed_events,
    }
    (plug_dir / 'policy_snapshot.json').write_text(json.dumps(policy_snapshot, indent=2), encoding='utf-8')

    # ledger_contract.json (minimal)
    ledger_contract = {
        'required': ['ulid','ts','event','policy_version','inputs','actions','status']
    }
    (plug_dir / 'ledger_contract.json').write_text(json.dumps(ledger_contract, indent=2), encoding='utf-8')

    # handler.py
    handler_src = HANDLER_TEMPLATE.format(
        name=spec['name'], version=spec['version'], contract_version=contract_version
    )
    (plug_dir / 'handler.py').write_text(handler_src, encoding='utf-8')

    # README_PLUGIN.md
    readme = f"""
# Plugin: {spec['name']}

*Handles*: `{spec['handles_event']}`  
*Version*: `{spec['version']}`

## Development
- Edit only between **BEGIN AUTO SECTION** and **END AUTO SECTION** in `handler.py`.
- Run `python scripts/validate_plugin.py --path {plug_dir.as_posix()}` before committing.

## Inputs\n{''.join(f'- {i}\n' for i in spec.get('inputs', []))}
## Outputs\n{''.join(f'- {o}\n' for o in spec.get('outputs', []))}
"""
    (plug_dir / 'README_PLUGIN.md').write_text(readme, encoding='utf-8')

    # healthcheck.md
    hc = f"""
# Healthcheck for {spec['name']}

- Validate contract compatibility
- Dry-run with sample event payload

```python
from importlib import util
import json
p = '{(plug_dir / 'handler.py').as_posix()}'
spec = util.spec_from_file_location('{spec['name']}_handler', p)
mod = util.module_from_spec(spec)
spec.loader.exec_module(mod)
print(json.dumps(mod.handle({{"name":"{spec['handles_event']}","inputs":{{"path":"README.md","size":12,"sha256":"deadbeef","mime":"text/markdown"}}}}), indent=2))
```
"""
    (plug_dir / 'healthcheck.md').write_text(hc, encoding='utf-8')

    print(f"Scaffold generated for plugin '{spec['name']}' at '{plug_dir}'")

if __name__ == '__main__':
    main()
```

---

## scripts/validate_plugin.py

```python
#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path
from importlib import util
import yaml

CONTRACT_DEFAULT = Path('./core/OPERATING_CONTRACT.md')
REQ = ['plugin.spec.json','manifest.json','policy_snapshot.json','ledger_contract.json','handler.py','README_PLUGIN.md','healthcheck.md']

YAML_BLOCKS = {
    'events': r"```yaml\s*lifecycle_events:(.*?)```",
    'actions': r"```yaml\s*allowed_actions_contract:(.*?)```",
}

DANGEROUS_PATTERNS = [
    r"^\s*import\s+subprocess",
    r"os\.system\(",
    r"Popen\(",
    r"^\s*import\s+requests",
    r"^\s*import\s+urllib",
    r"^\s*import\s+http\.",
    r"^\s*import\s+socket",
    r"curl\s",
    r"wget\s",
    r"git\s",
]

FRONT_MATTER_RE = re.compile(r"^---\n(.*?)\n---", re.S)


def read_text(p: Path) -> str:
    return p.read_text(encoding='utf-8')

def extract_yaml_block(md: str, which: str) -> dict:
    m = re.search(YAML_BLOCKS[which], md, re.S)
    if not m:
        raise SystemExit(f"Cannot find YAML block: {which}")
    block = m.group(1)
    key = 'lifecycle_events' if which == 'events' else 'allowed_actions_contract'
    return yaml.safe_load(f"{key}:{block}")

def parse_front_matter(md: str) -> dict:
    m = FRONT_MATTER_RE.search(md)
    return yaml.safe_load(m.group(1)) if m else {}

def kebab_ok(name: str) -> bool:
    return re.fullmatch(r"[a-z0-9-]+", name) is not None

def semver_ok(ver: str) -> bool:
    return re.fullmatch(r"\d+\.\d+\.\d+", ver) is not None

def static_check_handler(code: str) -> list[str]:
    errs = []
    if 'BEGIN AUTO SECTION' not in code or 'END AUTO SECTION' not in code:
        errs.append('handler.py must contain AUTO region markers')
    for pat in DANGEROUS_PATTERNS:
        if re.search(pat, code, re.I|re.M):
            errs.append(f'Forbidden pattern found: {pat}')
    return errs

def import_handler(handler_path: Path, mod_name: str):
    spec = util.spec_from_file_location(mod_name, handler_path.as_posix())
    mod = util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-p','--path', required=True, help='Path to plugin folder')
    ap.add_argument('-c','--contract', default=str(CONTRACT_DEFAULT), help='Path to OPERATING_CONTRACT.md')
    args = ap.parse_args()

    root = Path(args.path)
    missing = [f for f in REQ if not (root / f).exists()]
    if missing:
        sys.exit('Missing files: ' + ', '.join(missing))

    spec = json.loads(read_text(root / 'plugin.spec.json'))
    for k in ('name','version','handles_event'):
        if k not in spec:
            sys.exit(f"Spec missing required field: {k}")
    if not kebab_ok(spec['name']):
        sys.exit('spec.name must be kebab-case [a-z0-9-]+')
    if not semver_ok(spec['version']):
        sys.exit('spec.version must be SemVer X.Y.Z')

    contract_md = read_text(Path(args.contract))
    events = extract_yaml_block(contract_md, 'events')['lifecycle_events']
    allowed_events = [e['name'] for e in events]
    actions = extract_yaml_block(contract_md, 'actions')['allowed_actions_contract']
    allowed_action_names = list(actions.keys())

    if spec['handles_event'] not in allowed_events:
        sys.exit(f"handles_event '{spec['handles_event']}' not allowed by contract")

    code = read_text(root / 'handler.py')
    errs = static_check_handler(code)

    # Smoke: import and call handle()
    try:
        mod = import_handler(root / 'handler.py', f"handler_{spec['name']}")
        sample_evt = {'name': spec['handles_event'], 'inputs': {'path': '__test__', 'size': 1, 'sha256': 'deadbeef', 'mime': 'text/plain'}}
        proposals = mod.handle(sample_evt)
        if proposals is None:
            proposals = []
        if not isinstance(proposals, list):
            errs.append('handle() must return a list')
        else:
            for p in proposals:
                if not isinstance(p, dict):
                    errs.append('proposal items must be dicts')
                    break
                act = p.get('action')
                if act not in allowed_action_names:
                    errs.append(f"Proposal contains disallowed action: {act}")
                if 'payload' not in p or not isinstance(p['payload'], dict):
                    errs.append('Each proposal must include dict payload')
    except Exception as ex:
        errs.append(f'Handler execution failed: {ex!r}')

    if errs:
        for e in errs:
            print(f"ERROR: {e}")
        sys.exit(1)
    print(f"Validation passed for plugin at {root}")

if __name__ == '__main__':
    main()
```

---

## Example `/plugins/path-classifier/plugin.spec.json`

```json
{
  "name": "path-classifier",
  "version": "0.1.0",
  "handles_event": "FileDetected",
  "inputs": ["path","size","sha256","mtime","mime","shebang"],
  "outputs": ["propose_move","propose_quarantine","propose_dedupe"],
  "policy": {
    "rules": [
      { "if_path_match": "^src/.*", "action": "propose_move", "to": "${path}", "why": "already-src" },
      { "if_mime": "text/x-python", "action": "propose_move", "to": "src/${filename}", "why": "py-to-src" },
      { "else": true, "action": "propose_quarantine", "reason_code": "unknown_type" }
    ]
  }
}
```

---

## CLI usage

```
# 1) Generate scaffold
python scripts/generate_plugin_scaffold.py --spec plugins/path-classifier/plugin.spec.json

# 2) Validate
python scripts/validate_plugin.py --path plugins/path-classifier
```

---

## Optional CI snippet (Python path)

```yaml
- name: Validate plugins (Python path)
  run: |
    python -m pip install -r scripts/requirements.txt
    python scripts/validate_plugin.py --path plugins/path-classifier
    repo-caretaker plan --report out/report.json
```

