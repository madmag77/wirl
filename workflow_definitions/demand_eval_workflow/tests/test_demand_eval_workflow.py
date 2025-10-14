"""
Tests for DemandEvalWorkflow.
"""

import pytest
from unittest.mock import MagicMock, patch

from workflow_definitions.demand_eval_workflow.demand_eval_workflow import (
    Persona,
    PersonaEvaluation,
    DemandMetrics,
    generate_personas,
    process_next_persona,
    evaluate_product,
    collect_evaluations,
    analyze_demand,
)


@pytest.fixture
def sample_persona():
    """Create a sample persona for testing."""
    return Persona(
        age=35,
        gender="Female",
        income_level="High",
        education="Master's Degree",
        occupation="Software Engineer",
        location="Urban",
        lifestyle="Tech-savvy professional with active lifestyle",
        values=["Innovation", "Quality", "Sustainability"],
    )


@pytest.fixture
def sample_evaluation(sample_persona):
    """Create a sample evaluation for testing."""
    return PersonaEvaluation(
        persona=sample_persona,
        purchase_intent=6,
        intent_text="I would very likely purchase this product as it aligns with my values",
        reasoning="The product aligns with my values for innovation and quality",
        price_sensitivity="Low",
        likelihood_to_recommend=7,
        similarity_score=0.85,
    )


def test_generate_personas():
    """Test persona generation with mocked LLM."""
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = """```json
{
    "occupation": "Marketing Manager",
    "lifestyle": "Busy professional who values work-life balance and quality products",
    "values": ["Quality", "Convenience", "Value"]
}
```"""
    mock_llm.invoke.return_value = mock_response

    with patch(
        "workflow_definitions.demand_eval_workflow.demand_eval_workflow.ChatOllama",
        return_value=mock_llm,
    ):
        result = generate_personas(
            num_personas=2, config={"model": "gemma3:12b", "temperature": 0.8}
        )

        assert "personas" in result
        assert len(result["personas"]) == 2

        for persona in result["personas"]:
            assert isinstance(persona, Persona)
            assert persona.age > 0
            assert persona.gender in ["Male", "Female", "Non-binary"]
            assert persona.income_level in ["Low", "Medium", "High"]
            assert len(persona.values) > 0


def test_process_next_persona_first_iteration(sample_persona):
    """Test processing first persona."""
    personas = [sample_persona]

    result = process_next_persona(personas=None, initial_personas=personas, config={})

    assert "current_persona" in result
    assert "remaining_personas" in result
    assert "no_personas_left" in result
    assert result["no_personas_left"] is False
    assert result["current_persona"] == sample_persona
    assert len(result["remaining_personas"]) == 0


def test_process_next_persona_no_personas_left():
    """Test processing when no personas are left."""
    result = process_next_persona(personas=[], initial_personas=[], config={})

    assert result["no_personas_left"] is True
    assert result["remaining_personas"] == []


def test_evaluate_product(sample_persona):
    """Test product evaluation with mocked LLM and embeddings."""
    # Mock LLM for intent and details responses
    mock_llm = MagicMock()

    intent_response = MagicMock()
    intent_response.content = "I would very likely purchase this product as it aligns perfectly with my tech-savvy lifestyle and values of innovation."

    details_response = MagicMock()
    details_response.content = """```json
{
    "reasoning": "This product fits my lifestyle and values perfectly",
    "price_sensitivity": "Low",
    "recommendation_text": "I would definitely recommend this to others like me"
}
```"""

    mock_llm.invoke.side_effect = [intent_response, details_response]

    # Mock embeddings
    mock_embeddings = MagicMock()
    # Return embeddings that will match to rating 6 (high intent)
    mock_embeddings.embed_query.return_value = [0.1] * 768  # Mock 768-dim embedding

    with (
        patch(
            "workflow_definitions.demand_eval_workflow.demand_eval_workflow.ChatOllama",
            return_value=mock_llm,
        ),
        patch(
            "workflow_definitions.demand_eval_workflow.demand_eval_workflow.OllamaEmbeddings",
            return_value=mock_embeddings,
        ),
    ):
        result = evaluate_product(
            persona=sample_persona,
            product_name="Smart Home Hub",
            product_description="AI-powered home automation system",
            config={
                "model": "gemma3:12b",
                "temperature": 0.7,
                "embedding_model": "nomic-embed-text",
            },
        )

        assert "evaluation" in result
        evaluation = result["evaluation"]
        assert isinstance(evaluation, PersonaEvaluation)
        assert 1 <= evaluation.purchase_intent <= 7
        assert 1 <= evaluation.likelihood_to_recommend <= 7
        assert evaluation.price_sensitivity in ["Low", "Medium", "High"]
        assert len(evaluation.reasoning) > 0
        assert len(evaluation.intent_text) > 0
        assert 0.0 <= evaluation.similarity_score <= 1.0


def test_collect_evaluations_with_evaluation(sample_evaluation, sample_persona):
    """Test collecting evaluations."""
    result = collect_evaluations(
        evaluation=sample_evaluation,
        remaining_personas=[sample_persona],
        no_personas_left=False,
        config={},
    )

    assert "is_done" in result
    assert "evaluations" in result
    assert result["is_done"] is False
    assert len(result["evaluations"]) == 1
    assert result["evaluations"][0] == sample_evaluation


def test_collect_evaluations_done():
    """Test collecting evaluations when done."""
    result = collect_evaluations(
        evaluation=None, remaining_personas=[], no_personas_left=False, config={}
    )

    assert result["is_done"] is True
    assert result["evaluations"] == []


def test_analyze_demand(sample_evaluation):
    """Test demand analysis."""
    # Create multiple evaluations with varying purchase intents
    evaluations = []

    personas = [
        Persona(
            age=25,
            gender="Male",
            income_level="Low",
            education="Bachelor's Degree",
            occupation="Student",
            location="Urban",
            lifestyle="Budget conscious",
            values=["Value"],
        ),
        Persona(
            age=45,
            gender="Female",
            income_level="High",
            education="PhD",
            occupation="Executive",
            location="Suburban",
            lifestyle="Luxury seeker",
            values=["Quality"],
        ),
        Persona(
            age=60,
            gender="Male",
            income_level="Medium",
            education="High School",
            occupation="Retired",
            location="Rural",
            lifestyle="Traditional",
            values=["Reliability"],
        ),
    ]

    intents = [3, 6, 4]
    recommendations = [3, 7, 5]

    for i, persona in enumerate(personas):
        evaluations.append(
            PersonaEvaluation(
                persona=persona,
                purchase_intent=intents[i],
                intent_text=f"Intent text for evaluation {i}",
                reasoning=f"Evaluation {i}",
                price_sensitivity="Medium",
                likelihood_to_recommend=recommendations[i],
                similarity_score=0.75,
            )
        )

    result = analyze_demand(
        evaluations=evaluations, product_name="Test Product", config={}
    )

    assert "metrics" in result
    metrics = result["metrics"]
    assert isinstance(metrics, DemandMetrics)

    # Check basic statistics
    assert metrics.total_personas == 3
    assert metrics.mean_purchase_intent == pytest.approx(4.33, rel=0.1)
    assert metrics.std_purchase_intent > 0
    assert metrics.mean_recommendation == pytest.approx(5.0, rel=0.1)

    # Check distribution percentages
    assert (
        metrics.high_intent_percentage
        + metrics.medium_intent_percentage
        + metrics.low_intent_percentage
        == pytest.approx(100.0, rel=0.1)
    )

    # Check demographic insights exist
    assert len(metrics.demographic_insights) > 0
    assert (
        "age_18-35" in metrics.demographic_insights
        or "age_36-55" in metrics.demographic_insights
        or "age_56+" in metrics.demographic_insights
    )
    assert (
        "income_Low" in metrics.demographic_insights
        or "income_Medium" in metrics.demographic_insights
        or "income_High" in metrics.demographic_insights
    )


def test_analyze_demand_empty_evaluations():
    """Test demand analysis with empty evaluations."""
    result = analyze_demand(evaluations=[], product_name="Test Product", config={})

    assert "metrics" in result
    metrics = result["metrics"]
    assert metrics.total_personas == 0
    assert metrics.mean_purchase_intent == 0.0
    assert metrics.std_purchase_intent == 0.0


@pytest.mark.integration
def test_full_workflow_integration():
    """Integration test for the full workflow with mocked LLM calls."""
    # Mock LLM for persona generation
    mock_llm_personas = MagicMock()
    mock_response_persona = MagicMock()
    mock_response_persona.content = """```json
{
    "occupation": "Teacher",
    "lifestyle": "Family-oriented with modest income",
    "values": ["Education", "Family", "Value"]
}
```"""
    mock_llm_personas.invoke.return_value = mock_response_persona

    # Mock LLM for product evaluation (intent + details)
    mock_llm_eval = MagicMock()

    intent_response = MagicMock()
    intent_response.content = (
        "I would probably purchase this product as it fits my needs"
    )

    details_response = MagicMock()
    details_response.content = """```json
{
    "reasoning": "Good product for my needs",
    "price_sensitivity": "Medium",
    "recommendation_text": "I would likely recommend this to others"
}
```"""

    mock_llm_eval.invoke.side_effect = [
        intent_response,
        details_response,
    ] * 2  # 2 personas

    # Mock embeddings
    mock_embeddings = MagicMock()
    mock_embeddings.embed_query.return_value = [0.1] * 768

    with (
        patch(
            "workflow_definitions.demand_eval_workflow.demand_eval_workflow.ChatOllama"
        ) as mock_chat,
        patch(
            "workflow_definitions.demand_eval_workflow.demand_eval_workflow.OllamaEmbeddings",
            return_value=mock_embeddings,
        ),
    ):
        # Configure mock to return personas LLM
        mock_chat.return_value = mock_llm_personas

        # Generate personas
        personas_result = generate_personas(
            num_personas=2, config={"model": "gemma3:12b"}
        )
        personas = personas_result["personas"]
        assert len(personas) == 2

        # Switch to eval LLM
        mock_chat.return_value = mock_llm_eval

        # Evaluate product with each persona
        evaluations = []
        for persona in personas:
            eval_result = evaluate_product(
                persona=persona,
                product_name="Smart Watch",
                product_description="Fitness tracking smartwatch",
                config={"model": "gemma3:12b", "embedding_model": "nomic-embed-text"},
            )
            evaluations.append(eval_result["evaluation"])

        # Analyze demand
        metrics_result = analyze_demand(
            evaluations=evaluations, product_name="Smart Watch", config={}
        )

        metrics = metrics_result["metrics"]
        assert metrics.total_personas == 2
        assert metrics.mean_purchase_intent > 0
        assert len(metrics.demographic_insights) > 0
