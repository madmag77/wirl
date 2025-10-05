# AutoraterEvalWorkflow

Evaluates the performance of an autorater on the HotpotQA dataset by testing its ability to determine if given context is sufficient to answer questions.

## Overview

This workflow:
1. Loads the HotpotQA dataset
2. Processes samples through different context categories:
   - **FullGold**: Only golden paragraphs (sufficient)
   - **OnlyDistractor**: Only distractor paragraphs (insufficient)
   - **HalfGold**: One gold paragraph (insufficient)
   - **FullGoldAndDistractors**: All gold + 3 distractors (sufficient)
   - **HalfGoldAndDistractors**: 1 gold + 2 distractors (insufficient)
3. Autorates each sample using an LLM to classify context as "sufficient" or "insufficient"
4. Analyzes results with precision, recall, accuracy, and F1 score

## Background: Sufficient Context

This workflow implements an autorater based on the concept of **sufficient context** from the paper ["Sufficient Context: A New Lens on Retrieval Augmented Generation Systems"](https://arxiv.org/pdf/2411.06037) (Joren et al., 2024).

### What is Sufficient Context?

In RAG (Retrieval Augmented Generation) systems, the quality of retrieved context is crucial. The paper introduces a novel way to evaluate context quality by asking: *Does the provided context contain enough information to answer the query?*

**Sufficient context** is defined as context that provides enough information to construct an answer to a query, independent of the ground truth answer. This classification helps analyze LLM behavior by revealing:

1. **When models fail despite having sufficient information** - Large models (Gemini 1.5 Pro, GPT-4o, Claude 3.5) tend to generate incorrect answers rather than abstaining when context is insufficient
2. **When models hallucinate with insufficient context** - Models often confidently produce incorrect answers even when the context doesn't support the answer
3. **When context is helpful even if not complete** - Models sometimes answer correctly even with insufficient context, suggesting they leverage parametric knowledge

### The Autorater

The sufficient context autorater uses an LLM to classify whether context is sufficient to answer a question. According to the paper, this autorater achieves **93% accuracy** when evaluated on benchmark datasets.

The autorater prompt (from Appendix C.1 of the paper) instructs the model to:
1. Generate step-by-step questions to evaluate the context
2. Check for assumptions implicit in the question
3. Consider any required mathematical calculations or arithmetic
4. Determine if the context is sufficient to **infer** the answer (not just contain related information)

### Key Findings from the Paper

- **35-62%** of the time, SOTA LLMs output correct responses even with insufficient context, showing they combine parametric knowledge with retrieval
- Larger models excel when context is sufficient but fail to abstain when it's not
- Smaller models hallucinate or abstain often, even with sufficient context
- The selective generation method using sufficient context signals improves accuracy by **2-10%** for Gemini, GPT, and Gemma

### Implementation in This Workflow

This workflow validates the autorater concept by testing it on HotpotQA with controlled context scenarios. By manipulating which paragraphs are included (gold vs. distractor), we create known sufficient/insufficient cases and measure the autorater's classification accuracy.

## Requirements

- HotpotQA dataset (download from [HotpotQA website](https://hotpotqa.github.io/))
- Ollama or LM Studio running with a model loaded
- Python dependencies (installed via `requirements.txt`)

## Setup

### 1. Install Dependencies

From the repo root:
```bash
make workflows-setup
```

### 2. Download HotpotQA Dataset

Download the dev distractor dataset:
```bash
mkdir -p data
cd data
wget http://curtis.ml.cmu.edu/datasets/hotpot/hotpot_dev_distractor_v1.json
```

### 3. Start Your LLM Server

**Option A: Ollama**
```bash
ollama serve
ollama pull gemma3:12b
```

**Option B: LM Studio**
1. Start LM Studio
2. Load a model
3. Start the local server (default: http://localhost:1234/v1)

## Running the Workflow

### Via Make (recommended)

```bash
make run-workflow \
  WORKFLOW=autorater_eval_workflow \
  FUNCS=workflow_definitions.autorater_eval_workflow.autorater_eval_workflow \
  PARAMS="dataset_path=data/hotpot_dev_distractor_v1.json sample_size=50"
```

### Via Python Runner

```bash
python -m wirl_pregel_runner.pregel_runner \
  --wirl-path workflow_definitions/autorater_eval_workflow/autorater_eval_workflow.wirl \
  --funcs workflow_definitions.autorater_eval_workflow.autorater_eval_workflow \
  --params '{"dataset_path": "data/hotpot_dev_distractor_v1.json", "sample_size": 50}'
```

## Configuration

The workflow uses constants defined in the `.wirl` file for the `AutorateItem` node:
- `model`: Model name (default: "gemma3:12b")
- `model_type`: "ollama" or "lmstudio" (default: "ollama")
- `base_url`: API base URL (default: "http://localhost:1234/v1")

To use a different model, edit the `const` section in `autorater_eval_workflow.wirl`.

## Inputs

- `dataset_path` (String): Path to HotpotQA JSON file
- `sample_size` (Int): Number of samples to evaluate (distributed across 5 categories)

## Outputs

- `metrics` (Object): Evaluation metrics including:
  - `precision`: Precision score
  - `recall`: Recall score
  - `accuracy`: Accuracy score
  - `f1_score`: F1 score
  - `true_positives`: Count of true positives
  - `false_positives`: Count of false positives
  - `true_negatives`: Count of true negatives
  - `false_negatives`: Count of false negatives
  - `total_samples`: Total number of samples evaluated
  - `category_breakdown`: Per-category statistics

## Testing

Run the workflow tests:
```bash
make test-workflow WORKFLOW=autorater_eval_workflow
```

Or directly:
```bash
cd workflow_definitions/autorater_eval_workflow
pytest tests/
```

## How It Works

### 1. Load Dataset
The `LoadDataset` node loads the HotpotQA JSON file and shuffles the data. It then distributes the requested `sample_size` evenly across the five evaluation categories.

### 2. Evaluation Loop (Cycle)
For each sample:
- `ProcessNextSample`: Gets the next item from the list
- `AutorateItem`: Picks appropriate paragraphs based on category and calls the autorater
- `CollectResults`: Accumulates results using the `(append)` reducer

The cycle continues until all samples are processed or `max_iterations` (100) is reached.

### 3. Analyze Results
The `AnalyzeResults` node calculates metrics by comparing:
- **Ground Truth**: FullGold and FullGoldAndDistractors are "sufficient", others are "insufficient"
- **Predictions**: What the autorater classified each sample as

## Notes

- The workflow processes samples sequentially to avoid rate limiting issues with LLM APIs
- Category distribution is balanced automatically
- Random seed is initialized from system entropy for reproducibility
- The autorater uses a detailed prompt with chain-of-thought reasoning

## Troubleshooting

**Issue: Slow execution**
- Reduce `sample_size` for faster testing
- Use a smaller/faster model
- Ensure your LLM server has adequate resources

**Issue: Connection errors**
- Verify Ollama or LM Studio is running
- Check the `base_url` matches your server configuration
- Test with: `curl http://localhost:1234/v1/models` (for LM Studio)

**Issue: Poor metrics**
- Try a larger model
- Increase `request_timeout` in `autorater.py`
- Check that the model supports JSON mode

## Example Output

```json
{
  "AnalyzeResults.metrics": {
    "precision": 0.892,
    "recall": 0.875,
    "accuracy": 0.880,
    "f1_score": 0.883,
    "true_positives": 18,
    "false_positives": 2,
    "true_negatives": 26,
    "false_negatives": 4,
    "total_samples": 50,
    "category_breakdown": {
      "FullGold": {"sufficient": 9, "insufficient": 1, "total": 10},
      "OnlyDistractor": {"sufficient": 1, "insufficient": 9, "total": 10},
      ...
    }
  }
}
```
