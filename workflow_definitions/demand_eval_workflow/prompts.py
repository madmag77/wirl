"""
Prompts for DemandEvalWorkflow.

This module contains all prompt templates used in the workflow.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from workflow_definitions.demand_eval_workflow.demand_eval_workflow import Persona


def get_persona_generation_prompt(
    age: int,
    gender: str,
    income: str,
    education: str,
    location: str,
) -> str:
    """
    Generate a prompt for creating a persona profile.

    Args:
        age: Age of the persona
        gender: Gender of the persona
        income: Income level (Low, Medium, High)
        education: Education level
        location: Geographic location

    Returns:
        Formatted prompt for persona generation
    """
    return f"""Generate a realistic persona profile for market research.

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


def get_purchase_intent_prompt(
    persona: "Persona",
    product_name: str,
    product_description: str,
) -> str:
    """
    Generate a prompt for eliciting textual purchase intent from a persona.

    This implements the core methodology from the research paper:
    ask for TEXTUAL intent (not numeric) to avoid LLM rating bias.

    Args:
        persona: The persona evaluating the product
        product_name: Name of the product
        product_description: Detailed product description

    Returns:
        Formatted prompt for purchase intent elicitation
    """
    return f"""You are roleplaying as a market research participant with the following profile:

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

Please provide a detailed textual description of your purchase intent (one paragraph). Explain whether you would purchase this product or not and why, considering your demographic profile, lifestyle, and values. Do NOT provide a numeric rating - just describe your intent in words.
Don't hesitate to say you wouldn't buy this product if product is not a good fit for you. Be honest and blunt if needed.
"""
