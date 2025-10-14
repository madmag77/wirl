# Demand Evaluation Workflow

## Overview

This workflow evaluates product demand using LLM-simulated personas with diverse demographics. It implements the core methodology from the research paper "LLMs Reproduce Human Purchase Intent via Semantic Similarity Elicitation of Likert Ratings."

The workflow generates synthetic personas with varying demographic attributes (age, gender, income, education, location, lifestyle, values) and has each persona evaluate a product to provide purchase intent ratings on a 7-point Likert scale. The results are aggregated to provide comprehensive demand metrics and demographic insights.

## Research Foundation & Methodology

This workflow faithfully implements the key innovation from the research paper:

### Semantic Similarity Approach (NOT Direct Rating)

Instead of asking LLMs for numeric ratings directly (which can be biased), the workflow:

1. **Asks for TEXTUAL purchase intent**: The LLM describes their purchase intent in natural language (e.g., "I would very likely purchase this product because...")

2. **Vectorizes the response**: Uses embedding models (Nomic via Ollama) to convert the text into a vector representation

3. **Compares to golden intents**: Calculates cosine similarity between the response and 7 pre-defined "golden" intent descriptions that represent each point on the Likert scale

4. **Maps to rating**: Assigns the rating (1-7) of the golden intent with highest similarity

### Why This Approach Works

- **Reduces numeric bias**: LLMs can have biases when directly outputting numbers
- **Captures semantic meaning**: Similar textual expressions map to similar ratings
- **More realistic**: Mirrors how humans actually express purchase intent in surveys
- **Validated by research**: Produces distributions matching real human survey data

### Golden Intent Descriptions

The workflow uses these canonical descriptions for mapping:
- **1**: "I would definitely not purchase... no interest whatsoever"
- **2**: "I would probably not purchase... doesn't appeal to me"
- **3**: "I am somewhat unlikely... not convinced it's right for me"
- **4**: "I might or might not... neutral about it"
- **5**: "I would probably purchase... seems like a good fit"
- **6**: "I would very likely purchase... appeals strongly"
- **7**: "I would definitely purchase... exactly what I'm looking for"

## Workflow Architecture

### Inputs
- `product_name` (String): Name of the product to evaluate
- `product_description` (String): Detailed description of the product
- `num_personas` (Int): Number of synthetic personas to generate (recommended: 20-100)

### Outputs
- `metrics` (DemandMetrics): Aggregated demand metrics including:
  - Mean and standard deviation of purchase intent
  - Distribution of high/medium/low intent percentages
  - Mean likelihood to recommend
  - Demographic insights (purchase intent by age, income, location)
  - Total number of personas evaluated
- `evaluations` (List<PersonaEvaluation>): Individual evaluations from each persona

### Workflow Steps

1. **GeneratePersonas**: Creates diverse synthetic personas with demographic attributes
   - Generates personas across age ranges: 18-25, 26-35, 36-45, 46-55, 56-70
   - Varies gender, income level, education, and location
   - Uses LLM to generate realistic occupation, lifestyle, and values

2. **EvaluationLoop**: Iterates through each persona to evaluate the product
   - **ProcessNextPersona**: Manages iteration through personas
   - **EvaluateProduct**: Has each persona provide:
     - **Textual purchase intent** (not numeric) - describes their intent in natural language
     - Converts text to vector using **Nomic embeddings**
     - Calculates **cosine similarity** to golden intent descriptions
     - Maps to **1-7 Likert scale** based on best match
     - Also captures reasoning, price sensitivity, and recommendation intent
   - **CollectEvaluations**: Accumulates evaluation results with similarity scores

3. **AnalyzeDemand**: Computes aggregate metrics and demographic insights
   - Calculates mean, standard deviation, and distribution statistics
   - Breaks down purchase intent by demographic segments
   - Identifies high-intent segments for targeted marketing

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
  PARAMS="product_name='Smart Water Bottle' product_description='AI-powered hydration tracking bottle with app connectivity' num_personas=20"
```

**More examples:**

```bash
# Evaluate a SaaS product with 30 personas
make run-workflow \
  WORKFLOW=demand_eval_workflow \
  FUNCS=workflow_definitions.demand_eval_workflow.demand_eval_workflow \
  PARAMS="product_name='Project Management Tool' product_description='Cloud-based collaboration platform for remote teams' num_personas=30"

# Evaluate a consumer electronics product with 50 personas
make run-workflow \
  WORKFLOW=demand_eval_workflow \
  FUNCS=workflow_definitions.demand_eval_workflow.demand_eval_workflow \
  PARAMS="product_name='Wireless Earbuds' product_description='Noise-canceling earbuds with 24-hour battery life' num_personas=50"

# Quick test with fewer personas
make run-workflow \
  WORKFLOW=demand_eval_workflow \
  FUNCS=workflow_definitions.demand_eval_workflow.demand_eval_workflow \
  PARAMS="product_name='Smart Speaker' product_description='Voice-activated assistant with premium sound' num_personas=10"
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
      "num_personas": 30
    }
  }'
```

### Example Output

**Metrics Summary:**
```json
{
  "metrics": {
    "mean_purchase_intent": 5.2,
    "std_purchase_intent": 1.3,
    "high_intent_percentage": 65.0,
    "medium_intent_percentage": 25.0,
    "low_intent_percentage": 10.0,
    "mean_recommendation": 5.8,
    "demographic_insights": {
      "age_18-35": 5.8,
      "age_36-55": 5.0,
      "age_56+": 4.5,
      "income_Low": 3.9,
      "income_Medium": 5.1,
      "income_High": 6.2,
      "location_Urban": 5.7,
      "location_Suburban": 5.0,
      "location_Rural": 4.8
    },
    "total_personas": 30
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
  "purchase_intent": 6,
  "similarity_score": 0.87,
  "reasoning": "Aligns with my values for innovation and health tracking",
  "price_sensitivity": "Low",
  "likelihood_to_recommend": 7
}
```

Note: The `similarity_score` (0.87) indicates high confidence in the rating assignment - the persona's textual intent closely matched the golden intent description for rating 6.

## Interpretation

### Purchase Intent Scale
- **1-2**: Definitely would NOT purchase (Low intent)
- **3-4**: Somewhat unlikely to purchase (Medium intent)
- **5-7**: Likely to definitely purchase (High intent)

### Key Metrics

- **Mean Purchase Intent**: Overall average interest (target: >5.0 for strong demand)
- **High Intent %**: Percentage of personas likely to purchase (target: >50%)
- **Demographic Insights**: Identifies which segments show strongest interest
  - Use to target marketing and product positioning
  - Identifies potential early adopters vs. laggards

### Use Cases

1. **Product Concept Testing**: Validate new product ideas before development
2. **Market Segmentation**: Identify which demographics to target
3. **Pricing Strategy**: Correlate price sensitivity with purchase intent
4. **Marketing Copy**: Use persona reasoning to craft compelling messages
5. **Feature Prioritization**: Test variations to see which features resonate

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

Customize behavior via `const` blocks in the WIRL file:

### GeneratePersonas
- `model`: LLM model to use (default: "gemma3:12b")
- `temperature`: Creativity level (default: 0.8 for diversity)
- `model_type`: "ollama" or "openai"

### EvaluateProduct
- `model`: LLM model for text generation (default: "gemma3:12b")
- `temperature`: Response variability (default: 0.7)
- `embedding_model`: Model for vectorization (default: "nomic-embed-text")
- `model_type`: "ollama" or "openai"

## Limitations & Considerations

1. **Simulation Fidelity**: LLM personas approximate human behavior but may not capture all nuances
2. **Model Dependency**: Results vary by LLM model quality and training data
3. **Embedding Quality**: Nomic embeddings work well for English; other languages may need different models
4. **Cultural Context**: Ensure the LLM is trained on relevant cultural contexts
5. **Sample Size**: Larger persona counts (50-100+) provide more reliable statistics
6. **Validation**: Consider running pilot studies with real users to validate synthetic results
7. **Golden Intent Calibration**: The 7 golden intents are calibrated for general product evaluation; you may customize them for specific domains

## Research Citation

If using this workflow for research, consider citing the foundational work:
> "LLMs Reproduce Human Purchase Intent via Semantic Similarity Elicitation of Likert Ratings"

## Future Enhancements

Potential extensions:
- A/B testing: Compare multiple product variations
- Temporal dynamics: Simulate adoption curves over time
- Social influence: Model word-of-mouth and network effects
- Competitive analysis: Compare against alternative products
- Sentiment analysis: Extract qualitative themes from reasoning
- Human-in-the-loop: Allow manual review/adjustment of personas

## Support

For issues or questions:
1. Check existing workflow tests for examples
2. Review AGENTS.md for development guidelines
3. Verify LLM models are properly installed (`ollama list`)
4. Check logs for detailed error messages
