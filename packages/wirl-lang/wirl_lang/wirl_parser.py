from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from lark import Lark, Transformer


def load_grammar() -> str:
    return (Path(__file__).with_name("wirl.bnf")).read_text()


class Reducer(Enum):
    LAST = "last"
    APPEND = "append"


@dataclass
class Constant:
    """Represents a constant declaration"""

    name: str
    value: Any


@dataclass
class Input:
    """Represents an input parameter declaration"""

    type: str
    name: str
    default_value: Optional[str] = None
    optional: bool = False

    @property
    def target_node_name(self):
        if self.default_value is None or "." not in self.default_value:
            return None
        return self.default_value.split(".", 1)[0]


@dataclass
class Output:
    """Represents an output parameter declaration"""

    type: str
    name: str
    reducer: Reducer = Reducer.LAST
    default_value: Optional[Any] = None
    optional: bool = False

    @property
    def target_node_name(self):
        if self.default_value is None or "." not in self.default_value:
            return None
        return self.default_value.split(".", 1)[0]


@dataclass
class Metadata:
    """Represents workflow metadata"""

    entries: Dict[str, str] = field(default_factory=dict)


@dataclass
class HitlConfig:
    """Represents human-in-the-loop configuration"""

    correlation: str
    timeout: str


@dataclass
class RetryConfig:
    """Represents retry configuration"""

    attempts: int
    backoff: str
    policy: str


@dataclass
class NodeClass:
    """Represents a workflow node"""

    name: str
    call: str
    inputs: List[Input] = field(default_factory=list)
    outputs: List[Output] = field(default_factory=list)
    when: Optional[str] = None
    hitl: Optional[HitlConfig] = None
    retry: Optional[RetryConfig] = None
    constants: List[Constant] = field(default_factory=list)


@dataclass
class GuardClass:
    """Represents a workflow guard"""

    when: str = ""
    inputs: List[Input] = field(default_factory=list)


@dataclass
class CycleClass:
    """Represents a workflow cycle"""

    name: str
    inputs: List[Input] = field(default_factory=list)
    outputs: List[Output] = field(default_factory=list)
    nodes: List[NodeClass] = field(default_factory=list)
    guard: GuardClass = field(default_factory=GuardClass)
    max_iterations: int = 10
    nodes_outputs: List[str] = field(default_factory=list)


@dataclass
class Workflow:
    """Represents the complete workflow"""

    name: str
    metadata: Optional[Metadata] = None
    inputs: List[Input] = field(default_factory=list)
    outputs: List[Output] = field(default_factory=list)
    nodes: List[NodeClass | CycleClass] = field(default_factory=list)


class ASTBuilder(Transformer):
    def workflow(self, items):
        name = items[0]
        body = items[1]
        wf = Workflow(name=name)
        for it in body:
            if isinstance(it, Metadata):
                wf.metadata = it
            elif isinstance(it, list) and len(it) > 0 and isinstance(it[0], Input):
                wf.inputs = it
            elif isinstance(it, list) and len(it) > 0 and isinstance(it[0], Output):
                wf.outputs = it
            elif isinstance(it, (NodeClass, CycleClass)):
                wf.nodes.append(it)
        return wf

    def workflow_body(self, items):
        return items

    def metadata_block(self, items):
        metadata = Metadata()
        for entry in items:
            if isinstance(entry, tuple) and len(entry) == 2:
                key, value = entry
                metadata.entries[key] = value
        return metadata

    def inputs_block(self, items):
        return items

    def outputs_block(self, items):
        return items

    def constants_block(self, items):
        return [Constant(name=constant.name, value=constant.value) for constant in items]

    def const_entry(self, items):
        return Constant(name=items[0], value=items[1])

    def param_decl(self, items):
        type_name = items[0]
        name = items[1]
        default_value = items[2] if len(items) > 2 else None
        optional = items[3] if len(items) > 3 else False

        return Input(type=type_name, name=name, default_value=default_value, optional=optional)

    def output_param_decl(self, items):
        reducer = items[0] if isinstance(items[0], Reducer) else None
        reducer_offset = 1 if reducer else 0
        type_name = items[0 + reducer_offset]
        name = items[1 + reducer_offset]
        default_value = items[2 + reducer_offset] if len(items) > 2 + reducer_offset else None
        optional = items[3 + reducer_offset] if len(items) > 3 + reducer_offset else False

        return Output(reducer=reducer or Reducer.LAST, type=type_name, name=name, default_value=default_value, optional=optional)

    def param_value(self, items):
        return items[0]

    def metadata_entry(self, items):
        return (items[0], items[1])

    def node_block(self, items):
        name = items[0]
        body = items[1]
        node = NodeClass(name=name, call=body["call"])

        # Process node elements
        if "when" in body:
            node.when = body["when"]
        if "inputs" in body:
            node.inputs = body["inputs"]
        if "outputs" in body:
            node.outputs = body["outputs"]
        if "hitl" in body:
            node.hitl = body["hitl"]
        if "retry" in body:
            node.retry = body["retry"]
        if "constants" in body:
            node.constants = body["constants"]

        return node

    def node_body(self, items):
        info = {"call": items[0]}
        for it in items[1:]:
            if isinstance(it, dict):
                info.update(it)
            elif isinstance(it, list):
                # Handle inputs/outputs lists
                if len(it) > 0 and isinstance(it[0], Input):
                    info["inputs"] = it
                elif len(it) > 0 and isinstance(it[0], Output):
                    info["outputs"] = it
                elif len(it) > 0 and isinstance(it[0], Constant):
                    info["constants"] = it
        return info

    def node_element(self, items):
        # unwrap single element rules
        return items[0]

    def call_stmt(self, items):
        return items[0]

    def when_clause(self, items):
        return {"when": items[0]}

    def hitl_block(self, items):
        # For now, return basic config - can be enhanced later
        return {"hitl": HitlConfig(correlation="default", timeout="24h")}

    def cycle_block(self, items):
        name = items[0]
        body = items[1]
        cycle = CycleClass(name=name)

        # Process cycle elements
        if "inputs" in body:
            cycle.inputs = body["inputs"]
        if "outputs" in body:
            cycle.outputs = body["outputs"]
        if "nodes" in body:
            cycle.nodes = body["nodes"]
        if "guard" in body:
            cycle.guard = body["guard"]
        if "max_iterations" in body:
            cycle.max_iterations = body["max_iterations"]

        return cycle

    def cycle_body(self, items):
        res: dict[str, Any] = {"inputs": [], "outputs": [], "nodes": []}
        for it in items:
            if isinstance(it, NodeClass):
                res["nodes"].append(it)
            elif isinstance(it, list) and len(it) > 0 and isinstance(it[0], Input):
                res["inputs"] = it
            elif isinstance(it, list) and len(it) > 0 and isinstance(it[0], Output):
                res["outputs"] = it
            elif isinstance(it, dict) and "guard" in it:
                res["guard"] = it["guard"]
            elif isinstance(it, int):
                res["max_iterations"] = it
        return res

    def guard_clause(self, items):
        return {"guard": items[0]}

    def guard_body(self, items):
        return GuardClass(inputs=items[0], when=items[1]["when"])

    def expr(self, items):
        text = str(items[0]).strip()
        if "#" in text:
            text = text.split("#", 1)[0].strip()
        return text

    def reducer_decl(self, items):
        return Reducer(items[0])

    def default_value(self, items):
        return items[0]

    def literal(self, items):
        return items[0]

    def INT(self, token):
        return int(token)

    def NAME(self, token):
        return str(token)

    def STRING(self, token):
        s = str(token)
        return s[1:-1]

    def DURATION(self, token):
        return str(token)

    def BOOL(self, token):
        return str(token).lower() == "true"

    def QUESTION(self, token):
        return True

    def REDUCER(self, token):
        return str(token)

    def NAME_WITH_DOT(self, token):
        return str(token)


def parse_wirl_to_objects(path: str) -> Workflow:
    """Parse Wirl file and return structured object hierarchy"""
    grammar = load_grammar()
    parser = Lark(grammar, start="workflow")
    tree = parser.parse(Path(path).read_text())
    transformer = ASTBuilder()
    return transformer.transform(tree)
