"""
Pure functions for DemandEvalWorkflow.
Evaluates product demand using LLM-simulated personas with diverse demographics.

Based on the research paper: "LLMs Reproduce Human Purchase Intent via
Semantic Similarity Elicitation of Likert Ratings"

Key methodology:
- Ask LLM for textual purchase intent (not numeric rating)
- Vectorize using embeddings (Nomic via Ollama)
- Compare to golden intent descriptions via cosine similarity
- Map to Likert scale based on best match
"""

import json
import random
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import numpy as np
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field


class Persona(BaseModel):
    """Represents a synthetic persona with demographic attributes."""

    age: int = Field(description="Age of the persona")
    gender: str = Field(description="Gender (e.g., Male, Female, Non-binary)")
    income_level: str = Field(description="Income level (Low, Medium, High)")
    education: str = Field(description="Education level")
    occupation: str = Field(description="Occupation or job role")
    location: str = Field(
        description="Geographic location (e.g., Urban, Suburban, Rural)"
    )
    lifestyle: str = Field(description="Lifestyle description")
    values: List[str] = Field(description="Core values and preferences")


class PersonaEvaluation(BaseModel):
    """Evaluation of a product by a persona."""

    persona: Persona = Field(description="The persona who evaluated the product")
    purchase_intent: float = Field(
        description="Purchase intent rating (1-5 Likert scale, computed as expected value)"
    )
    intent_text: str = Field(description="Textual description of purchase intent")
    reasoning: str = Field(description="Explanation for the rating")
    price_sensitivity: str = Field(description="Price sensitivity (Low, Medium, High)")
    likelihood_to_recommend: float = Field(
        description="Likelihood to recommend (1-5, expected value)"
    )
    similarity_score: float = Field(
        description="Maximum cosine similarity to golden intents", default=0.0
    )
    pmfs: List[float] = Field(
        description="Probability mass function of purchase intent"
    )


class DemandMetrics(BaseModel):
    """Aggregated demand metrics from all evaluations."""

    mean_purchase_intent: float = Field(description="Average purchase intent")
    std_purchase_intent: float = Field(
        description="Standard deviation of purchase intent"
    )
    high_intent_percentage: float = Field(description="Percentage with intent >= 4")
    medium_intent_percentage: float = Field(description="Percentage with intent 2.5-4")
    low_intent_percentage: float = Field(description="Percentage with intent < 2.5")
    mean_recommendation: float = Field(description="Average likelihood to recommend")
    demographic_insights: Dict[str, float] = Field(
        description="Purchase intent by demographic"
    )
    total_personas: int = Field(description="Total number of personas evaluated")
    mean_pmfs: List[float] = Field(
        description="Mean probability mass function of purchase intent"
    )


# Golden intent descriptions for 5-point Likert scale mapping
# These represent canonical descriptions of purchase intent levels
GOLDEN_INTENTS = {
    1: "I would definitely not purchase this product. It does not meet my needs at all and I have no interest in it whatsoever.",
    2: "I would probably not purchase this product. It doesn't really appeal to me and I don't see much value in it.",
    3: "I might or might not purchase this product. I'm neutral about it - it has both pros and cons that balance out.",
    4: "I would probably purchase this product. It seems like a good fit for my needs and I'm fairly interested in it.",
    5: "I would definitely purchase this product. It's exactly what I'm looking for and I'm highly interested in buying it.",
}


def cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    """
    Calculate cosine similarity between two vectors.

    Args:
        vec1: First vector
        vec2: Second vector

    Returns:
        Cosine similarity score (0 to 1)
    """
    dot_product = np.dot(vec1, vec2)
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return float(dot_product / (norm1 * norm2))


def generate_personas(num_personas: int, config: dict) -> dict:
    """
    Generate synthetic personas with diverse demographics using an LLM.

    Args:
        num_personas: Number of personas to generate
        config: Runner config with model and temperature

    Returns:
        dict with personas list
    """
    model = config.get("model", "gemma3:12b")
    temperature = config.get("temperature", 0.8)
    model_type = config.get("model_type", "ollama")

    # Initialize LLM
    if model_type == "openai":
        llm = ChatOpenAI(model=model, temperature=temperature)
    else:
        llm = ChatOllama(
            model=model,
            temperature=temperature,
            validate_model_on_init=True,
        )

    # Generate diverse personas
    personas = []

    # Define demographic diversity templates
    age_ranges = [(18, 25), (26, 35), (36, 45), (46, 55), (56, 70)]
    genders = ["Male", "Female", "Non-binary"]
    income_levels = ["Low", "Medium", "High"]
    education_levels = ["High School", "Bachelor's Degree", "Master's Degree", "PhD"]
    locations = ["Urban", "Suburban", "Rural"]

    for i in range(num_personas):
        # Randomly sample demographics for diversity
        age_range = random.choice(age_ranges)
        age = random.randint(age_range[0], age_range[1])
        gender = random.choice(genders)
        income = random.choice(income_levels)
        education = random.choice(education_levels)
        location = random.choice(locations)

        # Use LLM to generate occupation, lifestyle, and values
        prompt = f"""Generate a realistic persona profile for market research.

Demographics:
- Age: {age}
- Gender: {gender}
- Income Level: {income}
- Education: {education}
- Location: {location}

Please provide:
1. A specific occupation that fits these demographics
2. A brief lifestyle description (2-3 sentences)
3. 3-5 core values or preferences

Format as JSON with keys: occupation, lifestyle, values (as a list)
"""

        response = llm.invoke(prompt)
        content = getattr(response, "content", str(response))

        # Parse LLM response
        try:
            # Extract JSON from markdown code blocks if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            persona_details = json.loads(content)

            persona = Persona(
                age=age,
                gender=gender,
                income_level=income,
                education=education,
                occupation=persona_details.get("occupation", "Professional"),
                location=location,
                lifestyle=persona_details.get("lifestyle", "Active lifestyle"),
                values=persona_details.get(
                    "values", ["Quality", "Value", "Innovation"]
                ),
            )
            personas.append(persona)

        except (json.JSONDecodeError, KeyError):
            # Fallback to simple persona if parsing fails
            persona = Persona(
                age=age,
                gender=gender,
                income_level=income,
                education=education,
                occupation="Professional",
                location=location,
                lifestyle=f"{income} income {location.lower()} resident with {education.lower()}",
                values=["Quality", "Value", "Reliability"],
            )
            personas.append(persona)

    return {"personas": personas}


def process_next_persona(
    personas: List[Persona] | None, initial_personas: List[Persona], config: dict
) -> dict:
    """
    Process the next persona from the list.

    Args:
        personas: Remaining personas from previous iteration
        initial_personas: Full list of personas
        config: Runner config

    Returns:
        dict with current_persona, remaining_personas, and no_personas_left
    """
    current_list = personas if personas is not None else initial_personas

    if not current_list or len(current_list) == 0:
        return {
            "current_persona": {},
            "remaining_personas": [],
            "no_personas_left": True,
        }

    current_persona = current_list[0]
    remaining = current_list[1:]

    return {
        "current_persona": current_persona,
        "remaining_personas": remaining,
        "no_personas_left": False,
    }


def evaluate_product(
    persona: Persona, product_name: str, product_description: str, config: dict
) -> dict:
    """
    Have a persona evaluate a product using semantic similarity to golden intents.

    This implements the core methodology from the research paper:
    1. Ask LLM for TEXTUAL purchase intent (not a number)
    2. Vectorize the response using embeddings (Nomic via Ollama)
    3. Compare to golden intent descriptions via cosine similarity
    4. Map to Likert scale based on best match

    Args:
        persona: The persona evaluating the product
        product_name: Name of the product
        product_description: Detailed product description
        config: Runner config with model, temperature, and embedding_model

    Returns:
        dict with evaluation containing ratings and reasoning
    """
    model = config.get("model", "gemma3:12b")
    temperature = config.get("temperature", 0.7)
    model_type = config.get("model_type", "ollama")
    embedding_model = config.get("embedding_model", "nomic-embed-text")

    # Initialize LLM for text generation
    if model_type == "openai":
        llm = ChatOpenAI(model=model, temperature=temperature)
    else:
        llm = ChatOllama(
            model=model,
            temperature=temperature,
            validate_model_on_init=True,
        )

    # Initialize embeddings model (Nomic via Ollama)
    embeddings = OllamaEmbeddings(model=embedding_model)

    # Step 1: Ask for TEXTUAL purchase intent (not numeric rating)
    intent_prompt = f"""You are roleplaying as a market research participant with the following profile:

Age: {persona.age}
Gender: {persona.gender}
Income Level: {persona.income_level}
Education: {persona.education}
Occupation: {persona.occupation}
Location: {persona.location}
Lifestyle: {persona.lifestyle}
Core Values: {', '.join(persona.values)}

You are being asked to evaluate the following product:

Product: {product_name}
Description: {product_description}

Question: How likely would you be to purchase this product?

Please provide a detailed textual description of your purchase intent. Explain whether you would purchase this product and why, considering your demographic profile, lifestyle, and values. Do NOT provide a numeric rating - just describe your intent in words.

Be specific about your level of interest (e.g., "definitely would", "probably would", "might", "probably not", "definitely not").
"""

    intent_response = llm.invoke(intent_prompt)
    intent_text = getattr(intent_response, "content", str(intent_response))

    # Step 2: Get additional information (reasoning, price sensitivity, recommendation)
    details_prompt = f"""Based on your purchase intent: "{intent_text}"

Please provide:
1. A brief summary of your reasoning (why you feel this way about the product)
2. Your price sensitivity for this type of product (Low, Medium, or High)
3. A textual description of how likely you'd be to recommend this product to others with a similar profile

Format as JSON with keys: reasoning (string), price_sensitivity (string), recommendation_text (string)
"""

    details_response = llm.invoke(details_prompt)
    details_content = getattr(details_response, "content", str(details_response))

    # Parse details
    try:
        if "```json" in details_content:
            details_content = (
                details_content.split("```json")[1].split("```")[0].strip()
            )
        elif "```" in details_content:
            details_content = details_content.split("```")[1].split("```")[0].strip()

        details_data = json.loads(details_content)
        reasoning = details_data.get("reasoning", intent_text[:200])
        price_sensitivity = details_data.get("price_sensitivity", "Medium")
        recommendation_text = details_data.get("recommendation_text", intent_text)
    except (json.JSONDecodeError, KeyError):
        reasoning = intent_text[:200] if len(intent_text) > 200 else intent_text
        price_sensitivity = "Medium"
        recommendation_text = intent_text

    # Step 3: Vectorize the intent text
    try:
        intent_embedding = np.array(embeddings.embed_query(intent_text[:5000]))

        # Step 4: Calculate similarities to all golden intents and compute expected rating
        # Following the paper's methodology:
        # 1. Get cosine similarities to all anchors
        # 2. Subtract minimum to shift range
        # 3. Normalize to get probability distribution
        # 4. Compute expected rating as weighted sum

        similarities = []
        ratings = []
        for rating, golden_text in sorted(GOLDEN_INTENTS.items()):
            golden_embedding = np.array(embeddings.embed_query(golden_text))
            similarity = cosine_similarity(intent_embedding, golden_embedding)
            similarities.append(similarity)
            ratings.append(rating)

        # Subtract minimum similarity
        min_sim = min(similarities)
        shifted_sims = [s - min_sim for s in similarities]

        # Normalize to get probability distribution
        total = sum(shifted_sims)
        if total > 0:
            probabilities = [s / total for s in shifted_sims]
        else:
            # If all similarities are equal, use uniform distribution
            probabilities = [1.0 / len(similarities)] * len(similarities)

        # Compute expected rating as weighted sum
        purchase_intent = sum(r * p for r, p in zip(ratings, probabilities))
        best_similarity = max(similarities)  # For logging/debugging

        # Also process recommendation text using the same method
        recommendation_embedding = np.array(embeddings.embed_query(recommendation_text))
        rec_similarities = []

        for rating, golden_text in sorted(GOLDEN_INTENTS.items()):
            golden_embedding = np.array(embeddings.embed_query(golden_text))
            similarity = cosine_similarity(recommendation_embedding, golden_embedding)
            rec_similarities.append(similarity)

        # Apply same transformation for recommendation
        min_rec_sim = min(rec_similarities)
        shifted_rec_sims = [s - min_rec_sim for s in rec_similarities]

        total_rec = sum(shifted_rec_sims)
        if total_rec > 0:
            rec_probabilities = [s / total_rec for s in shifted_rec_sims]
        else:
            rec_probabilities = [1.0 / len(rec_similarities)] * len(rec_similarities)

        likelihood_to_recommend = sum(r * p for r, p in zip(ratings, rec_probabilities))

    except Exception:
        # Fallback if embeddings fail
        purchase_intent = 3.0  # Neutral on 5-point scale
        likelihood_to_recommend = 3.0
        best_similarity = 0.0
        probabilities = [1.0 / 5] * 5

    evaluation = PersonaEvaluation(
        pmfs=probabilities,
        persona=persona,
        purchase_intent=purchase_intent,
        intent_text=intent_text,
        reasoning=reasoning,
        price_sensitivity=price_sensitivity,
        likelihood_to_recommend=likelihood_to_recommend,
        similarity_score=best_similarity,
    )

    return {"evaluation": evaluation}


def collect_evaluations(
    evaluation: PersonaEvaluation | None,
    remaining_personas: List[Persona] | None,
    no_personas_left: bool | None,
    config: dict,
) -> dict:
    """
    Collect persona evaluations.

    Args:
        evaluation: Evaluation from EvaluateProduct
        remaining_personas: Remaining personas to process
        no_personas_left: Flag indicating if there are no more personas
        config: Runner config

    Returns:
        dict with is_done flag and evaluations list
    """
    if no_personas_left:
        return {
            "is_done": True,
            "evaluations": [],
        }

    remaining = remaining_personas or []
    is_done = len(remaining) == 0

    return {
        "is_done": is_done,
        "evaluations": [evaluation] if evaluation else [],
    }


def analyze_demand(
    evaluations: List[PersonaEvaluation], product_name: str, config: dict
) -> dict:
    """
    Analyze demand metrics from persona evaluations.

    Computes aggregate statistics and demographic insights as described
    in the research paper methodology.

    Args:
        evaluations: List of persona evaluations
        product_name: Name of the evaluated product
        config: Runner config

    Returns:
        dict with metrics containing demand analysis
    """
    if not evaluations or len(evaluations) == 0:
        return {
            "metrics": DemandMetrics(
                mean_pmfs=[],
                mean_purchase_intent=0.0,
                std_purchase_intent=0.0,
                high_intent_percentage=0.0,
                medium_intent_percentage=0.0,
                low_intent_percentage=0.0,
                mean_recommendation=0.0,
                demographic_insights={},
                total_personas=0,
            )
        }

    # Extract purchase intents and recommendations
    intents = [e.purchase_intent for e in evaluations]
    recommendations = [e.likelihood_to_recommend for e in evaluations]

    # Calculate mean PMF across all personas
    # mean_pmfs[i] = average probability for rating i+1 across all personas
    pmfs = [e.pmfs for e in evaluations]
    mean_pmfs = []
    num_ratings = len(pmfs[0]) if pmfs else 0
    for i in range(num_ratings):
        mean_pmfs.append(sum(pmf[i] for pmf in pmfs) / len(pmfs))

    # Calculate basic statistics
    mean_intent = sum(intents) / len(intents)
    variance = sum((x - mean_intent) ** 2 for x in intents) / len(intents)
    std_intent = variance**0.5
    mean_rec = sum(recommendations) / len(recommendations)

    # Calculate intent distribution (for 5-point scale)
    high_intent = sum(1 for i in intents if i >= 4)
    medium_intent = sum(1 for i in intents if 2.5 <= i < 4)
    low_intent = sum(1 for i in intents if i < 2.5)

    total = len(intents)
    high_pct = (high_intent / total) * 100
    medium_pct = (medium_intent / total) * 100
    low_pct = (low_intent / total) * 100

    # Demographic insights - purchase intent by key demographics
    demographic_insights = {}

    # Group by age brackets
    age_groups = {"18-35": [], "36-55": [], "56+": []}
    for e in evaluations:
        if e.persona.age <= 35:
            age_groups["18-35"].append(e.purchase_intent)
        elif e.persona.age <= 55:
            age_groups["36-55"].append(e.purchase_intent)
        else:
            age_groups["56+"].append(e.purchase_intent)

    for group, intents_list in age_groups.items():
        if intents_list:
            demographic_insights[f"age_{group}"] = sum(intents_list) / len(intents_list)

    # Group by income level
    income_groups = {"Low": [], "Medium": [], "High": []}
    for e in evaluations:
        if e.persona.income_level in income_groups:
            income_groups[e.persona.income_level].append(e.purchase_intent)

    for level, intents_list in income_groups.items():
        if intents_list:
            demographic_insights[f"income_{level}"] = sum(intents_list) / len(
                intents_list
            )

    # Group by location
    location_groups = {"Urban": [], "Suburban": [], "Rural": []}
    for e in evaluations:
        if e.persona.location in location_groups:
            location_groups[e.persona.location].append(e.purchase_intent)

    for loc, intents_list in location_groups.items():
        if intents_list:
            demographic_insights[f"location_{loc}"] = sum(intents_list) / len(
                intents_list
            )

    metrics = DemandMetrics(
        mean_pmfs=mean_pmfs,
        mean_purchase_intent=mean_intent,
        std_purchase_intent=std_intent,
        high_intent_percentage=high_pct,
        medium_intent_percentage=medium_pct,
        low_intent_percentage=low_pct,
        mean_recommendation=mean_rec,
        demographic_insights=demographic_insights,
        total_personas=total,
    )

    return {"metrics": metrics}


def save_report(
    product_name: str,
    product_description: str,
    num_personas: int,
    metrics: DemandMetrics,
    report_path: str,
    config: dict,
) -> dict:
    """
    Save demand evaluation report as a Markdown file with timestamp.

    Creates a comprehensive report containing product details, evaluation
    metrics, and demographic insights, saved with a timestamped filename.

    Args:
        product_name: Name of the evaluated product
        product_description: Description of the product
        num_personas: Number of personas that were evaluated
        metrics: Demand metrics from analysis
        report_path: Directory path where the report should be saved
        config: Runner config

    Returns:
        dict with final_metrics (pass-through of input metrics)
    """
    # Create timestamp for filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Sanitize product name for filename (replace spaces and special chars)
    safe_product_name = "".join(
        c if c.isalnum() or c in ("-", "_") else "_" for c in product_name
    )

    # Create filename
    filename = f"demand_eval_{safe_product_name}_{timestamp}.md"

    # Ensure report_path is a Path object and exists
    report_dir = Path(report_path)
    report_dir.mkdir(parents=True, exist_ok=True)

    # Full path to report file
    report_file = report_dir / filename

    # Generate markdown report
    report_content = f"""# Demand Evaluation Report: {product_name}

**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Product Information

**Product Name:** {product_name}

**Description:** {product_description}

**Number of Personas Evaluated:** {num_personas}

---

## Executive Summary

### Overall Purchase Intent

- **Mean Purchase Intent:** {metrics.mean_purchase_intent:.2f} / 5.0
- **Standard Deviation:** {metrics.std_purchase_intent:.2f}
- **Mean Recommendation Score:** {metrics.mean_recommendation:.2f} / 5.0

### Intent Distribution

| Category | Percentage |
|----------|-----------|
| **High Intent** (≥ 4.0) | {metrics.high_intent_percentage:.1f}% |
| **Medium Intent** (2.5 - 4.0) | {metrics.medium_intent_percentage:.1f}% |
| **Low Intent** (< 2.5) | {metrics.low_intent_percentage:.1f}% |

### Probability Distribution (Mean PMF)

The following table shows the average probability distribution across all personas for each rating level. This represents how likely personas are to have each specific purchase intent level based on semantic similarity to golden anchors:

"""

    # Add PMF table if available
    if metrics.mean_pmfs and len(metrics.mean_pmfs) == 5:
        report_content += "| Rating | Description | Mean Probability |\n"
        report_content += "|--------|-------------|------------------|\n"
        rating_labels = [
            "1 - Definitely NOT",
            "2 - Probably NOT",
            "3 - Neutral/Might",
            "4 - Probably Would",
            "5 - Definitely Would",
        ]
        for i, (label, prob) in enumerate(zip(rating_labels, metrics.mean_pmfs)):
            report_content += f"| {label} | {GOLDEN_INTENTS[i+1][:50]}... | {prob:.3f} ({prob*100:.1f}%) |\n"

        report_content += "\n*Note: These probabilities are averaged across all persona evaluations and represent the distribution of semantic similarity to each anchor rating.*\n"

    report_content += """
---

## Demand Assessment

"""

    # Add demand interpretation
    mean_intent = metrics.mean_purchase_intent
    if mean_intent >= 4.0:
        assessment = "**Strong Demand** 🟢"
        interpretation = (
            "The product shows strong market demand with high purchase intent. "
            "This indicates good product-market fit and suggests proceeding with development/launch."
        )
    elif mean_intent >= 3.0:
        assessment = "**Moderate Demand** 🟡"
        interpretation = (
            "The product shows moderate market demand. Consider refining the value "
            "proposition or targeting specific high-intent demographic segments identified below."
        )
    else:
        assessment = "**Low Demand** 🔴"
        interpretation = (
            "The product shows limited market demand. Significant changes to the product "
            "concept, positioning, or target market may be needed."
        )

    report_content += f"""{assessment}

{interpretation}

**High Intent Personas:** {metrics.high_intent_percentage:.1f}% of evaluated personas are likely to purchase (rating ≥ 4.0).

---

## Demographic Insights

The following segments show varying levels of purchase intent:

"""

    # Add demographic insights table
    if metrics.demographic_insights:
        report_content += "| Demographic Segment | Mean Purchase Intent |\n"
        report_content += "|---------------------|---------------------|\n"

        # Sort by intent (highest first)
        sorted_insights = sorted(
            metrics.demographic_insights.items(),
            key=lambda x: x[1],
            reverse=True,
        )

        for segment, intent in sorted_insights:
            # Format segment name nicely
            formatted_segment = segment.replace("_", " ").title()
            report_content += f"| {formatted_segment} | {intent:.2f} |\n"

        report_content += "\n### Key Findings\n\n"

        # Identify highest and lowest intent segments
        if len(sorted_insights) >= 2:
            highest_segment, highest_intent = sorted_insights[0]
            lowest_segment, lowest_intent = sorted_insights[-1]

            report_content += f"- **Highest Intent Segment:** {highest_segment.replace('_', ' ').title()} ({highest_intent:.2f})\n"
            report_content += f"- **Lowest Intent Segment:** {lowest_segment.replace('_', ' ').title()} ({lowest_intent:.2f})\n\n"

        # Provide targeting recommendations
        high_segments = [seg for seg, intent in sorted_insights if intent >= 4.0]
        if high_segments:
            report_content += "**Recommended Target Segments:** "
            report_content += ", ".join(
                seg.replace("_", " ").title() for seg in high_segments
            )
            report_content += "\n\n"
    else:
        report_content += "*No demographic insights available.*\n\n"

    # Add methodology section
    report_content += """---

## Methodology

This evaluation uses LLM-simulated personas with diverse demographic attributes:
- **Age ranges:** 18-70 years
- **Income levels:** Low, Medium, High
- **Education levels:** High School through PhD
- **Locations:** Urban, Suburban, Rural

### Semantic Similarity Rating Approach

Purchase intent ratings are calculated using a probability-weighted semantic similarity method based on the research paper methodology:

1. Each persona provides textual purchase intent (not numeric)
2. Text is vectorized using Nomic embeddings
3. Cosine similarities are calculated against 5 golden intent anchors
4. Similarities are transformed into a probability mass function (PMF):
   - Subtract minimum similarity to shift range
   - Normalize to create a probability distribution over the 5 rating levels
5. Final rating is computed as the expected value (weighted sum of ratings × probabilities)

**Mean PMF Calculation:** The mean PMF shown in the report is calculated by averaging the individual PMFs from each persona. This provides insight into the overall distribution of purchase intent across the population, showing which rating levels are most probable on average.

This approach reduces bias and produces more human-like rating distributions, as described in the paper "LLMs Reproduce Human Purchase Intent via Semantic Similarity Elicitation of Likert Ratings".

### Rating Scale (5-point continuous)

- **1.0** - Definitely would NOT purchase
- **2.0** - Probably would NOT purchase
- **3.0** - Neutral / might or might not purchase
- **4.0** - Probably would purchase
- **5.0** - Definitely would purchase

Ratings are continuous values (e.g., 3.6) providing nuanced insights.

---

## Recommendations

"""

    # Add recommendations based on metrics
    high_pct = metrics.high_intent_percentage
    mean = metrics.mean_purchase_intent

    if high_pct >= 60 and mean >= 4.0:
        report_content += """### Strong Go-to-Market Opportunity ✅

1. **Launch Strategy:** Proceed with product development and go-to-market planning
2. **Target Marketing:** Focus on high-intent demographic segments identified above
3. **Early Adopters:** The identified high-intent segments are strong candidates for beta testing
4. **Value Proposition:** Current positioning resonates well with target market
"""
    elif high_pct >= 40 and mean >= 3.0:
        report_content += """### Optimize Before Launch 🔧

1. **Refine Positioning:** Strengthen value proposition to increase intent
2. **Segment Focus:** Concentrate marketing efforts on high-intent demographics
3. **Product Iteration:** Consider feedback from medium-intent personas to improve appeal
4. **Pricing Strategy:** Evaluate price sensitivity across segments
"""
    else:
        report_content += """### Significant Changes Needed ⚠️

1. **Product Redesign:** Current concept shows limited market appeal
2. **Market Research:** Conduct deeper investigation into customer needs
3. **Alternative Positioning:** Consider different target markets or use cases
4. **Feature Validation:** Re-evaluate core features and value proposition
"""

    report_content += """
---

## Next Steps

1. **Validate Results:** Consider pilot testing with real users from high-intent segments
2. **Deep Dive Analysis:** Review individual persona evaluations for qualitative insights
3. **Competitive Analysis:** Compare against alternative products in the market
4. **Pricing Strategy:** Use price sensitivity data to optimize pricing
5. **Marketing Messages:** Extract common themes from high-intent persona reasoning

---

*This report was generated using the WIRL Demand Evaluation Workflow, which implements methodology from the research paper "LLMs Reproduce Human Purchase Intent via Semantic Similarity Elicitation of Likert Ratings"*
"""

    # Write report to file
    report_file.write_text(report_content, encoding="utf-8")

    return {"final_metrics": metrics}
