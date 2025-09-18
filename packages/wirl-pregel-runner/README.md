## WIRL Pregel Runner

Run WIRL workflows on top of LangGraph's Pregel execution model with built‑in parallelism, checkpoints, and optional human‑in‑the‑loop (HITL) steps.

## 1) What is WIRL?

WIRL is a compact workflow DSL that compiles to an explicit directed graph with optional guarded loops. Nodes declare inputs/outputs; optional inputs do not block scheduling; reducers like `(append)` accumulate outputs across iterations. See `packages/wirl-lang/` for the DSL, parser, and quickstart.

## 2) What is the WIRL Pregel Runner?

Python runner that executes WIRL workflows with LangGraph Pregel:
- **Parallelization**: ready nodes run concurrently in supersteps.
- **Checkpoints**: resume from saved state with a checkpointer.
- **HITL**: supports human‑in‑the‑loop hooks from the WIRL spec.

API: `wirl_pregel_runner.run_workflow(workflow_path, fn_map, params=None, thread_id=None, resume=None, checkpointer=None)`.

## 3) Install

Requires Python 3.10+

```bash
# from source (editable)
cd packages/wirl-pregel-runner
pip install -e .
# or with uv
uv pip install -e .
```

## 4) Use

### Python API
```python
from wirl_pregel_runner import run_workflow

workflow_path = "tests/wirls/sample.wirl"

fn_map = {
    "query_extender": lambda query, config: {"extended_query": "extended query"},
    "retrieve_from_web": lambda extended_query, config: {"chunks": ["chunk"], "need_filtering": False},
}

result = run_workflow(
    workflow_path,
    fn_map=fn_map,
    params={"query": "hello"},
    thread_id="cli",
)
print(result)
```

### CLI
```bash
python -m wirl_pregel_runner.pregel_runner \
  path/to/workflow.wirl \
  --functions your_module_with_functions \
  --param key=value \
  --thread-id myrun \
  --resume '{"configurable": {"thread_id": "myrun"}}'
```

- `--functions`: module exposing callables whose names match WIRL `call` identifiers
- `--param`: repeatable `key=value`; numbers auto‑parsed
- `--thread-id`: correlates runs for checkpointing
- `--resume`: JSON string to resume via LangGraph

### Examples

Use the wirls in tests as references:
- `tests/wirls/sample.wirl`
- `tests/wirls/sample_with_cycle.wirl`

See how functions are wired and assertions made in:
- `tests/test_simple_wirl_runner.py`
- `tests/test_wirl_with_cycles_runner.py`

### When Block Evaluation

The Pregel runner evaluates `when` blocks with special truthiness rules:

- **False conditions**: Only `None` or explicit `False` evaluate to false
- **True conditions**: All other values evaluate to true, including:
  - Empty containers: `[]`, `{}`, `""`
  - Zero values: `0`, `0.0`
  - Objects with undefined types (e.g., custom classes not in scope)

This means expressions like `None or [CustomType(...)]` will evaluate to `true` even if `CustomType` is not defined in the evaluation context, as long as the actual data exists in the workflow state.

**Example:**
```wirl
node ProcessData {
  when {
    SomeNode.results  // True even if results is [] or contains undefined types
  }
}

node SkipIfNone {
  when {
    SomeNode.optional_data  // False only if None or explicit False
  }
}
```

## 5) License

MIT — see root `LICENSE`.

## Also useful

- DSL and parser: `packages/wirl-lang/`
- Larger example workflow: `workflow_definitions/paper_rename_workflow/`
