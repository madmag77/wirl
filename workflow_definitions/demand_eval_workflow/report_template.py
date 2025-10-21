"""
Report template for DemandEvalWorkflow.

This module contains the report generation logic for creating Markdown reports.
"""

from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from workflow_definitions.demand_eval_workflow.demand_eval_workflow import (
        DemandMetrics,
    )


# Golden intent descriptions for display in reports
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


def generate_report_content(
    product_name: str,
    product_description: str,
    num_personas: int,
    metrics: "DemandMetrics",
) -> str:
    """
    Generate the complete Markdown report content.

    Args:
        product_name: Name of the evaluated product
        product_description: Description of the product
        num_personas: Number of personas that were evaluated
        metrics: Demand metrics from analysis

    Returns:
        Complete Markdown report as a string
    """
    # Start with header and product info
    report = _generate_header(product_name, product_description, num_personas)

    # Add executive summary
    report += _generate_executive_summary(metrics)

    # Add PMF table if available
    if metrics.mean_pmfs and len(metrics.mean_pmfs) == 5:
        report += _generate_pmf_table(metrics.mean_pmfs)
        report += "\n---\n\n"

    # Add demographic insights
    report += _generate_demographic_insights(metrics)

    # Add recommendations
    report += _generate_recommendations(metrics)

    # Add next steps
    report += _generate_next_steps()

    return report


def _generate_header(
    product_name: str, product_description: str, num_personas: int
) -> str:
    """Generate the report header with product information."""
    return f"""# Demand Evaluation Report: {product_name}

**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Product Information

**Product Name:** {product_name}

**Description:** {product_description}

**Number of Personas Evaluated:** {num_personas}

---

"""


def _generate_executive_summary(metrics: "DemandMetrics") -> str:
    """Generate the executive summary section."""
    return f"""## Executive Summary

- **Mean Purchase Intent:** {metrics.mean_purchase_intent:.2f} / 5.0
- **Standard Deviation:** {metrics.std_purchase_intent:.2f}

### Probability Distribution (Mean PMF)

Average probability across all personas for each rating level:

"""


def _generate_pmf_table(mean_pmfs: list[float]) -> str:
    """Generate the PMF probability table."""
    table = "| Rating | Description | Mean Probability |\n"
    table += "|--------|-------------|------------------|\n"

    rating_labels = [
        "1 - Would NOT",
        "2 - Probably NOT",
        "3 - Might Buy",
        "4 - Probably Would",
        "5 - Would Buy",
    ]

    # Summarized descriptions for each rating (representing all 5 variations)
    rating_descriptions = {
        1: "Would not buy (no need, bad fit, too expensive, lacks features, no interest)",
        2: "Probably would not buy (limited need, poor fit, high price, missing features, low appeal)",
        3: "Might buy depending on circumstances (need, fit, price/features alignment)",
        4: "Would probably buy (seems like good fit, reasonable price, has desired features)",
        5: "Would buy (good fit for needs, great value, has features I'm looking for)",
    }

    for i, (label, prob) in enumerate(zip(rating_labels, mean_pmfs)):
        table += (
            f"| {label} | {rating_descriptions[i+1]} | {prob:.3f} ({prob*100:.1f}%) |\n"
        )

    table += "\n*Probabilities show semantic similarity to each rating anchor across all persona responses.*\n"

    return table


def _generate_demographic_insights(metrics: "DemandMetrics") -> str:
    """Generate the demographic insights section."""
    content = """## Demographic Insights

Purchase intent by segment (sorted highest to lowest):

"""

    if metrics.demographic_insights:
        content += "| Segment | Mean Intent |\n"
        content += "|---------|-------------|\n"

        # Sort by intent (highest first)
        sorted_insights = sorted(
            metrics.demographic_insights.items(),
            key=lambda x: x[1],
            reverse=True,
        )

        for segment, intent in sorted_insights:
            # Format segment name nicely
            formatted_segment = segment.replace("_", " ").title()
            content += f"| {formatted_segment} | {intent:.2f} |\n"

        # Identify highest and lowest intent segments
        if len(sorted_insights) >= 2:
            highest_segment, highest_intent = sorted_insights[0]
            lowest_segment, lowest_intent = sorted_insights[-1]

            content += f"\n**Highest:** {highest_segment.replace('_', ' ').title()} ({highest_intent:.2f}) | "
            content += f"**Lowest:** {lowest_segment.replace('_', ' ').title()} ({lowest_intent:.2f})\n\n"

        # Provide targeting recommendations
        high_segments = [seg for seg, intent in sorted_insights if intent >= 4.0]
        if high_segments:
            content += "**Target Segments:** "
            content += ", ".join(seg.replace("_", " ").title() for seg in high_segments)
            content += "\n\n"
    else:
        content += "*No demographic insights available.*\n\n"

    content += "---\n\n"
    return content


def _generate_recommendations(metrics: "DemandMetrics") -> str:
    """Generate the recommendations section."""
    high_pct = metrics.high_intent_percentage
    mean = metrics.mean_purchase_intent

    content = """## Recommendations

"""

    if high_pct >= 60 and mean >= 4.0:
        content += """### Strong Go-to-Market Opportunity ✅

1. **Launch Strategy:** Proceed with product development and go-to-market planning
2. **Target Marketing:** Focus on high-intent demographic segments identified above
3. **Early Adopters:** The identified high-intent segments are strong candidates for beta testing
4. **Value Proposition:** Current positioning resonates well with target market
"""
    elif high_pct >= 40 and mean >= 3.0:
        content += """### Optimize Before Launch 🔧

1. **Refine Positioning:** Strengthen value proposition to increase intent
2. **Segment Focus:** Concentrate marketing efforts on high-intent demographics
3. **Product Iteration:** Consider feedback from medium-intent personas to improve appeal
4. **Pricing Strategy:** Evaluate price sensitivity across segments
"""
    else:
        content += """### Significant Changes Needed ⚠️

1. **Product Redesign:** Current concept shows limited market appeal
2. **Market Research:** Conduct deeper investigation into customer needs
3. **Alternative Positioning:** Consider different target markets or use cases
4. **Feature Validation:** Re-evaluate core features and value proposition
"""

    return content


def _generate_next_steps() -> str:
    """Generate the next steps section."""
    return """## Next Steps

1. Review individual persona evaluations for qualitative insights
2. Pilot test with real users from high-intent segments
3. Refine value proposition based on segment feedback
4. Compare against competitive alternatives

---

*Generated by WIRL Demand Evaluation Workflow*
"""
