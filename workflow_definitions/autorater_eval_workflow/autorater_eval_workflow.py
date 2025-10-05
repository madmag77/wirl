"""
Pure functions for AutoraterEvalWorkflow.
Evaluates autorater performance on HotpotQA dataset.
"""

import json
import random
from typing import Dict, List

from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)

from .autorater import autorate


def load_dataset(dataset_path: str, sample_size: int, config: dict) -> dict:
    """
    Load HotpotQA dataset and prepare items for evaluation.

    Args:
        dataset_path: Path to HotpotQA JSON file
        sample_size: Number of samples to evaluate
        config: Runner config

    Returns:
        dict with dataset_items (list) and total_samples (int)
    """
    # Ensure sample_size is an integer (in case it comes as a string from inputs)
    sample_size = int(sample_size)

    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Shuffle data for random sampling
    random.seed()
    random.shuffle(data)

    # Define categories for evaluation
    categories = [
        "FullGold",
        "OnlyDistractor",
        "HalfGold",
        "FullGoldAndDistractors",
        "HalfGoldAndDistractors",
    ]

    # Distribute samples across categories
    samples_per_category = sample_size // len(categories)
    remaining_samples = sample_size % len(categories)

    # Prepare dataset items with category assignments
    dataset_items = []
    data_idx = 0

    for i, category in enumerate(categories):
        category_samples = samples_per_category + (1 if i < remaining_samples else 0)

        for _ in range(category_samples):
            if data_idx >= len(data):
                break

            item = data[data_idx]
            dataset_items.append(
                {
                    "question": item["question"],
                    "context": item.get("context", []),
                    "supporting_facts": item.get("supporting_facts", []),
                    "category": category,
                }
            )
            data_idx += 1

    return {
        "dataset_items": dataset_items,
        "total_samples": len(dataset_items),
    }


def _pick_paragraphs(item: Dict, category: str) -> str:
    """
    Pick paragraphs based on category.

    Args:
        item: Dataset item with context and supporting facts
        category: Category determining which paragraphs to include

    Returns:
        Concatenated paragraphs as a string
    """
    gold_titles = {title for title, _ in item.get("supporting_facts", [])}

    # Separate gold and distractor paragraphs
    gold_paragraphs = []
    distractor_paragraphs = []

    for title, sentences in item.get("context", []):
        paragraph = " ".join(sentences)
        if title in gold_titles:
            gold_paragraphs.append(paragraph)
        else:
            distractor_paragraphs.append(paragraph)

    if category == "FullGold":
        return "\n".join(gold_paragraphs)

    elif category == "OnlyDistractor":
        return "\n".join(distractor_paragraphs)

    elif category == "HalfGold":
        return random.choice(gold_paragraphs) if gold_paragraphs else ""

    elif category == "FullGoldAndDistractors":
        selected_paragraphs = gold_paragraphs.copy()
        selected_distractors = random.sample(
            distractor_paragraphs, min(3, len(distractor_paragraphs))
        )
        selected_paragraphs.extend(selected_distractors)
        return "\n".join(selected_paragraphs)

    elif category == "HalfGoldAndDistractors":
        selected_paragraphs = []
        if gold_paragraphs:
            selected_paragraphs.append(random.choice(gold_paragraphs))
        selected_distractors = random.sample(
            distractor_paragraphs, min(2, len(distractor_paragraphs))
        )
        selected_paragraphs.extend(selected_distractors)
        return "\n".join(selected_paragraphs)

    else:
        raise ValueError(f"Unknown category: {category}")


def process_next_sample(
    items: List[Dict] | None, initial_items: List[Dict], config: dict
) -> dict:
    """
    Process the next sample from the dataset.

    Args:
        items: Remaining items from previous iteration (None on first iteration)
        initial_items: Full list of items from LoadDataset
        config: Runner config

    Returns:
        dict with current_item, remaining_items, and no_items_left
    """
    # Use initial_items on first iteration, otherwise use remaining items
    current_list = items if items is not None else initial_items

    if not current_list or len(current_list) == 0:
        return {
            "current_item": {},
            "remaining_items": [],
            "no_items_left": True,
        }

    # Take the first item and return the rest
    current_item = current_list[0]
    remaining = current_list[1:]

    return {
        "current_item": current_item,
        "remaining_items": remaining,
        "no_items_left": False,
    }


def autorate_item(item: Dict, config: dict) -> dict:
    """
    Autorate a single item using the autorater.

    Args:
        item: Dataset item with question, context, supporting_facts, and category
        config: Runner config with model, model_type, and base_url

    Returns:
        dict with result containing question, context, label, and category
    """
    # Pick paragraphs based on category
    context = _pick_paragraphs(item, item["category"])

    # Get autorater parameters from config
    model = config.get("model", "gemma3:12b")
    model_type = config.get("model_type", "ollama")
    base_url = config.get("base_url", "http://localhost:1234/v1")

    # Call autorater
    label = autorate(
        item["question"], context, model=model, model_type=model_type, base_url=base_url
    )

    return {
        "result": {
            "question": item["question"],
            "context": context,
            "autorater_label": label,
            "dataset_label": item["category"],
        }
    }


def collect_results(
    result: Dict | None,
    remaining_items: List[Dict] | None,
    no_items_left: bool | None,
    config: dict,
) -> dict:
    """
    Collect evaluation results.

    Args:
        result: Evaluation result from AutorateItem (None if no items left)
        remaining_items: Remaining items to process (None on first call)
        no_items_left: Flag indicating if there are no more items
        config: Runner config

    Returns:
        dict with is_done flag and results list (accumulated via append reducer)
    """
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


def analyze_results(results: List[Dict], config: dict) -> dict:
    """
    Analyze autorater evaluation results and calculate metrics.

    Ground truth: context is sufficient only for FullGold and FullGoldAndDistractors.

    Args:
        results: List of evaluation results from the cycle
        config: Runner config

    Returns:
        dict with metrics including precision, recall, accuracy, f1, and confusion matrix
    """
    if not results or len(results) == 0:
        return {
            "metrics": {
                "precision": 0.0,
                "recall": 0.0,
                "accuracy": 0.0,
                "f1_score": 0.0,
                "true_positives": 0,
                "false_positives": 0,
                "true_negatives": 0,
                "false_negatives": 0,
                "total_samples": 0,
                "category_breakdown": {},
            }
        }

    # Define sufficient categories
    sufficient_categories = {"FullGold", "FullGoldAndDistractors"}

    # Prepare ground truth and predictions
    y_true = []
    y_pred = []
    category_breakdown = {}

    for result in results:
        dataset_label = result.get("dataset_label", "")
        autorater_label = result.get("autorater_label", "")

        # Ground truth: is the category sufficient?
        ground_truth_sufficient = dataset_label in sufficient_categories
        y_true.append(ground_truth_sufficient)

        # Prediction: did autorater say sufficient?
        predicted_sufficient = autorater_label == "sufficient"
        y_pred.append(predicted_sufficient)

        # Track category breakdown
        if dataset_label not in category_breakdown:
            category_breakdown[dataset_label] = {
                "sufficient": 0,
                "insufficient": 0,
                "total": 0,
            }
        category_breakdown[dataset_label]["total"] += 1
        if autorater_label == "sufficient":
            category_breakdown[dataset_label]["sufficient"] += 1
        else:
            category_breakdown[dataset_label]["insufficient"] += 1

    # Calculate metrics
    precision = precision_score(y_true, y_pred, zero_division=0)
    recall = recall_score(y_true, y_pred, zero_division=0)
    accuracy = accuracy_score(y_true, y_pred)
    f1 = f1_score(y_true, y_pred, zero_division=0)

    # Create confusion matrix
    cm = confusion_matrix(y_true, y_pred)
    tn, fp, fn, tp = cm.ravel() if cm.size == 4 else (0, 0, 0, 0)

    return {
        "metrics": {
            "precision": float(precision),
            "recall": float(recall),
            "accuracy": float(accuracy),
            "f1_score": float(f1),
            "true_positives": int(tp),
            "false_positives": int(fp),
            "true_negatives": int(tn),
            "false_negatives": int(fn),
            "total_samples": len(results),
            "category_breakdown": category_breakdown,
        }
    }
