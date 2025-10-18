# Demand Evaluation Workflow

## Overview

This workflow evaluates product demand using LLM-simulated personas with diverse demographics. It implements the core methodology from the research paper [LLMs Reproduce Human Purchase Intent via Semantic Similarity Elicitation of Likert Ratings.](https://arxiv.org/pdf/2510.08338)

The workflow generates synthetic personas with varying demographic attributes (age, gender, income, education, location, lifestyle, values) and has each persona evaluate a product to provide purchase intent ratings on a 5-point Likert scale. The results are aggregated to provide comprehensive demand metrics and demographic insights.

## Research Foundation & Methodology

This workflow faithfully implements the key innovation from the research paper:

### Semantic Similarity Approach (NOT Direct Rating)

Instead of asking LLMs for numeric ratings directly (which can be biased), the workflow:

1. **Asks for TEXTUAL purchase intent**: The LLM describes their purchase intent in natural language (e.g., "I would very likely purchase this product because...")

2. **Vectorizes the response**: Uses embedding models (like Nomic via Ollama) to convert the text into a vector representation

3. **Compares to golden intents**: Calculates cosine similarity between the response and 5 pre-defined "golden" intent descriptions that represent each point on the Likert scale

4. **Computes expected rating**: Uses a probability-based approach:
   - Calculates similarities to all 5 golden intents
   - Subtracts minimum similarity to shift the range
   - Normalizes to create a probability distribution (PMF - Probability Mass Function)
   - Computes expected rating as weighted sum: rating = Σ(rating_i × probability_i)
   - Returns a continuous value (e.g., 3.6) rather than discrete integers
   - Individual PMFs are stored for each persona evaluation
   - Mean PMF is calculated across all personas to show overall distribution

### Why This Approach Works

- **Reduces numeric bias**: LLMs can have biases when directly outputting numbers
- **Captures semantic meaning**: Similar textual expressions map to similar ratings
- **More realistic**: Mirrors how humans actually express purchase intent in surveys
- **Validated by research**: Produces distributions matching real human survey data

### Golden Intent Descriptions

The workflow uses a comprehensive set of canonical descriptions for the 5-point scale. Each rating level has **5 variations** representing different reasoning patterns:

1. **Need-based reasoning**: "Do I need it?"
2. **Fit-based reasoning**: "Is it right for me?"
3. **Price-based reasoning**: "Is it worth the cost?"
4. **Feature-based reasoning**: "Does it have what I want?"
5. **Interest-based reasoning**: "Does it appeal to me?"

For example, Rating 1 (Definitely NOT) includes:
- "I would definitely not buy it as I don't need it at all"
- "I would definitely not buy it because it's not a good fit for me"
- "I would definitely not buy it as it's too expensive for what it offers"
- "I would definitely not buy it as it lacks important features I need"
- "I would definitely not buy it as I'm just not interested in this type of product"

Each rating level (1-5) has similar variations across these 5 reasoning dimensions, providing a more robust semantic similarity matching that captures diverse ways people express purchase intent.

### Example Calculation

For a response: *"I'm somewhat interested; if the price is fair, I'd try it."*

1. Cosine similarities to 5 anchors: [0.82, 0.86, 0.90, 0.95, 0.88]
2. Subtract min (0.82): [0.00, 0.04, 0.08, 0.13, 0.06]
3. Normalize: p ≈ [0.00, 0.14, 0.27, 0.43, 0.16]
4. Expected rating = 1×0 + 2×0.14 + 3×0.27 + 4×0.43 + 5×0.16 ≈ **3.6**

This probability-weighted approach provides more nuanced ratings than simple "best match" selection.

## Workflow Architecture

### Inputs
- `product_name` (String): Name of the product to evaluate
- `product_description` (String): Detailed description of the product
- `num_personas` (Int): Number of synthetic personas to generate (recommended: 20-100)
- `report_path` (String): Directory path where the Markdown report will be saved

### Outputs
- `metrics` (DemandMetrics): Aggregated demand metrics including:
  - Mean and standard deviation of purchase intent
  - Distribution of high/medium/low intent percentages
  - Mean likelihood to recommend
  - Demographic insights (purchase intent by age, income, location)
  - Total number of personas evaluated
  - **Mean PMF** (Probability Mass Function): Average probability distribution across all personas for each rating level (1-5)
- `evaluations` (List<PersonaEvaluation>): Individual evaluations from each persona, including:
  - Individual PMF (probability distribution for each rating level)

**Note:** A comprehensive Markdown report is automatically generated and saved to `report_path` with a timestamped filename.

### Workflow Steps

1. **GeneratePersonas**: Creates diverse synthetic personas with demographic attributes
   - Generates personas across age ranges: 18-25, 26-35, 36-45, 46-55, 56-70
   - Varies gender, income level, education, and location
   - Uses LLM to generate realistic occupation, lifestyle, and values

2. **CalculateGoldenEmbeddings**: Pre-calculates embeddings for all golden intent variations
   - Computes embeddings for all 25 golden intent descriptions (5 variations × 5 rating levels)
   - Averages the 5 variations for each rating level to create 5 anchor embeddings
   - **Runs once** before the evaluation loop for efficiency
   - These pre-calculated embeddings are passed to the cycle and reused for all persona evaluations

3. **EvaluationLoop**: Iterates through each persona to evaluate the product
   - **ProcessNextPersona**: Manages iteration through personas
   - **GetPurchaseIntent**: Gets **textual purchase intent** from each persona
     - Uses LLM to elicit natural language description of purchase intent (not numeric)
     - Avoids rating bias by asking for words instead of numbers
   - **CalculatePersonaMetrics**: Converts intent text to rating using semantic similarity
     - Converts text to vector using **Nomic embeddings**
     - Calculates **cosine similarity** to the 5 pre-calculated golden anchor embeddings
     - Computes **expected rating** (1-5 continuous scale) using probability-weighted approach
   - **CollectEvaluations**: Accumulates evaluation results with similarity scores

4. **AnalyzeDemand**: Computes aggregate metrics and demographic insights
   - Calculates mean, standard deviation, and distribution statistics
   - Breaks down purchase intent by demographic segments
   - Identifies high-intent segments for targeted marketing

5. **SaveReport**: Generates comprehensive Markdown report
   - Creates timestamped report file: `demand_eval_ProductName_YYYYMMDD_HHMMSS.md`
   - Includes product details, metrics, demographic insights, and recommendations
   - Automatic demand assessment (Strong 🟢 / Moderate 🟡 / Low 🔴)
   - Actionable recommendations tailored to demand level
   - Saved to specified `report_path` directory

## Setup

### Environment Variables

No environment variables are strictly required. The workflow uses local Ollama models by default.

Optional:
- Set `model_type=openai` in config to use OpenAI models (requires `OPENAI_API_KEY`)

### Dependencies

Install via:
```bash
cd workflow_definitions/demand_eval_workflow
pip install -r requirements.txt
```

Key dependencies:
- `langchain-ollama`: For local LLM inference
- `langchain-openai`: For OpenAI models (optional)
- `pydantic`: For data validation
- `numpy`: For cosine similarity calculations

### LLM Models Required

**Text Generation Model** (default: `gemma3:12b`)

Install with:
```bash
ollama pull gemma3:12b
```

Recommended alternatives:
- `qwen3:8b` - Faster, good quality
- `llama3:8b` - Good general-purpose model
- `gpt-4` - Via OpenAI (requires API key)

**Embedding Model** (default: `nomic-embed-text`)

Install with:
```bash
ollama pull nomic-embed-text
```

This is crucial for the semantic similarity matching. Nomic provides high-quality embeddings optimized for text similarity tasks.

## Usage

### From CLI (Without Apps)

Run the workflow directly from the command line without starting backend/workers:

```bash
# From repo root
make run-workflow \
  WORKFLOW=demand_eval_workflow \
  FUNCS=workflow_definitions.demand_eval_workflow.demand_eval_workflow \
  PARAMS="product_name='Smart Water Bottle' product_description='AI-powered hydration tracking bottle with app connectivity' num_personas=20 report_path='./reports'"
```

**More examples:**

```bash
# Evaluate a SaaS product with 30 personas
make run-workflow \
  WORKFLOW=demand_eval_workflow \
  FUNCS=workflow_definitions.demand_eval_workflow.demand_eval_workflow \
  PARAMS="product_name='Project Management Tool' product_description='Cloud-based collaboration platform for remote teams' num_personas=30 report_path='./reports'"

# Evaluate a consumer electronics product with 50 personas
make run-workflow \
  WORKFLOW=demand_eval_workflow \
  FUNCS=workflow_definitions.demand_eval_workflow.demand_eval_workflow \
  PARAMS="product_name='Wireless Earbuds' product_description='Noise-canceling earbuds with 24-hour battery life' num_personas=50 report_path='./reports'"

# Quick test with fewer personas
make run-workflow \
  WORKFLOW=demand_eval_workflow \
  FUNCS=workflow_definitions.demand_eval_workflow.demand_eval_workflow \
  PARAMS="product_name='Smart Speaker' product_description='Voice-activated assistant with premium sound' num_personas=10 report_path='./reports'"
```

**Note:** This runs the workflow synchronously and outputs results to the terminal. For production use with multiple workflows, use the API approach below.

### Via Workflow Runner API

1. Start the backend and workers:
```bash
make run_wirl_apps
```

2. Use the API at `http://localhost:8000/api/docs` to:
   - List templates: `GET /templates`
   - Start workflow: `POST /workflows/start`
   - Check status: `GET /workflows/{workflow_run_id}`

Example API call:
```bash
curl -X POST "http://localhost:8000/api/workflows/start" \
  -H "Content-Type: application/json" \
  -d '{
    "template_name": "demand_eval_workflow",
    "inputs": {
      "product_name": "Smart Water Bottle",
      "product_description": "AI-powered hydration tracking bottle with app connectivity",
      "num_personas": 30,
      "report_path": "/absolute/path/to/reports"
    }
  }'
```

### Generated Report

After the workflow completes, a comprehensive Markdown report is automatically generated with the following sections:

#### Report Filename
`demand_eval_ProductName_20251015_083806.md`

Reports include timestamp to track multiple evaluations over time.

#### Report Contents

1. **Product Information**: Name, description, number of personas evaluated
2. **Executive Summary**: Mean intent, standard deviation, and high-intent percentage
3. **Probability Distribution (Mean PMF)**: Table showing average probability for each rating level across all personas
4. **Demographic Insights**: Sorted table showing purchase intent by segment with highest/lowest
5. **Recommendations**: Actionable next steps based on demand level
6. **Next Steps**: Concrete actions for validation and iteration

**Example Report Excerpt:**

```markdown
# Demand Evaluation Report: Smart Water Bottle

**Generated:** 2025-10-15 08:38:06

## Executive Summary

- **Mean Purchase Intent:** 4.20 / 5.0
- **Standard Deviation:** 0.80

### Probability Distribution (Mean PMF)

Average probability across all personas for each rating level:

| Rating | Description | Mean Probability |
|--------|-------------|------------------|
| 1 - Would NOT | Would not buy (no need, bad fit, too expensive...) | 0.050 (5.0%) |
| 2 - Probably NOT | Probably would not buy (limited need, poor fit...) | 0.080 (8.0%) |
| 3 - Might Buy | Might buy depending on circumstances | 0.150 (15.0%) |
| 4 - Probably Would | Would probably buy (seems like good fit...) | 0.350 (35.0%) |
| 5 - Would Buy | Would buy (good fit for needs, great value...) | 0.370 (37.0%) |

*Probabilities show semantic similarity to each rating anchor across all persona responses.*

---

## Demographic Insights

Purchase intent by segment (sorted highest to lowest):

| Segment | Mean Intent |
|---------|-------------|
| Income High | 4.80 |
| Age 18-35 | 4.50 |
| Location Urban | 4.40 |
...
```

### Workflow Output (JSON)

**Metrics Summary:**
```json
{
  "metrics": {
    "mean_purchase_intent": 3.8,
    "std_purchase_intent": 0.9,
    "high_intent_percentage": 60.0,
    "medium_intent_percentage": 30.0,
    "low_intent_percentage": 10.0,
    "demographic_insights": {
      "age_18-35": 4.2,
      "age_36-55": 3.7,
      "age_56+": 3.3,
      "income_Low": 2.9,
      "income_Medium": 3.8,
      "income_High": 4.5,
      "location_Urban": 4.0,
      "location_Suburban": 3.7,
      "location_Rural": 3.5
    },
    "total_personas": 30,
    "mean_pmfs": [0.10, 0.15, 0.20, 0.30, 0.25]
  }
}
```

**Sample Individual Evaluation:**
```json
{
  "persona": {
    "age": 32,
    "gender": "Female",
    "income_level": "High",
    "occupation": "Product Manager"
  },
  "intent_text": "I would very likely purchase this product. As someone who values innovation and convenience, this Smart Water Bottle fits perfectly into my active lifestyle. The AI-powered features would help me stay on top of my hydration goals.",
  "purchase_intent": 4.3,
  "similarity_score": 0.87,
  "pmfs": [0.05, 0.10, 0.15, 0.35, 0.35]
}
```

**Note:**
- Ratings are continuous values (e.g., 4.3) computed as probability-weighted expected values, not integers
- The `similarity_score` (0.87) represents the maximum similarity to any golden intent anchor
- Higher similarity scores indicate clearer, more confident intent expressions
- The `pmfs` array shows the probability distribution over all 5 rating levels (sums to 1.0)
- Mean PMF is calculated by averaging individual PMFs across all personas, showing the overall population distribution

## Interpretation

### Purchase Intent Scale (5-point continuous)
- **< 2.5**: Definitely would NOT purchase (Low intent)
- **2.5 - 4.0**: Neutral to somewhat interested (Medium intent)
- **≥ 4.0**: Likely to definitely purchase (High intent)

Note: Ratings are continuous values (e.g., 3.6) computed using probability-weighted semantic similarity, providing more nuanced insights than discrete integer ratings.

### Key Metrics

- **Mean Purchase Intent**: Overall average interest (target: >3.5 for strong demand on 5-point scale)
- **High Intent %**: Percentage of personas likely to purchase (target: >50%)
- **Demographic Insights**: Identifies which segments show strongest interest
  - Use to target marketing and product positioning
  - Identifies potential early adopters vs. laggards

### Use Cases

1. **Product Concept Testing**: Validate new product ideas before development
   - Generate comprehensive reports to share with stakeholders
   - Compare multiple product variations by running separate evaluations

2. **Market Segmentation**: Identify which demographics to target
   - Reports automatically highlight highest-intent segments
   - Use demographic insights table to prioritize marketing spend

3. **Pricing Strategy**: Correlate price sensitivity with purchase intent
   - Track evaluations over time with timestamped reports
   - A/B test different price points in product descriptions

4. **Marketing Copy**: Use persona intent descriptions to craft compelling messages
   - Review individual evaluations for qualitative insights
   - Extract common themes from high-intent persona intent text

5. **Feature Prioritization**: Test variations to see which features resonate
   - Generate reports for different feature sets
   - Compare demand metrics across product configurations

6. **Stakeholder Communication**: Professional reports for decision-making
   - Markdown format easy to convert to PDF or presentations
   - Actionable recommendations included automatically
   - Visual indicators (🟢🟡🔴) for quick assessment

## Testing

Run tests:
```bash
# From repo root
make test-workflow WORKFLOW=demand_eval_workflow

# Or directly with pytest
cd workflow_definitions/demand_eval_workflow
pytest tests/
```

Tests include:
- Unit tests for each function
- Mocked LLM responses and embeddings
- Integration test for full workflow

## Configuration Options

Customize behavior via `const` blocks in the WIRL file or input parameters:

### Input Parameters
- `product_name`: Product name (appears in report title and filename)
- `product_description`: Detailed description for persona evaluation
- `num_personas`: Number of personas to generate (20-100 recommended)
- `report_path`: Directory for saving reports (created if doesn't exist)

### GeneratePersonas Node
- `model`: LLM model to use (default: "gemma3:12b")
- `temperature`: Creativity level (default: 0.8 for diversity)
- `model_type`: "ollama" or "openai"

### GetPurchaseIntent Node
- `model`: LLM model for text generation (default: "gemma3:12b")
- `temperature`: Response variability (default: 0.7)
- `model_type`: "ollama" or "openai"

### CalculatePersonaMetrics Node
- `embedding_model`: Model for vectorization (default: "nomic-embed-text")

### SaveReport Node
No configuration needed - automatically generates reports based on metrics

## Limitations & Considerations

1. **Simulation Fidelity**: LLM personas approximate human behavior but may not capture all nuances
2. **Model Dependency**: Results vary by LLM model quality and training data
3. **Embedding Quality**: Nomic embeddings work well for English; other languages may need different models
4. **Cultural Context**: Ensure the LLM is trained on relevant cultural contexts
5. **Sample Size**: Larger persona counts (50-100+) provide more reliable statistics
6. **Validation**: Consider running pilot studies with real users to validate synthetic results
7. **Golden Intent Calibration**: The 25 golden intent variations (5 per rating level) are calibrated for general product evaluation covering different reasoning patterns (need, fit, price, features, interest); you may customize them for specific domains or add more variations
8. **Continuous Ratings**: Ratings are computed as expected values (e.g., 3.6), providing more granular insights than discrete integers
9. **Report Storage**: Reports are saved locally; ensure adequate disk space and appropriate file permissions for `report_path`
10. **Timestamp Collisions**: Running multiple evaluations in the same second may need manual handling
11. **Streamlined Data Model**: This implementation focuses on core purchase intent metric only, without additional attributes like price sensitivity or recommendation likelihood

## Research Citation

If using this workflow for research, consider citing the foundational work:
> "LLMs Reproduce Human Purchase Intent via Semantic Similarity Elicitation of Likert Ratings"

## Future Enhancements

Potential extensions:
- **A/B testing**: Batch compare multiple product variations in single workflow
- **Temporal dynamics**: Simulate adoption curves over time
- **Social influence**: Model word-of-mouth and network effects
- **Competitive analysis**: Compare against alternative products in one report
- **Sentiment analysis**: Extract qualitative themes from intent descriptions
- **Human-in-the-loop**: Allow manual review/adjustment of personas
- **Report formats**: Export to PDF, HTML, or PowerPoint
- **Interactive dashboards**: Web-based visualization of metrics
- **Trend analysis**: Compare reports over time to track product evolution
- **Custom templates**: Allow custom report sections/branding

## Support

For issues or questions:
1. Check existing workflow tests for examples
2. Review AGENTS.md for development guidelines
3. Verify LLM models are properly installed (`ollama list`)
4. Check logs for detailed error messages
5. Ensure `report_path` directory is writable
6. Review generated reports in `report_path` directory

## Report Tips

**Best Practices:**
- Use descriptive product names (they appear in report titles)
- Store reports in version control for historical tracking
- Create dated subdirectories (e.g., `reports/2025-10/`) for organization
- Share reports with stakeholders in Markdown or convert to PDF
- Compare reports across product iterations to track improvements
- Archive reports with product version tags for reference

**Report Organization Example:**
```
reports/
├── 2025-10/
│   ├── demand_eval_Smart_Water_Bottle_v1_20251015_083806.md
│   ├── demand_eval_Smart_Water_Bottle_v2_20251015_143022.md
│   └── demand_eval_Fitness_Tracker_20251016_091234.md
└── 2025-11/
    └── demand_eval_Smart_Watch_Pro_20251101_100000.md
```
