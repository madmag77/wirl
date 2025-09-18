# wirl-lang — Workflow DSL (BNF + Parser)

This package contains the grammar and parser for the WIRL workflow DSL. The DSL compiles to an explicit directed graph with optional guarded loops. This subfolder is self-contained: a BNF grammar and a Python parser that produces a structured AST you can feed into an engine.

## Scope of this folder

- Grammar: `grammar/wirl.bnf`
- Parser and AST dataclasses: `grammar/wirl_parser.py`
- Public API: `parse_wirl_to_objects(path: str) -> Workflow`

## Quick start

```python
from wirl_lang import parse_wirl_to_objects

workflow = parse_wirl_to_objects(
    "workflow_definitions/paper_rename_workflow/paper_rename_workflow.wirl"
)

print(workflow.name)
for node in workflow.nodes:
    print(type(node).__name__, getattr(node, "name", None))
```

## DSL at a glance

- Workflow file defines exactly one runnable graph: `workflow <Name> { ... }`.
- Nodes are external function calls with declared inputs/outputs and immutable `const { ... }`.
- Data dependencies are implicit: a node becomes eligible once its inputs are available.
- No shared mutable state. All values are immutable except outputs with reducer `(append)` which accumulate into a list.
- Optional inputs/outputs use a trailing `?` in their declaration. Optional inputs do not create execution dependencies.
- Guarded loops via `cycle` with a `guard { ... }` clause and `max_iterations: <int>`.
- Conditional execution via `when { <boolean-expr> }` on nodes and guards.
- Human-in-the-loop `hitl { ... }` and `retry { ... }` are present in the grammar; see status below.

## Example (excerpt)

This is a shortened excerpt of the working workflow in `workflow_definitions/paper_rename_workflow/paper_rename_workflow.wirl`:

```txt
workflow PaperRenameWorkflow {

  metadata {
    description: "Paper Rename workflow"
    owner: "madmag77"
    version: "1.0"
    files_extension: "pdf"
  }

  inputs {
    String drafts_folder_path
    String processed_folder_path
  }

  outputs {
    List<String> processed_files = ReturnProcessedFiles.processed_files
  }

  node GetFiles {
    call get_files
    inputs {
      String drafts_folder_path = drafts_folder_path
    }
    outputs {
      List<String> file_paths
    }
  }
```

```txt
  cycle RenameLoop {
    inputs {
        List<String> initial_file_paths_to_process = GetFiles.file_paths
        List<String> remaining_file_paths_to_process = ReadPdfFile.remaining_file_paths
        String processed_folder_path = processed_folder_path
    }
    outputs {
        List<String> processed_files = CheckAllFilesProcessed.processed_files
    }

    node ReadPdfFile {
        call read_pdf_file
        inputs {
           List<T<Image>> file_paths = RenameLoop.remaining_file_paths_to_process?
           List<String> initial_file_paths_to_process = RenameLoop.initial_file_paths_to_process
        }
        const {
            pages_to_read: 2
        }
        outputs {
           List<T<Image>> pages
           String file_path
           List<String> remaining_file_paths
           Bool no_files_to_process
        }
    }

    ...

    guard {
      inputs {
        Bool is_done = CheckAllFilesProcessed.is_done
      }
      when {
        CheckAllFilesProcessed.is_done
      }
    }
    max_iterations: 10
  }
```

## Grammar highlights

- Top-level:
  - `workflow <Name> { metadata? inputs? outputs? node* cycle* }`
- Nodes:
  - `node <Name> { call <module_or_func> inputs { ... } outputs { ... } const { ... } when { ... } hitl { ... } retry { ... } }`
- Parameters:
  - Declarations: `TYPE name (= value)? ?`
  - Values: literal or reference `OtherNode.outputName`
  - Optional: trailing `?` (e.g., `String clarifications?`)
  - Reducers on outputs: `(append) TYPE name` or default `(last)`
- Cycles:
  - `cycle <Name> { inputs { ... } outputs { ... } node* guard { inputs { ... } when { ... } } max_iterations: INT }`
- Conditionals:
  - `when { <boolean-expr> }` on nodes and inside guards

## Parser API

- `parse_wirl_to_objects(path: str) -> Workflow`
  - Returns a `Workflow` dataclass with:
    - `name: str`
    - `metadata: Optional[Metadata]` (`entries: Dict[str, str]`)
    - `inputs: List[Input]`, `outputs: List[Output]`
    - `nodes: List[NodeClass | CycleClass]`
  - `NodeClass`: `name`, `call`, `inputs`, `outputs`, `when`, `hitl`, `retry`, `constants`
  - `CycleClass`: `name`, `inputs`, `outputs`, `nodes`, `guard`, `max_iterations`
  - `Output.reducer`: `"last"` (default) or `"append"`

## Type system

- Supported tokens in the grammar: `Bool, Int, Float, String, File, Object<...>, List<T>` (free-form `TYPE` token covers these and generics).
- Current parser does not enforce types; it records the declared type name string.

## Feature status

- Implemented in grammar and parser:
  - Workflows, nodes, inputs/outputs, constants, reducers `(append)`
  - `when { ... }` conditions
  - `cycle` with `guard { ... }` and `max_iterations`
- Present in grammar but not fully wired in the AST yet:
  - `retry { attempts, backoff, policy }` (parsed token exists; transformer wiring pending)
  - `hitl { correlation, timeout }` (accepted; current transformer sets a placeholder/default)
- Planned validations (not yet implemented):
  - Missing required inputs, unused outputs, type mismatches
  - Single entry/exit checks and reachability

## Design notes (execution semantics)

- One file ⇒ one graph with a single entry and a single exit.
- Dataflow drive: node executes when all non-optional inputs become available and `when` block is evaluated to True (if any).
- All values are immutable; `(append)` outputs accumulate across iterations/paths.
- Guarded loops model Pregel-style supersteps; parallelism can be expressed with multiple nodes eligible in the same step. A `parallel` block may be added in the future.

### When Block Evaluation Rules

The `when` blocks use special truthiness evaluation that differs from standard Python boolean logic:

- **False conditions**: Only `None` or explicit `False` evaluate to false
- **True conditions**: All other values evaluate to true, including:
  - Empty containers: `[]`, `{}`, `""`
  - Zero values: `0`, `0.0`
  - Objects with custom types not defined in the evaluation context

This design ensures that:
1. Only explicit absence (`None`) or negation (`False`) prevents node execution
2. Empty results from previous nodes don't block subsequent processing
3. Type definitions don't need to be available during condition evaluation

**Examples:**
```wirl
node ProcessIfResults {
  when {
    DataLoader.items  // True even if items is []
  }
}

node SkipIfDisabled {
  when {
    Config.enabled  // False only if None or explicit False
  }
}

node HandleCustomObjects {
  when {
    Parser.objects  // True even if objects contains undefined types
  }
}
```

## Local development

- Edit the grammar in `grammar/wirl.bnf` and the transformer in `grammar/wirl_parser.py`.
- After grammar changes, re-run your parser-driven test or the quick-start snippet above.

## FAQ

- Can I reference optional outputs? Yes. Declare the consuming input as optional with a trailing `?` and assign from `Producer.optionalOutput`.
- Do optional inputs block execution? No. Absence of an optional input does not prevent node scheduling.
- How do I append across iterations? Mark the output with `(append)` in its declaration, e.g., `(append) List<String> processed_files`.

## License

This package is released under the repository’s root license.
