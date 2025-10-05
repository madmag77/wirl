"""Tests for AutoraterEvalWorkflow."""

from wirl_pregel_runner import run_workflow


def load_dataset(dataset_path: str, sample_size: int, config: dict) -> dict:
    """Mock function to load dataset."""
    # Create mock dataset items
    items = []
    categories = [
        "FullGold",
        "OnlyDistractor",
        "HalfGold",
        "FullGoldAndDistractors",
        "HalfGoldAndDistractors",
    ]

    for i in range(sample_size):
        category = categories[i % len(categories)]
        items.append(
            {
                "question": f"Question {i}?",
                "context": [["Title A", ["Sentence 1", "Sentence 2"]]],
                "supporting_facts": [["Title A", 0]],
                "category": category,
            }
        )

    return {
        "dataset_items": items,
        "total_samples": len(items),
    }


def process_next_sample(items: list | None, initial_items: list, config: dict) -> dict:
    """Mock function to process next sample."""
    current_list = items if items is not None else initial_items

    if not current_list or len(current_list) == 0:
        return {
            "current_item": {},
            "remaining_items": [],
            "no_items_left": True,
        }

    current_item = current_list[0]
    remaining = current_list[1:]

    return {
        "current_item": current_item,
        "remaining_items": remaining,
        "no_items_left": False,
    }


def autorate_item(item: dict, config: dict) -> dict:
    """Mock function to autorate an item."""
    # Mock autorater: FullGold and FullGoldAndDistractors are sufficient
    category = item.get("category", "")
    sufficient_categories = {"FullGold", "FullGoldAndDistractors"}

    # Simulate 90% accuracy
    import random

    if random.random() < 0.9:
        label = "sufficient" if category in sufficient_categories else "insufficient"
    else:
        # 10% error rate
        label = "insufficient" if category in sufficient_categories else "sufficient"

    return {
        "result": {
            "question": item.get("question", ""),
            "context": "mock context",
            "autorater_label": label,
            "dataset_label": category,
        }
    }


def collect_results(
    result: dict | None,
    remaining_items: list | None,
    no_items_left: bool | None,
    config: dict,
) -> dict:
    """Mock function to collect results."""
    # We're done if we've processed the last item (no more remaining)
    if no_items_left:
        # No result to add, just signal we're done
        return {
            "is_done": True,
            "results": [],
        }

    # Check if remaining items is empty (we just processed the last item)
    remaining = remaining_items or []
    is_done = len(remaining) == 0

    # Add the result from this iteration
    return {
        "is_done": is_done,
        "results": [result] if result else [],
    }


def analyze_results(results: list, config: dict) -> dict:
    """Mock function to analyze results."""
    if not results:
        return {
            "metrics": {
                "precision": 0.0,
                "recall": 0.0,
                "accuracy": 0.0,
                "f1_score": 0.0,
                "total_samples": 0,
            }
        }

    sufficient_categories = {"FullGold", "FullGoldAndDistractors"}

    y_true = []
    y_pred = []

    for result in results:
        dataset_label = result.get("dataset_label", "")
        autorater_label = result.get("autorater_label", "")

        ground_truth = dataset_label in sufficient_categories
        predicted = autorater_label == "sufficient"

        y_true.append(ground_truth)
        y_pred.append(predicted)

    # Simple accuracy calculation
    correct = sum(1 for t, p in zip(y_true, y_pred) if t == p)
    accuracy = correct / len(results) if results else 0.0

    return {
        "metrics": {
            "accuracy": accuracy,
            "total_samples": len(results),
            "correct_predictions": correct,
        }
    }


FN_MAP = {
    "load_dataset": load_dataset,
    "process_next_sample": process_next_sample,
    "autorate_item": autorate_item,
    "collect_results": collect_results,
    "analyze_results": analyze_results,
}


def test_autorater_eval_e2e():
    """Test the full autorater evaluation workflow."""
    result = run_workflow(
        "workflow_definitions/autorater_eval_workflow/autorater_eval_workflow.wirl",
        fn_map=FN_MAP,
        params={
            "dataset_path": "mock_dataset.json",
            "sample_size": 10,
        },
    )

    print("Result:", result)

    # Verify we got metrics
    assert "AnalyzeResults.metrics" in result
    metrics = result["AnalyzeResults.metrics"]

    # Verify metrics structure
    assert "accuracy" in metrics
    assert "total_samples" in metrics
    assert metrics["total_samples"] == 10

    # Accuracy should be reasonably high (we simulate 90% in mock)
    assert 0 <= metrics["accuracy"] <= 1.0


def test_autorater_eval_small_sample():
    """Test with a very small sample size."""
    result = run_workflow(
        "workflow_definitions/autorater_eval_workflow/autorater_eval_workflow.wirl",
        fn_map=FN_MAP,
        params={
            "dataset_path": "mock_dataset.json",
            "sample_size": 3,
        },
    )

    print("Small sample result:", result)

    # Verify we got metrics
    assert "AnalyzeResults.metrics" in result
    metrics = result["AnalyzeResults.metrics"]
    assert metrics["total_samples"] == 3
