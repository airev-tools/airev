# airev Architecture Guide

This document defines the architecture, design patterns, and implementation standards for `airev`. Every code change must conform to these principles. Read this fully before writing any code.

---

## 1. Project Identity

**airev** is a high-performance, multi-language static analysis engine purpose-built to detect defects characteristic of AI-generated code: hallucinated APIs, phantom imports, deprecated API usage, hardcoded secrets, inconsistent error handling, and copy-paste drift.

- **Build language:** Python 3.12+
- **Scan targets:** Python, JavaScript, TypeScript
- **Distribution:** Native binary (Nuitka AOT compilation), Docker container, `pip install`
- **Interfaces:** CLI, GitHub Action, SARIF output
- **Design philosophy:** Zero-config by default. Auto-detect languages. Single command: `airev scan .`

---

## 2. Architecture Overview

```
                    ┌─────────────────────────────────┐
                    │         INTERFACES               │
                    │  CLI  │  GitHub Action  │  SARIF  │
                    └───────────────┬──────────────────┘
                                    │
                    ┌───────────────▼──────────────────┐
                    │         ORCHESTRATOR              │
                    │  File discovery → Language detect  │
                    │  → Parallel dispatch (loky)       │
                    │  → Collect diagnostics            │
                    └───────────────┬──────────────────┘
                                    │
          ┌─────────────────────────┼─────────────────────────┐
          │                         │                         │
   ┌──────▼──────┐          ┌──────▼──────┐          ┌──────▼──────┐
   │   PARSERS    │          │    RULES     │          │  HEURISTICS  │
   │ Tree-sitter  │          │ Pure funcs   │          │ Winnowing    │
   │ CST → UAST   │          │ Dict dispatch│          │ MinHash      │
   │ SoA Arena    │          │ → Findings   │          │ datasketch   │
   └──────────────┘          └──────────────┘          └──────────────┘
```

### Pipeline (per file)

1. **Read** — Load source bytes from disk
2. **Parse** — Tree-sitter produces error-tolerant Concrete Syntax Tree (CST)
3. **Lower** — Language adapter maps CST → UAST stored in numpy SoA arena
4. **Enrich** — Semantic builder extracts import metadata and bindings into `LintContext`
5. **Evaluate** — Single-pass linear scan over arena with dictionary jump table dispatch
6. **Collect** — Findings aggregated, deduplicated, sorted by severity
7. **Report** — Formatted as terminal output, JSON, or SARIF

### Parallelization (multi-file)

- **loky** process pool distributes file batches across CPU cores
- **Task chunking** — workers process ~50 files per batch, return all diagnostics at once
- **Zero-copy IPC** via `multiprocessing.shared_memory` + numpy for large arenas (Phase 2)
- Diagnostic results returned as lightweight dicts, not serialized AST objects

---

## 3. Core Design Principles

### 3.1 Data-Oriented Design Over Object-Oriented Design

airev prioritizes cache-friendly memory layouts and data-oriented patterns over traditional OOP. This is the single most important performance decision.

**Use Structure of Arrays (SoA), not Array of Structures (AoS):**

```python
# ❌ WRONG — Array of Structures. Each node is a heap-allocated object.
# Traversing a list of these causes CPU cache thrashing.
nodes = [UastNode(...), UastNode(...), UastNode(...)]

# ✅ CORRECT — Structure of Arrays. Parallel numpy arrays with contiguous memory.
# Linear traversal hits L1 cache perfectly.
class UastArena:
    node_types: np.ndarray      # int32, contiguous
    start_bytes: np.ndarray     # int32, contiguous
    end_bytes: np.ndarray       # int32, contiguous
    parent_indices: np.ndarray  # int32, contiguous
```

A "node" is an integer index, not an object. Properties are retrieved by querying parallel arrays at that index. This gives ~10x traversal speedup over object-based trees.

### 3.2 Slotted Frozen Dataclasses for Non-Arena Data

For data structures that DON'T live in the numpy arena (findings, config, etc.), use `@dataclass(slots=True, frozen=True)`:

```python
from dataclasses import dataclass

# ✅ CORRECT — slots=True eliminates __dict__ (63% memory reduction)
#              frozen=True provides immutability guarantees
@dataclass(slots=True, frozen=True)
class Finding:
    rule_id: str
    message: str
    severity: Severity
    file_path: str
    line: int
    col: int
    end_line: int
    end_col: int
    suggestion: str | None = None
    fix: CodeAction | None = None
    confidence: Confidence = Confidence.HIGH
```

**NEVER use plain `@dataclass` or `@dataclass(frozen=True)` without `slots=True`.**

### 3.3 Dictionary Jump Tables for Dispatch

**NEVER use match/case, if-elif chains, or `singledispatch` for node routing.** Dictionary dispatch is 5.2x faster than match/case in CPython.

```python
# ❌ WRONG — O(N) linear branching, slow
match node_type:
    case NodeType.FUNCTION: handle_function(...)
    case NodeType.IMPORT: handle_import(...)
    case NodeType.CALL: handle_call(...)

# ❌ WRONG — singledispatch adds ~400ns overhead per call
@singledispatch
def evaluate(node): ...

# ✅ CORRECT — O(1) integer hash dispatch via dict
DISPATCH_TABLE: dict[int, Callable] = {
    NodeType.FUNCTION: evaluate_function,
    NodeType.IMPORT: evaluate_import,
    NodeType.CALL: evaluate_call,
}
NO_OP = lambda arena, idx, ctx: []

def linear_scan(arena: UastArena, ctx: LintContext) -> list[Finding]:
    findings: list[Finding] = []
    for idx in range(arena.count):
        evaluator = DISPATCH_TABLE.get(arena.node_types[idx], NO_OP)
        findings.extend(evaluator(arena, idx, ctx))
    return findings
```

Integer hashing in CPython is effectively a no-op (zero computation). This is the fastest dispatch mechanism available in Python.

### 3.4 Pure Functions Everywhere

Every rule, heuristic, and transformer must be a **pure function** with no side effects.

```python
# ✅ CORRECT — Pure function. Takes arena + index, returns findings. No mutation.
def check_hallucinated_api(arena: UastArena, idx: int, ctx: LintContext) -> list[Finding]:
    call_name = arena.get_string(arena.name_indices[idx])
    if not ctx.resolver.resolve_call(call_name):
        return [Finding(rule_id="hallucinated-api", ...)]
    return []

# ❌ WRONG — Mutates external state
def check_hallucinated_api(arena, idx, ctx):
    if not ctx.resolver.resolve_call(...):
        global_findings.append(...)  # Side effect!
```

### 3.5 Core/Interface Decoupling

The `airev_core` package knows NOTHING about:
- File systems (receives `bytes`, not file paths)
- Terminal output (returns `Finding` objects, never prints)
- CLI arguments, GitHub Actions, environment variables

The `interfaces/` layer handles all I/O and passes data into the pure core.

---

## 4. Project Structure

```
airev/
├── airev_core/                     # Pure analysis engine — no I/O
│   ├── __init__.py
│   │
│   ├── parsers/                    # Language adapters: CST → UAST Arena
│   │   ├── __init__.py
│   │   ├── registry.py             # Auto-detect language from extension, route to parser
│   │   ├── python_parser.py        # Tree-sitter Python → UastArena population
│   │   └── typescript_parser.py    # Tree-sitter JS/TS → UastArena population
│   │
│   ├── arena/                      # Structure of Arrays UAST storage
│   │   ├── __init__.py
│   │   ├── uast_arena.py           # NumpyUASTArena: parallel numpy arrays + bump allocator
│   │   ├── node_types.py           # Integer constants for all UAST node types
│   │   └── string_table.py         # Interned string storage for identifiers/names
│   │
│   ├── semantics/                  # Semantic enrichment layer
│   │   ├── __init__.py
│   │   ├── context.py              # LintContext: bundles arena + resolved metadata for rules
│   │   └── resolver.py             # Import/dependency resolution
│   │                               #   Python: Pyright-style sys.path + venv + typeshed
│   │                               #   JS/TS: node_modules + package.json exports
│   │
│   ├── rules/                      # Detection rules — all pure functions
│   │   ├── __init__.py
│   │   ├── registry.py             # Rule registry + dispatch table builder
│   │   ├── common/                 # Language-agnostic rules
│   │   │   ├── __init__.py
│   │   │   ├── hallucinated_api.py
│   │   │   ├── phantom_import.py
│   │   │   ├── deprecated_api.py
│   │   │   ├── hardcoded_secrets.py
│   │   │   ├── inconsistent_errors.py
│   │   │   └── copy_paste_drift.py
│   │   └── language_specific/
│   │       ├── python/
│   │       │   └── __init__.py
│   │       └── typescript/
│   │           └── __init__.py
│   │
│   ├── heuristics/                 # Mathematical algorithms — pure functions, numpy-vectorized
│   │   ├── __init__.py
│   │   ├── winnowing.py            # Structural fingerprinting via numpy stride tricks
│   │   ├── minhash.py              # MinHash signatures via datasketch (numpy backend)
│   │   └── patterns.py             # Regex + entropy-based secret detection
│   │
│   ├── findings/                   # Finding collection and processing
│   │   ├── __init__.py
│   │   ├── models.py               # Finding, Severity, Confidence, CodeAction, FixSafety
│   │   └── collector.py            # Aggregate, deduplicate, sort findings
│   │
│   ├── parallel/                   # Parallelization engine
│   │   ├── __init__.py
│   │   ├── orchestrator.py         # loky process pool + task chunking
│   │   └── worker.py               # Per-worker: parse → lower → evaluate → return diagnostics
│   │
│   └── config/                     # Configuration management
│       ├── __init__.py
│       ├── loader.py               # Read .airev.toml → merge with defaults
│       └── defaults.py             # Default rules, severities, thresholds
│
├── interfaces/                     # I/O layer — connects core to outside world
│   ├── __init__.py
│   ├── cli/
│   │   ├── __init__.py
│   │   ├── main.py                 # Entry point: `airev scan .`, `airev init`, `airev rules`
│   │   └── formatters/
│   │       ├── __init__.py
│   │       ├── terminal.py         # Colored, rich terminal output with source snippets
│   │       ├── json_fmt.py         # JSON output for programmatic consumption
│   │       └── sarif.py            # SARIF 2.1.0 for GitHub code scanning integration
│   │
│   └── github_action/
│       ├── action.yml
│       ├── Dockerfile
│       └── entrypoint.sh
│
├── tests/
│   ├── conftest.py                 # Shared fixtures: arena builders, temp project helpers
│   ├── fixtures/                   # Sample code with known AI-generated defects
│   │   ├── python/
│   │   │   ├── hallucinated_api/
│   │   │   ├── phantom_import/
│   │   │   └── ...
│   │   └── typescript/
│   │       ├── hallucinated_api/
│   │       ├── phantom_import/
│   │       └── ...
│   ├── __snapshots__/              # syrupy snapshot baselines (.ambr files)
│   ├── test_arena/
│   ├── test_parsers/
│   ├── test_rules/
│   │   ├── test_hallucinated_api.py
│   │   ├── test_phantom_import.py
│   │   └── ...
│   ├── test_heuristics/
│   │   ├── test_winnowing.py
│   │   └── test_minhash.py
│   ├── test_resolver/
│   ├── test_cli/
│   └── test_integration/           # End-to-end: source file → CLI → verify output
│
├── build/
│   ├── nuitka_build.py
│   └── install.sh
│
├── .github/
│   ├── workflows/
│   │   ├── ci.yml
│   │   ├── release.yml
│   │   └── docker.yml
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.yml
│   │   └── feature_request.yml
│   └── PULL_REQUEST_TEMPLATE.md
│
├── .claude/
│   ├── github-workflow.md
│   └── architecture.md             # THIS FILE
│
├── CLAUDE.md
├── pyproject.toml
├── CHANGELOG.md
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
├── LICENSE                         # MIT
└── README.md
```

---

## 5. The UAST Arena (Structure of Arrays)

### 5.1 Why SoA Over Objects

Standard Python objects cost ~152 bytes each due to `__dict__` overhead. A 500-file project can produce millions of UAST nodes. Object-based trees cause:
- Memory bloat (152MB for 1M nodes)
- CPU cache thrashing (pointer chasing across fragmented heap)
- GC pressure from millions of small allocations

The SoA arena stores everything in parallel numpy arrays. A "node" is just an integer index. Memory is contiguous, cache-friendly, and GC-invisible.

### 5.2 Arena Implementation

```python
import numpy as np

class UastArena:
    """Structure of Arrays storage for UAST nodes. Mimics a bump-allocated arena."""

    def __init__(self, capacity: int = 100_000):
        # Node properties — parallel contiguous arrays
        self.node_types = np.zeros(capacity, dtype=np.int32)
        self.start_bytes = np.zeros(capacity, dtype=np.int32)
        self.end_bytes = np.zeros(capacity, dtype=np.int32)
        self.start_lines = np.zeros(capacity, dtype=np.int32)
        self.start_cols = np.zeros(capacity, dtype=np.int32)

        # Tree structure — integer indices, not pointers
        self.parent_indices = np.full(capacity, -1, dtype=np.int32)
        self.first_child = np.full(capacity, -1, dtype=np.int32)
        self.next_sibling = np.full(capacity, -1, dtype=np.int32)

        # String references — index into string table
        self.name_indices = np.full(capacity, -1, dtype=np.int32)

        # Bump allocator state
        self._count = 0
        self._capacity = capacity

    @property
    def count(self) -> int:
        return self._count

    def allocate(self, node_type: int, start: int, end: int,
                 line: int, col: int, parent: int = -1) -> int:
        """Allocate a node. Returns its index. O(1) bump allocation."""
        if self._count >= self._capacity:
            self._grow()
        idx = self._count
        self.node_types[idx] = node_type
        self.start_bytes[idx] = start
        self.end_bytes[idx] = end
        self.start_lines[idx] = line
        self.start_cols[idx] = col
        self.parent_indices[idx] = parent
        self._count += 1
        return idx

    def _grow(self):
        """Double capacity when exhausted."""
        new_cap = self._capacity * 2
        for attr in ['node_types', 'start_bytes', 'end_bytes', 'start_lines',
                      'start_cols', 'parent_indices', 'first_child',
                      'next_sibling', 'name_indices']:
            old = getattr(self, attr)
            new = np.zeros(new_cap, dtype=old.dtype)
            if old.dtype == np.int32 and attr in ('parent_indices', 'first_child',
                                                    'next_sibling', 'name_indices'):
                new[:] = -1
            new[:self._capacity] = old
            setattr(self, attr, new)
        self._capacity = new_cap
```

### 5.3 String Table

Identifiers (function names, import names, variable names) are stored in a separate interned string table. Arena nodes reference strings by integer index, keeping the arena arrays purely numeric.

```python
class StringTable:
    """Interned string storage. Deduplicates identical identifiers."""

    def __init__(self):
        self._strings: list[str] = []
        self._index: dict[str, int] = {}

    def intern(self, s: str) -> int:
        """Returns the index of the string, interning it if new."""
        if s in self._index:
            return self._index[s]
        idx = len(self._strings)
        self._strings.append(s)
        self._index[s] = idx
        return idx

    def get(self, idx: int) -> str:
        return self._strings[idx]
```

### 5.4 CST Node Backlinks

For language-specific rules that need full Tree-sitter CST access, maintain a separate list mapping arena index → Tree-sitter node. This is NOT stored in numpy (Tree-sitter nodes are Python objects). Only accessed when a rule explicitly needs CST detail.

```python
# Stored alongside arena, not inside it
cst_backlinks: list[tree_sitter.Node | None]  # arena_idx → CST node
```

---

## 6. The Rule Engine

### 6.1 Rule Interface

Rules are callables that operate on the arena + index:

```python
from typing import Protocol

class NodeRule(Protocol):
    """Rule evaluated per-node during linear scan."""

    @property
    def id(self) -> str: ...

    @property
    def severity(self) -> Severity: ...

    @property
    def target_node_types(self) -> frozenset[int]:
        """Which node types this rule cares about. Used to build dispatch table."""
        ...

    def evaluate(self, arena: UastArena, idx: int, ctx: LintContext) -> list[Finding]: ...


class FileRule(Protocol):
    """Rule evaluated once per file after the linear scan."""

    @property
    def id(self) -> str: ...

    @property
    def severity(self) -> Severity: ...

    def evaluate(self, arena: UastArena, ctx: LintContext) -> list[Finding]: ...
```

### 6.2 Dispatch Table Construction

At initialization, the rule registry builds a dispatch table mapping each node type integer to the list of rules that target it:

```python
def build_dispatch_table(rules: list[NodeRule]) -> dict[int, list[NodeRule]]:
    table: dict[int, list[NodeRule]] = {}
    for rule in rules:
        for node_type in rule.target_node_types:
            table.setdefault(node_type, []).append(rule)
    return table
```

### 6.3 Single-Pass Linear Scan

```python
def evaluate_file(arena: UastArena, node_rules: dict[int, list[NodeRule]],
                  file_rules: list[FileRule], ctx: LintContext) -> list[Finding]:
    findings: list[Finding] = []

    # Single linear pass over contiguous arena
    for idx in range(arena.count):
        node_type = arena.node_types[idx]
        rules = node_rules.get(node_type)
        if rules:
            for rule in rules:
                findings.extend(rule.evaluate(arena, idx, ctx))

    # Whole-file rules (copy-paste drift, inconsistent error handling)
    for rule in file_rules:
        findings.extend(rule.evaluate(arena, ctx))

    return findings
```

### 6.4 Safe Fix vs Unsafe Fix Classification

```python
@dataclass(slots=True, frozen=True)
class CodeAction:
    description: str
    replacement: str
    start_byte: int
    end_byte: int
    safety: FixSafety

class FixSafety(Enum):
    SAFE = "safe"       # Guaranteed no semantic change (e.g., remove unused import)
    UNSAFE = "unsafe"   # Requires human review (e.g., remove undefined security decorator)
```

- **Safe fixes** auto-applied with `airev scan --fix`
- **Unsafe fixes** surfaced as suggestions only — never auto-applied

---

## 7. Dependency Resolution

### 7.1 Python Import Resolution (Pyright Model)

Resolve through this ordered fallback chain:
1. **Workspace** — scan project directory for matching `.py` files/packages
2. **Virtual environment** — scan `site-packages` in detected venv
3. **Standard library** — check against known stdlib module list for detected Python version
4. **Type stubs** — check for PEP 561 stub packages
5. **Known dynamic modules** — whitelist of legitimately runtime-generated packages

If ALL paths fail → `phantom-import` with HIGH confidence.

### 7.2 JavaScript/TypeScript Resolution

1. **Relative imports** — resolve against file system
2. **node_modules** — walk up directory tree
3. **package.json exports** — honor `exports` field
4. **Built-in modules** — Node.js built-ins (`fs`, `path`, etc.)
5. **TypeScript paths** — resolve `tsconfig.json` path mappings

If ALL paths fail → `phantom-import` with HIGH confidence.

### 7.3 API Existence Verification

After resolving that a package EXISTS, verify the specific API:
- **Python**: Parse package's `__init__.py` and public modules for export map
- **JS/TS**: Read `package.json` exports + `.d.ts` declaration files

---

## 8. Heuristics

### 8.1 Copy-Paste Drift Detection

**Step 1: Structural Tokenization**
Strip variable names, comments, string literals from UAST. Retain only structural token sequence from the arena's `node_types` array.

**Step 2: Winnowing via numpy stride tricks (zero-copy k-gram extraction)**
```python
import numpy as np

def extract_kgrams(node_types: np.ndarray, start: int, end: int, k: int = 5) -> np.ndarray:
    """Zero-copy sliding window k-gram extraction using stride manipulation."""
    seq = node_types[start:end]
    shape = (seq.shape[0] - k + 1, k)
    strides = (seq.strides[0], seq.strides[0])
    return np.lib.stride_tricks.as_strided(seq, shape=shape, strides=strides)
```

**Step 3: MinHash similarity via datasketch**
```python
from datasketch import MinHash

def compute_signature(kgrams: np.ndarray, num_perm: int = 128) -> MinHash:
    m = MinHash(num_perm=num_perm)
    m.update_batch([gram.tobytes() for gram in kgrams])
    return m
```

Flag pairs with Jaccard similarity ≥ 0.7 as `copy-paste-drift`.

**Libraries:** Use `datasketch` (numpy backend) as default. Consider `rensa` (Rust-backed, 2.5-3x faster) or `scanoss-winnowing` (C-backed) if performance requires it.

### 8.2 Secret Detection

Curated regex patterns + Shannon entropy analysis:
- AWS keys: `AKIA[0-9A-Z]{16}`
- Generic API keys: high-entropy strings (Shannon > 4.5) assigned to variables named `key`, `token`, `secret`, `password`
- Private keys: `-----BEGIN.*PRIVATE KEY-----`
- Connection strings with embedded credentials

---

## 9. Parallelization

### 9.1 Engine: loky (not ProcessPoolExecutor)

`loky` provides:
- Robust worker management (no deadlocks on worker death)
- Consistent spawn behavior across OS
- Reusable process pools (avoid fork overhead on repeated scans)

### 9.2 Task Chunking Pattern

Workers process batches of files (not individual files) to amortize IPC overhead:

```python
from loky import get_reusable_executor

def parallel_scan(file_paths: list[str], rules: list, config: Config) -> list[Finding]:
    executor = get_reusable_executor(max_workers=os.cpu_count())

    # Chunk files into batches of ~50
    chunks = [file_paths[i:i+50] for i in range(0, len(file_paths), 50)]

    futures = [executor.submit(worker_scan_chunk, chunk, rules, config)
               for chunk in chunks]

    all_findings: list[Finding] = []
    for future in futures:
        all_findings.extend(future.result())  # Lightweight dicts, not AST objects

    return all_findings
```

### 9.3 What Crosses Process Boundaries

- **INTO worker:** file paths (strings), rule config (small dict) — cheap to pickle
- **OUT of worker:** list of `Finding` dicts — lightweight, cheap to pickle
- **NEVER crosses boundary:** arena arrays, Tree-sitter objects, CST nodes — these stay process-local

### 9.4 Phase 2: Shared Memory Arena

For very large monorepos (10k+ files), use `multiprocessing.shared_memory` to share numpy arrays across processes without copying. The main process pre-allocates the arena in shared memory, workers populate it in place. This eliminates ALL IPC serialization overhead.

---

## 10. Testing Strategy

### 10.1 Snapshot Testing via syrupy

**syrupy** is the mandated snapshot testing framework. It provides:
- Idiomatic pytest assertions: `assert data == snapshot`
- Strict failure on missing snapshots (no silent passes)
- Interactive review: `pytest --snapshot-update`
- `.ambr` format readable in GitHub PR diffs
- Redaction filters for non-deterministic data

```python
def test_hallucinated_api_numpy(snapshot):
    source = b'''
import numpy as np
result = np.fast_fourier_transform(data)  # doesn't exist
'''
    findings = scan_source(source, language="python")
    assert findings == snapshot
```

### 10.2 Snapshot Determinism

All snapshot outputs MUST replace:
- Absolute paths → `<project_root>/relative/path`
- Timestamps → `<TIMESTAMP>`
- Non-deterministic ordering → sort findings by (file, line, rule_id)
- Memory addresses / arena capacities → redacted via `exclude` filter

### 10.3 Minimum Test Requirements Per Rule

- 2 true-positive fixtures (code that SHOULD trigger)
- 2 true-negative fixtures (code that should NOT trigger)
- 1 edge case fixture
- 1 snapshot test covering all fixtures
- 1 integration test: source file → CLI → verify finding in output

### 10.4 Fixture Structure

```
tests/fixtures/python/hallucinated_api/
├── bad_numpy_method.py         # True positive
├── bad_requests_method.py      # True positive
├── valid_numpy_method.py       # True negative
├── valid_custom_module.py      # True negative
├── dynamic_getattr.py          # Edge case
└── expected.md                 # Documents what each fixture tests
```

---

## 11. Distribution

### 11.1 Native Binary (Primary)

- **Nuitka** compiles Python → C → native binary
- Single ~15MB executable, zero runtime dependencies
- CI builds for: `linux-x86_64`, `linux-arm64`, `macos-x86_64`, `macos-arm64`
- Attached to GitHub Releases on version tags
- Install: `curl -fsSL https://airev.dev/install.sh | bash`

### 11.2 Docker (for CI/CD)

- Minimal container with just the binary
- Published to `ghcr.io/airev-tools/airev`
- GitHub Action uses this container

### 11.3 pip (Secondary)

- `pip install airev` for Python developers who prefer it

---

## 12. Configuration

### 12.1 Zero-Config Default

`airev scan .` works with no config file. All rules enabled. Languages auto-detected.

### 12.2 Optional `.airev.toml`

```toml
[airev]
exclude = ["vendor/**", "dist/**", "node_modules/**"]

[rules]
hallucinated-api = "off"
hardcoded-secrets = "error"
copy-paste-drift = "warning"

[rules.copy-paste-drift]
similarity_threshold = 0.8
min_lines = 10

[languages]
enabled = ["python", "typescript"]
```

### 12.3 CLI Flags

```bash
airev scan .                              # Zero config
airev scan . --lang python                # Only Python
airev scan . --exclude "tests/**"         # Exclude paths
airev scan . --format sarif               # Output format
airev scan . --fix                        # Auto-apply safe fixes
airev scan . --rule hallucinated-api      # Run single rule
```

---

## 13. Key Dependencies

| Package | Purpose | Why this one |
|---------|---------|-------------|
| `tree-sitter` | CST parsing | Error-tolerant, multi-language, C-backed |
| `tree-sitter-python` | Python grammar | Official Tree-sitter grammar |
| `tree-sitter-javascript` | JS/TS grammar | Official Tree-sitter grammar |
| `tree-sitter-typescript` | TypeScript grammar | Official Tree-sitter grammar |
| `numpy` | SoA arena storage | Contiguous C arrays, zero-copy views, stride tricks |
| `datasketch` | MinHash/Jaccard | Production-ready, numpy-optimized backend |
| `loky` | Process parallelism | Robust alternative to ProcessPoolExecutor |
| `click` | CLI framework | Clean, composable, well-tested |
| `rich` | Terminal output | Colored output with source code snippets |
| `syrupy` | Snapshot testing | Interactive review, strict failure, .ambr format |
| `ruff` | Linting/formatting | Fastest Python linter (we use what we preach) |
| `mypy` | Type checking | Strict mode for full type safety |

---

## 14. Performance Targets

| Metric | Target | Method |
|--------|--------|--------|
| Small file (<500 LOC) | <50ms | Single-thread, numpy arena scan |
| Medium project (50 files) | <2s | loky process pool, task chunking |
| Large project (500 files) | <15s | loky + file-hash caching for incremental |
| Binary size | <20MB | Nuitka `--standalone` |
| Memory per file | <5MB | SoA arena, no per-node object overhead |

---

## 15. Phase 2 Roadmap (NOT for MVP)

Documented for architectural awareness only. Do NOT build during Phase 1.

- **Incremental computation** via `mandala` — hierarchical memoization with DAG-based "early cutoff" (Python equivalent of Rust's Salsa framework)
- **Shared memory arena** — `multiprocessing.shared_memory` + numpy for zero-copy IPC across workers
- **Rust rewrite** — if airev gains traction, rewrite core in Rust (arena alloc, Rayon, Salsa, WASM)
- **LSP server** — real-time editor integration
- **WASM build** — run in browser-based editors
- **Control Flow Graphs** — detect unreachable code, missed returns
- **Full scope analysis** — variable hoisting, shadowing, dead stores
- **Object pooling** — `pond` library for Tree-sitter wrapper recycling during parse phase
- **Custom rule DSL** — let users write rules without Python

---

## 16. Coding Standards

### 16.1 Type Safety

- **Strict mypy** with `--strict`. No `Any` without justification.
- All function signatures fully annotated.
- Use `|` union syntax (Python 3.12+), not `Optional`.

### 16.2 Formatting and Linting

- **Ruff** for linting and formatting. Zero warnings.

### 16.3 Naming

- Modules: `snake_case.py`
- Classes: `PascalCase`
- Functions: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Node type constants: `UPPER_SNAKE_CASE` integers (`TYPE_FUNCTION_DEF = 1`)
- Rule IDs: `kebab-case` (`hallucinated-api`, `phantom-import`)

### 16.4 Import Ordering

```python
# 1. Standard library
import os
from pathlib import Path

# 2. Third-party
import numpy as np
import tree_sitter

# 3. Local — always absolute imports
from airev_core.arena.uast_arena import UastArena
from airev_core.findings.models import Finding, Severity
```

### 16.5 No Global Mutable State

Zero global variables. Zero module-level mutable state. Configuration passed as arguments or via `LintContext`.