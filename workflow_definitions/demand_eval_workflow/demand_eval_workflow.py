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
from pathlib import Path
from typing import Dict, List

import numpy as np
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from workflow_definitions.demand_eval_workflow.prompts import (
    get_persona_generation_prompt,
    get_purchase_intent_prompt,
)
from workflow_definitions.demand_eval_workflow.report_template import (
    generate_report_content,
)


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
    demographic_insights: Dict[str, float] = Field(
        description="Purchase intent by demographic"
    )
    total_personas: int = Field(description="Total number of personas evaluated")
    mean_pmfs: List[float] = Field(
        description="Mean probability mass function of purchase intent"
    )


# Golden intent descriptions for 5-point Likert scale mapping
# Each rating has 5 variations representing different reasoning patterns
GOLDEN_INTENTS = {
    1: [
        "I would definitely not buy it as I don't need it at all",
        "I would definitely not buy it because it's not a good fit for me",
        "I would definitely not buy it as it's too expensive for what it offers",
        "I would definitely not buy it as it lacks important features I need",
        "I would definitely not buy it as I'm just not interested in this type of product",
    ],
    2: [
        "I would probably not buy it as I don't really need it that much",
        "I would probably not buy it because it doesn't seem like a great fit",
        "I would probably not buy it as the price seems a bit high for the value",
        "I would probably not buy it as it's missing some features I'd want",
        "I would probably not buy it as it doesn't really appeal to me",
    ],
    3: [
        "I might buy it depending on whether I actually need it or not",
        "I might buy it if it turns out to be a good fit for my situation",
        "I might buy it but only if the price and features align well",
        "I might buy it if it has enough of the features I'm looking for",
        "I might buy it if I become more interested after learning more about it",
    ],
    4: [
        "I would probably buy it as I think I need something like this",
        "I would probably buy it because it seems like a good fit for me",
        "I would probably buy it as the price seems reasonable for the features",
        "I would probably buy it as it has most of the features I want",
        "I would probably buy it as it genuinely interests me",
    ],
    5: [
        "I would buy it as I need something like this",
        "I would buy it because it's a good fit for my needs",
        "I would buy it as it offers great value for the price",
        "I would buy it as it has the features I'm looking for",
        "I would buy it as I'm quite interested in this product",
    ],
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


def calculate_golden_embeddings(num_personas: int, config: dict) -> dict:
    """
    Pre-calculate embeddings for all golden intent descriptions.

    This calculates embeddings for all 5 variations of each rating level (1-5),
    then computes the average embedding for each rating level. This runs once
    before the evaluation loop starts.

    Args:
        num_personas: Number of personas (not used, but required for workflow dependency)
        config: Runner config with embedding_model

    Returns:
        dict with golden_embeddings (list of 5 average embeddings, one per rating level)
    """
    embedding_model = config.get("embedding_model", "nomic-embed-text")

    # Initialize embeddings model
    embeddings = OllamaEmbeddings(model=embedding_model)

    # Calculate embeddings for each rating level
    golden_embeddings = []

    for rating in range(1, 6):  # Ratings 1-5
        rating_variations = GOLDEN_INTENTS[rating]

        # Get embeddings for all variations
        variation_embeddings = []
        for intent_text in rating_variations:
            embedding = np.array(embeddings.embed_query(intent_text))
            variation_embeddings.append(embedding)

        # Calculate average embedding for this rating
        avg_embedding = np.mean(variation_embeddings, axis=0)
        golden_embeddings.append(avg_embedding.tolist())

    return {"golden_embeddings": golden_embeddings}


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
    family_statuses = ["Single", "Married", "Divorced", "Widowed"]

    for i in range(num_personas):
        # Randomly sample demographics for diversity
        age_range = random.choice(age_ranges)
        age = random.randint(age_range[0], age_range[1])
        gender = random.choice(genders)
        income = random.choice(income_levels)
        education = random.choice(education_levels)
        location = random.choice(locations)
        family_status = random.choice(family_statuses)

        # Use LLM to generate occupation, lifestyle, and values
        prompt = get_persona_generation_prompt(
            age=age,
            gender=gender,
            income=income,
            education=education,
            location=location,
            family_status=family_status,
        )

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


def get_purchase_intent(
    persona: Persona, product_name: str, product_description: str, config: dict
) -> dict:
    """
    Get textual purchase intent from a persona.

    This implements step 1 of the research paper methodology:
    Ask LLM for TEXTUAL purchase intent (not a number) to avoid rating bias.

    Args:
        persona: The persona evaluating the product
        product_name: Name of the product
        product_description: Detailed product description
        config: Runner config with model and temperature

    Returns:
        dict with intent_text (textual description of purchase intent)
    """
    model = config.get("model", "gemma3:12b")
    temperature = config.get("temperature", 0.7)
    model_type = config.get("model_type", "ollama")

    # Initialize LLM for text generation
    if model_type == "openai":
        llm = ChatOpenAI(model=model, temperature=temperature)
    else:
        llm = ChatOllama(
            model=model,
            temperature=temperature,
            validate_model_on_init=True,
        )

    # Ask for TEXTUAL purchase intent (not numeric rating)
    intent_prompt = get_purchase_intent_prompt(
        persona=persona,
        product_name=product_name,
        product_description=product_description,
    )

    intent_response = llm.invoke(intent_prompt)
    intent_text = getattr(intent_response, "content", str(intent_response))

    return {"intent_text": intent_text}


def calculate_persona_metrics(
    persona: Persona,
    intent_text: str,
    golden_embeddings: List[List[float]],
    config: dict,
) -> dict:
    """
    Calculate purchase intent metrics using semantic similarity to golden intents.

    This implements steps 2-4 of the research paper methodology:
    - Vectorize the intent text using embeddings
    - Compare to pre-calculated golden intent embeddings via cosine similarity
    - Compute probability-weighted rating (PMF approach)

    Args:
        persona: The persona who provided the intent
        intent_text: Textual description of purchase intent
        golden_embeddings: Pre-calculated average embeddings for each rating level (1-5)
        config: Runner config with embedding_model

    Returns:
        dict with evaluation containing purchase intent and probability distribution
    """
    embedding_model = config.get("embedding_model", "nomic-embed-text")

    # Initialize embeddings model (Nomic via Ollama)
    embeddings = OllamaEmbeddings(model=embedding_model)

    # Vectorize the intent text and calculate similarities
    try:
        intent_embedding = np.array(embeddings.embed_query(intent_text[:5000]))

        # Calculate similarities to all golden intent embeddings and compute expected rating
        # Following the paper's methodology:
        # 1. Get cosine similarities to all anchors
        # 2. Subtract minimum to shift range
        # 3. Normalize to get probability distribution
        # 4. Compute expected rating as weighted sum

        similarities = []
        ratings = []
        for rating_idx, golden_embedding_list in enumerate(golden_embeddings):
            golden_embedding = np.array(golden_embedding_list)
            similarity = cosine_similarity(intent_embedding, golden_embedding)
            similarities.append(similarity)
            ratings.append(rating_idx + 1)  # Ratings are 1-5

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

    except Exception:
        # Fallback if embeddings fail
        purchase_intent = 3.0  # Neutral on 5-point scale
        best_similarity = 0.0
        probabilities = [1.0 / 5] * 5

    evaluation = PersonaEvaluation(
        pmfs=probabilities,
        persona=persona,
        purchase_intent=purchase_intent,
        intent_text=intent_text,
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
                demographic_insights={},
                total_personas=0,
            )
        }

    # Extract purchase intents and recommendations
    intents = [e.purchase_intent for e in evaluations]

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
    from datetime import datetime

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

    # Generate markdown report using template
    report_content = generate_report_content(
        product_name=product_name,
        product_description=product_description,
        num_personas=num_personas,
        metrics=metrics,
    )

    # Write report to file
    report_file.write_text(report_content, encoding="utf-8")

    return {"final_metrics": metrics}
