from __future__ import annotations

import json
import logging
import operator
from typing import Any, Callable, Dict, List, Set

from langchain_core.runnables import RunnableConfig, RunnableLambda
from langgraph.channels import BinaryOperatorAggregate, LastValue
from langgraph.pregel import Pregel
from langgraph.pregel._read import PregelNode
from langgraph.pregel._write import ChannelWrite, ChannelWriteTupleEntry
from langgraph.types import interrupt
from wirl_lang import (
    CycleClass,
    NodeClass,
    Reducer,
    Workflow,
    parse_wirl_to_objects,
)

logger = logging.getLogger(__name__)

START_NODE_NAME = "start"


def _eval_value(expr: str, state: Dict[str, Any]):
    if expr is None:
        raise ValueError("Value is None")

    expr = str(expr).strip()
    if expr.startswith('"') and expr.endswith('"'):
        return expr[1:-1]
    try:
        return int(expr)
    except ValueError:
        try:
            return float(expr)
        except ValueError:
            pass
    return state.get(expr)


def _eval_condition(expr: str, state: Dict[str, Any]) -> bool:
    if expr is None:
        raise ValueError("Condition is None")

    expr = str(expr).strip()

    # Create a safe evaluation namespace with state values
    safe_globals = {"__builtins__": {}}
    safe_locals = {}

    # Add state values to the evaluation namespace
    for key, value in state.items():
        # Handle dotted notation like "NodeName.output"
        if "." in key:
            parts = key.split(".")
            if len(parts) == 2:
                node_name, attr_name = parts
                if node_name not in safe_locals:
                    safe_locals[node_name] = {}
                safe_locals[node_name][attr_name] = value
        else:
            safe_locals[key] = value

    # Create objects for dotted access with fallback to False for missing attributes
    class StateObject:
        def __init__(self, data):
            for k, v in data.items():
                setattr(self, k, v)

        def __getattr__(self, name):
            # Return False for any missing attribute instead of raising AttributeError
            return False

    # Convert nested dicts to objects for attribute access
    for key, value in list(safe_locals.items()):
        if isinstance(value, dict):
            safe_locals[key] = StateObject(value)

    # Create a custom dict that returns a falsy StateObject for missing keys
    class FalsyDict(dict):
        def __missing__(self, key):
            # Return an empty StateObject that will return False for any attribute access
            return StateObject({})

    # Wrap safe_locals in FalsyDict to handle missing node names
    safe_locals = FalsyDict(safe_locals)

    try:
        result = eval(expr, safe_globals, safe_locals)
        # Only None or explicit False should evaluate to False
        # Empty containers like [], {}, "", 0 should evaluate to True
        return result is not None and result is not False
    except (NameError, AttributeError):
        # If we can't evaluate due to missing names/attributes, return False
        return False


def extract_dependencies(inputs: List, workflow_inputs: Set[str]) -> Set[str]:
    """Extract node dependencies from input assignments"""
    dependencies = set()
    for inp in inputs:
        if inp.default_value is not None:
            default_val = str(inp.default_value).strip()
            # Check if it's a node reference (contains a dot)
            if "." in default_val and not default_val.startswith('"'):
                node_name = default_val.split(".")[0]
                dependencies.add(node_name)
            elif default_val in workflow_inputs:
                dependencies.add(START_NODE_NAME)
            else:
                # It's a constant or a workflow input
                pass
    return dependencies


def extract_in_cycle_dependencies(inputs: List, cycle_inputs: Set[str], cycle_start_name: str) -> Set[str]:
    """Extract node dependencies from input assignments"""
    dependencies = set()
    for inp in inputs:
        if inp.default_value is not None:
            default_val = str(inp.default_value).strip()
            if default_val in cycle_inputs:
                dependencies.add(cycle_start_name)
            elif "." in default_val and not default_val.startswith('"'):
                node_name = default_val.split(".")[0]
                dependencies.add(node_name)
            else:
                raise ValueError(f"Node {default_val} not found")
    return dependencies


def make_cycle_guard_pregel_node(cycle: CycleClass, iteration_key: str, all_in_cycle_outputs: set[str]):
    def cycle_guard(task_input: dict) -> dict | None:
        all_inputs_available = all(task_input.get(inp.default_value) is not None for inp in cycle.guard.inputs if inp.default_value is not None and not inp.optional)
        if not all_inputs_available:
            return None

        update = {}
        count = task_input.get(iteration_key, 0)
        if _eval_condition(cycle.guard.when, task_input) or count >= cycle.max_iterations - 1:
            # Prepare the output of the cycle block
            for out in cycle.outputs:
                val = _eval_value(out.default_value or "", task_input)
                update[cycle.name + "." + out.name] = val
            # And finish the cycle
            return update

        # This will trigger the next iteration
        update[iteration_key] = 1
        return update

    triggers = [inp.default_value for inp in cycle.guard.inputs if inp.target_node_name is not None and inp.default_value is not None]
    return create_pregel_node_from_params(fn=cycle_guard, channels=triggers + [iteration_key] + list(all_in_cycle_outputs), triggers=triggers)


def create_cycle_start_pregel_node(cycle: CycleClass, iteration_key: str, cycle_nodes_outputs_to_clean: list[str], all_in_cycle_outputs: set[str]):
    inputs_dict = {inp.name: inp.default_value for inp in cycle.inputs if inp.default_value is not None}

    def cycle_start(task_input: dict) -> dict:
        update = {}
        for k, expr in inputs_dict.items():
            val = _eval_value(expr, task_input)
            update[cycle.name + "." + k] = val

        for clear_node in cycle_nodes_outputs_to_clean:
            update[clear_node] = None

        return update

    triggers = [inp.default_value for inp in cycle.inputs if inp.default_value is not None and inp.default_value not in all_in_cycle_outputs]
    triggers.append(iteration_key)
    return create_pregel_node_from_params(fn=cycle_start, channels=triggers + list(all_in_cycle_outputs), triggers=triggers)


def make_pregel_task(node: NodeClass, fn_map: Dict[str, Any]):
    func = fn_map.get(node.call)
    if not callable(func):
        raise ValueError(f"Function '{node.call}' not provided")
    metadata = {constant.name: constant.value for constant in node.constants}

    def task(task_input: dict, config: RunnableConfig) -> dict | None:
        logger.info(f"Running {node.call} with inputs {task_input}")
        # Check if all inputs are available
        all_inputs_available = all(task_input.get(inp.default_value) is not None for inp in node.inputs if not inp.optional and inp.default_value is not None)
        if not all_inputs_available:
            return None

        # Check if the "when" condition is met
        if node.when and not _eval_condition(node.when, task_input):
            return None

        update_with_node_name = {}
        inputs = {inp.name: task_input.get(inp.default_value, None) for inp in node.inputs}
        try:
            # We run HITL initiating function only the first time (because otherwise langgraph will be re-running the function after each resume)
            resume = (config.get("configurable") or {}).get("resume", None)
            if not resume or not node.hitl:
                update = func(**inputs, config=metadata | config) or {}
                update_with_node_name = {node.name + "." + k: v for k, v in update.items()}
        except Exception as e:
            error_msg = f"Error in {node.call}: {e}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e
        if node.hitl:
            user_answer = interrupt({"request": json.dumps(inputs)})
            update_with_node_name[node.name + "." + node.outputs[0].name] = user_answer
        return update_with_node_name

    return task


def create_pregel_node_from_params(fn: Callable, channels: List[str], triggers: List[str]):
    def update_mapper(x):
        if x is None:
            return None
        updates: list[tuple[str, Any]] = []
        for k, v in x.items():
            updates.append((k, v))
        return updates

    return PregelNode(
        channels=channels,
        triggers=triggers,
        tags=[],
        metadata={},
        writers=[ChannelWrite([ChannelWriteTupleEntry(mapper=update_mapper)])],
        bound=RunnableLambda(fn),
        retry_policy=[],
        cache_policy=None,
    )


def create_pregel_node(node: NodeClass, fn_map: Dict[str, Any]):
    channels = [inp.default_value for inp in node.inputs if inp.default_value is not None]
    return create_pregel_node_from_params(make_pregel_task(node, fn_map), channels, channels)


def build_pregel_graph(path: str, functions: Dict[str, Any], checkpointer: Any | None = None):
    workflow: Workflow = parse_wirl_to_objects(path)

    # Dynamically build fields from workflow inputs, outputs, and all node inputs/outputs
    field_names = {}

    # Add workflow inputs and outputs
    for inp in workflow.inputs:
        field_names[inp.name] = LastValue(Any)
    for out in workflow.outputs:
        field_names[out.name] = LastValue(Any)

    fn_map = dict(functions)

    # Get workflow input names
    workflow_inputs = {inp.name for inp in workflow.inputs}

    # Collect nodes dependencies
    node_dependencies = {}
    all_dependencies = set()
    number_of_cycles = 0
    nodes = {}
    cycle_iteration_keys = []
    for node in workflow.nodes:
        if isinstance(node, NodeClass):
            for out in node.outputs:
                field_names[node.name + "." + out.name] = LastValue(Any)
            deps = extract_dependencies(node.inputs, workflow_inputs)
            node_dependencies[node.name] = deps

            # Add node to graph
            nodes[node.name] = create_pregel_node(node, fn_map)

        elif isinstance(node, CycleClass):
            number_of_cycles += 1

            iteration_key = f"{node.name}.iteration_counter"
            cycle_iteration_keys.append(iteration_key)
            field_names[iteration_key] = BinaryOperatorAggregate(int, operator.add)
            in_cycle_node_output_names = set()
            cycle_nodes_outputs_to_clean = set()
            for out in node.outputs:
                field_names[node.name + "." + out.name] = LastValue(Any)
            for inp in node.inputs:
                field_names[node.name + "." + inp.name] = LastValue(Any)
            for in_cycle_node in node.nodes:
                for out in in_cycle_node.outputs:
                    in_cycle_node_output_names.add(in_cycle_node.name + "." + out.name)
                    if out.reducer == Reducer.APPEND:
                        field_names[in_cycle_node.name + "." + out.name] = BinaryOperatorAggregate(list[Any], operator.add)  # noqa: E501
                        # we don't want to clear aggregated values
                    else:
                        field_names[in_cycle_node.name + "." + out.name] = LastValue(Any)
                        cycle_nodes_outputs_to_clean.add(in_cycle_node.name + "." + out.name)

            # Handle cycle as a composite node with 2 special nodes: start and guard
            cycle_start_name = f"{node.name}_cycle_start"
            cycle_guard_name = f"{node.name}_cycle_guard"

            # Add cycle start node
            nodes[cycle_start_name] = create_cycle_start_pregel_node(node, iteration_key, list(cycle_nodes_outputs_to_clean), in_cycle_node_output_names)

            # Extract dependencies for the cycle
            deps = extract_dependencies(node.inputs + node.outputs, workflow_inputs)
            deps.add(cycle_guard_name)
            node_dependencies[cycle_start_name] = deps

            cycle_inputs_and_outputs = [node.name + "." + inp.name for inp in node.inputs] + [node.name + "." + out.name for out in node.outputs]
            nodes_outputs = []
            for cycle_node in node.nodes:
                deps = extract_in_cycle_dependencies(cycle_node.inputs, set(cycle_inputs_and_outputs), cycle_start_name)
                node_dependencies[cycle_node.name] = deps
                nodes[cycle_node.name] = create_pregel_node(cycle_node, fn_map)
                nodes_outputs.extend([cycle_node.name + "." + out.name for out in cycle_node.outputs])

            # Add cycle guard node
            nodes[cycle_guard_name] = make_cycle_guard_pregel_node(node, iteration_key, in_cycle_node_output_names)
            node_dependencies[cycle_guard_name] = set([cycle_start_name])

    # Create dependency-based edges
    for node_name, deps in node_dependencies.items():
        for dep in deps:
            all_dependencies.add(dep)

    output_nodes = set(node_dependencies.keys()) - all_dependencies
    if len(output_nodes) > 1:
        raise ValueError(f"There is more than one output node detected: {output_nodes}")
    if len(output_nodes) == 0:
        raise ValueError(f"There is no output node detected in {workflow.name}")

    app = Pregel(
        nodes=nodes,
        channels=field_names,
        input_channels=list(workflow_inputs),
        output_channels=[out.default_value for out in workflow.outputs if out.default_value is not None] + cycle_iteration_keys,
        checkpointer=checkpointer,
    )

    return app
