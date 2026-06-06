# SmartDev Agent — Project Map

*Generated: 2026-06-06T13:20:23Z*

## Overview

- Files: 85
- Artifacts: 1150
- Relations: 259
- Languages: ['python', 'yaml', 'markdown', 'json', 'toml', 'unknown']

## Most Imported Internal Modules

| Module | Dependents | Risk |
|--------|-----------|------|
| `smartdev.models` | 28 | R2 |
| `smartdev.skills.base` | 24 | R2 |
| `pytest` | 14 | R2 |
| `smartdev.context.project_index` | 10 | R2 |
| `smartdev.context.index_store` | 9 | R2 |
| `smartdev.detectors.tech_stack` | 4 | R1 |
| `smartdev.detectors.docs_status` | 4 | R1 |
| `smartdev.core.reporter` | 3 | R1 |
| `smartdev.core.risk` | 3 | R1 |
| `smartdev.detectors.entrypoints` | 3 | R1 |

## External Dependencies

| Package | Used By |
|---------|---------|
| `pathlib` | 45 files |
| `__future__` | 31 files |
| `dataclasses` | 17 files |
| `json` | 12 files |
| `re` | 4 files |
| `time` | 3 files |
| `enum` | 3 files |
| `sys` | 2 files |
| `subprocess` | 2 files |
| `datetime` | 2 files |

## Suggested Validation Focus

1. Core module `smartdev.models` has 28 dependents — verify changes carefully
2. Run full test suite: `python -m pytest tests/ -q`
