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
GOLDEN_INTENTS = {
    1: "I would definitely not purchase this product. It does not meet my needs at all and I have no interest in it whatsoever.",
    2: "I would probably not purchase this product. It doesn't really appeal to me and I don't see much value in it.",
    3: "I might or might not purchase this product. I'm neutral about it - it has both pros and cons that balance out.",
    4: "I would probably purchase this product. It seems like a good fit for my needs and I'm fairly interested in it.",
    5: "I would definitely purchase this product. It's exactly what I'm looking for and I'm highly interested in buying it.",
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

    # Add demand assessment
    report += _generate_demand_assessment(metrics)

    # Add demographic insights
    report += _generate_demographic_insights(metrics)

    # Add methodology section
    report += _generate_methodology()

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

### Overall Purchase Intent

- **Mean Purchase Intent:** {metrics.mean_purchase_intent:.2f} / 5.0
- **Standard Deviation:** {metrics.std_purchase_intent:.2f}

### Intent Distribution

| Category | Percentage |
|----------|-----------|
| **High Intent** (≥ 4.0) | {metrics.high_intent_percentage:.1f}% |
| **Medium Intent** (2.5 - 4.0) | {metrics.medium_intent_percentage:.1f}% |
| **Low Intent** (< 2.5) | {metrics.low_intent_percentage:.1f}% |

### Probability Distribution (Mean PMF)

The following table shows the average probability distribution across all personas for each rating level. This represents how likely personas are to have each specific purchase intent level based on semantic similarity to golden anchors:

"""


def _generate_pmf_table(mean_pmfs: list[float]) -> str:
    """Generate the PMF probability table."""
    table = "| Rating | Description | Mean Probability |\n"
    table += "|--------|-------------|------------------|\n"

    rating_labels = [
        "1 - Definitely NOT",
        "2 - Probably NOT",
        "3 - Neutral/Might",
        "4 - Probably Would",
        "5 - Definitely Would",
    ]

    for i, (label, prob) in enumerate(zip(rating_labels, mean_pmfs)):
        table += f"| {label} | {GOLDEN_INTENTS[i+1][:50]}... | {prob:.3f} ({prob*100:.1f}%) |\n"

    table += "\n*Note: These probabilities are averaged across all persona evaluations and represent the distribution of semantic similarity to each anchor rating.*\n"

    return table


def _generate_demand_assessment(metrics: "DemandMetrics") -> str:
    """Generate the demand assessment section."""
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

    return f"""
---

## Demand Assessment

{assessment}

{interpretation}

**High Intent Personas:** {metrics.high_intent_percentage:.1f}% of evaluated personas are likely to purchase (rating ≥ 4.0).

---

"""


def _generate_demographic_insights(metrics: "DemandMetrics") -> str:
    """Generate the demographic insights section."""
    content = """## Demographic Insights

The following segments show varying levels of purchase intent:

"""

    if metrics.demographic_insights:
        content += "| Demographic Segment | Mean Purchase Intent |\n"
        content += "|---------------------|---------------------|\n"

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

        content += "\n### Key Findings\n\n"

        # Identify highest and lowest intent segments
        if len(sorted_insights) >= 2:
            highest_segment, highest_intent = sorted_insights[0]
            lowest_segment, lowest_intent = sorted_insights[-1]

            content += f"- **Highest Intent Segment:** {highest_segment.replace('_', ' ').title()} ({highest_intent:.2f})\n"
            content += f"- **Lowest Intent Segment:** {lowest_segment.replace('_', ' ').title()} ({lowest_intent:.2f})\n\n"

        # Provide targeting recommendations
        high_segments = [seg for seg, intent in sorted_insights if intent >= 4.0]
        if high_segments:
            content += "**Recommended Target Segments:** "
            content += ", ".join(seg.replace("_", " ").title() for seg in high_segments)
            content += "\n\n"
    else:
        content += "*No demographic insights available.*\n\n"

    return content


def _generate_methodology() -> str:
    """Generate the methodology section."""
    return """---

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

"""


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
    return """
---

## Next Steps

1. **Validate Results:** Consider pilot testing with real users from high-intent segments
2. **Deep Dive Analysis:** Review individual persona evaluations for qualitative insights
3. **Competitive Analysis:** Compare against alternative products in the market
4. **Market Positioning:** Refine value proposition based on high-intent segment feedback
5. **Marketing Messages:** Extract common themes from high-intent persona intent descriptions

---

*This report was generated using the WIRL Demand Evaluation Workflow, which implements methodology from the research paper "LLMs Reproduce Human Purchase Intent via Semantic Similarity Elicitation of Likert Ratings"*
"""
