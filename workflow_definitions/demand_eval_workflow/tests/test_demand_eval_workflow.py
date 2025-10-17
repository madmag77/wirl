"""
Tests for DemandEvalWorkflow.
"""

import pytest
from unittest.mock import MagicMock, patch
from wirl_pregel_runner import run_workflow

from workflow_definitions.demand_eval_workflow.demand_eval_workflow import (
    Persona,
    PersonaEvaluation,
    DemandMetrics,
    generate_personas,
    process_next_persona,
    get_purchase_intent,
    calculate_persona_metrics,
    collect_evaluations,
    analyze_demand,
    save_report,
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
        purchase_intent=4.5,
        intent_text="I would very likely purchase this product as it aligns with my values",
        similarity_score=0.85,
        pmfs=[0.05, 0.10, 0.15, 0.35, 0.35],
    )


@pytest.fixture
def sample_metrics():
    """Create sample metrics for testing."""
    return DemandMetrics(
        mean_purchase_intent=3.8,
        std_purchase_intent=0.9,
        high_intent_percentage=60.0,
        medium_intent_percentage=30.0,
        low_intent_percentage=10.0,
        demographic_insights={
            "age_18-35": 4.2,
            "age_36-55": 3.7,
            "income_High": 4.5,
            "location_Urban": 4.0,
        },
        total_personas=20,
        mean_pmfs=[0.10, 0.15, 0.20, 0.30, 0.25],
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


def test_get_purchase_intent(sample_persona):
    """Test getting purchase intent with mocked LLM."""
    # Mock LLM for intent response
    mock_llm = MagicMock()

    intent_response = MagicMock()
    intent_response.content = "I would very likely purchase this product as it aligns perfectly with my tech-savvy lifestyle and values of innovation."

    mock_llm.invoke.return_value = intent_response

    with patch(
        "workflow_definitions.demand_eval_workflow.demand_eval_workflow.ChatOllama",
        return_value=mock_llm,
    ):
        result = get_purchase_intent(
            persona=sample_persona,
            product_name="Smart Home Hub",
            product_description="AI-powered home automation system",
            config={
                "model": "gemma3:12b",
                "temperature": 0.7,
            },
        )

        assert "intent_text" in result
        intent_text = result["intent_text"]
        assert isinstance(intent_text, str)
        assert len(intent_text) > 0
        assert "purchase" in intent_text.lower() or "would" in intent_text.lower()


def test_calculate_persona_metrics(sample_persona):
    """Test calculating persona metrics with mocked embeddings."""
    intent_text = "I would very likely purchase this product as it aligns perfectly with my tech-savvy lifestyle and values of innovation."

    # Mock embeddings
    mock_embeddings = MagicMock()
    # Return embeddings that will be consistent
    mock_embeddings.embed_query.return_value = [0.1] * 768  # Mock 768-dim embedding

    with patch(
        "workflow_definitions.demand_eval_workflow.demand_eval_workflow.OllamaEmbeddings",
        return_value=mock_embeddings,
    ):
        result = calculate_persona_metrics(
            persona=sample_persona,
            intent_text=intent_text,
            config={
                "embedding_model": "nomic-embed-text",
            },
        )

        assert "evaluation" in result
        evaluation = result["evaluation"]
        assert isinstance(evaluation, PersonaEvaluation)
        assert 1 <= evaluation.purchase_intent <= 5
        assert len(evaluation.intent_text) > 0
        assert 0.0 <= evaluation.similarity_score <= 1.0
        assert len(evaluation.pmfs) == 5
        assert pytest.approx(sum(evaluation.pmfs), abs=0.01) == 1.0


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

    intents = [2.8, 4.5, 3.6]

    pmfs_list = [
        [0.15, 0.25, 0.30, 0.20, 0.10],
        [0.05, 0.10, 0.15, 0.30, 0.40],
        [0.10, 0.15, 0.25, 0.35, 0.15],
    ]

    for i, persona in enumerate(personas):
        evaluations.append(
            PersonaEvaluation(
                persona=persona,
                purchase_intent=intents[i],
                intent_text=f"Intent text for evaluation {i}",
                similarity_score=0.75,
                pmfs=pmfs_list[i],
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
    assert metrics.mean_purchase_intent == pytest.approx(3.63, rel=0.1)
    assert metrics.std_purchase_intent > 0

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

    # Check mean PMFs
    assert len(metrics.mean_pmfs) == 5
    assert pytest.approx(sum(metrics.mean_pmfs), abs=0.01) == 1.0


def test_analyze_demand_empty_evaluations():
    """Test demand analysis with empty evaluations."""
    result = analyze_demand(evaluations=[], product_name="Test Product", config={})

    assert "metrics" in result
    metrics = result["metrics"]
    assert metrics.total_personas == 0
    assert metrics.mean_purchase_intent == 0.0
    assert metrics.std_purchase_intent == 0.0


def test_save_report(sample_metrics, tmp_path):
    """Test report saving functionality."""
    report_path = tmp_path / "reports"

    result = save_report(
        product_name="Smart Water Bottle",
        product_description="AI-powered hydration tracking bottle",
        num_personas=20,
        metrics=sample_metrics,
        report_path=str(report_path),
        config={},
    )

    # Check return value
    assert "final_metrics" in result
    assert result["final_metrics"] == sample_metrics

    # Check that report directory was created
    assert report_path.exists()
    assert report_path.is_dir()

    # Check that report file was created
    report_files = list(report_path.glob("demand_eval_*.md"))
    assert len(report_files) == 1

    report_file = report_files[0]
    assert report_file.exists()

    # Check report filename format
    assert report_file.name.startswith("demand_eval_Smart_Water_Bottle_")
    assert report_file.name.endswith(".md")

    # Check report content
    report_content = report_file.read_text(encoding="utf-8")

    # Check key sections exist
    assert "# Demand Evaluation Report: Smart Water Bottle" in report_content
    assert "AI-powered hydration tracking bottle" in report_content
    assert "Number of Personas Evaluated:** 20" in report_content
    assert "Mean Purchase Intent:** 3.80" in report_content
    assert "60.0%" in report_content  # High intent percentage
    assert "Demographic Insights" in report_content
    assert "Age 18-35" in report_content
    assert "Methodology" in report_content
    assert "Recommendations" in report_content

    # Check that demographic insights are properly formatted
    assert "4.20" in report_content  # age_18-35 value
    assert "4.50" in report_content  # income_High value


def test_save_report_with_special_characters(sample_metrics, tmp_path):
    """Test report saving with special characters in product name."""
    report_path = tmp_path / "reports"

    result = save_report(
        product_name="Smart Watch (2024) - Pro Edition!",
        product_description="Advanced fitness tracking",
        num_personas=10,
        metrics=sample_metrics,
        report_path=str(report_path),
        config={},
    )

    # Check return value
    assert "final_metrics" in result

    # Check that file was created with sanitized name
    report_files = list(report_path.glob("demand_eval_*.md"))
    assert len(report_files) == 1

    # Verify special characters were replaced
    report_file = report_files[0]
    assert "(" not in report_file.name
    assert ")" not in report_file.name
    assert "!" not in report_file.name
    assert "_" in report_file.name  # Special chars replaced with underscore


def test_save_report_demand_assessments(tmp_path):
    """Test different demand assessment categories in report."""
    report_path = tmp_path / "reports"

    # Test strong demand
    strong_metrics = DemandMetrics(
        mean_purchase_intent=4.5,
        std_purchase_intent=0.5,
        high_intent_percentage=80.0,
        medium_intent_percentage=15.0,
        low_intent_percentage=5.0,
        demographic_insights={},
        total_personas=10,
        mean_pmfs=[0.05, 0.05, 0.10, 0.30, 0.50],
    )

    save_report(
        product_name="Strong Product",
        product_description="High demand product",
        num_personas=10,
        metrics=strong_metrics,
        report_path=str(report_path),
        config={},
    )

    report_file = list(report_path.glob("*Strong_Product*.md"))[0]
    content = report_file.read_text(encoding="utf-8")
    assert "**Strong Demand** 🟢" in content
    assert "Strong Go-to-Market Opportunity" in content

    # Test moderate demand
    moderate_metrics = DemandMetrics(
        mean_purchase_intent=3.2,
        std_purchase_intent=0.8,
        high_intent_percentage=40.0,
        medium_intent_percentage=50.0,
        low_intent_percentage=10.0,
        demographic_insights={},
        total_personas=10,
        mean_pmfs=[0.10, 0.15, 0.35, 0.30, 0.10],
    )

    save_report(
        product_name="Moderate Product",
        product_description="Moderate demand product",
        num_personas=10,
        metrics=moderate_metrics,
        report_path=str(report_path),
        config={},
    )

    report_file = list(report_path.glob("*Moderate_Product*.md"))[0]
    content = report_file.read_text(encoding="utf-8")
    assert "**Moderate Demand** 🟡" in content
    assert "Optimize Before Launch" in content

    # Test low demand
    low_metrics = DemandMetrics(
        mean_purchase_intent=2.0,
        std_purchase_intent=0.7,
        high_intent_percentage=10.0,
        medium_intent_percentage=30.0,
        low_intent_percentage=60.0,
        demographic_insights={},
        total_personas=10,
        mean_pmfs=[0.35, 0.35, 0.20, 0.08, 0.02],
    )

    save_report(
        product_name="Low Product",
        product_description="Low demand product",
        num_personas=10,
        metrics=low_metrics,
        report_path=str(report_path),
        config={},
    )

    report_file = list(report_path.glob("*Low_Product*.md"))[0]
    content = report_file.read_text(encoding="utf-8")
    assert "**Low Demand** 🔴" in content
    assert "Significant Changes Needed" in content


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

    # Mock LLM for product evaluation (intent only)
    mock_llm_eval = MagicMock()

    intent_response = MagicMock()
    intent_response.content = (
        "I would probably purchase this product as it fits my needs"
    )

    mock_llm_eval.invoke.return_value = intent_response

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
            # Get intent
            intent_result = get_purchase_intent(
                persona=persona,
                product_name="Smart Watch",
                product_description="Fitness tracking smartwatch",
                config={"model": "gemma3:12b"},
            )
            intent_text = intent_result["intent_text"]

            # Calculate metrics
            eval_result = calculate_persona_metrics(
                persona=persona,
                intent_text=intent_text,
                config={"embedding_model": "nomic-embed-text"},
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


@pytest.mark.integration
def test_full_workflow_with_report(tmp_path):
    """Integration test including report generation."""
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

    # Mock LLM for product evaluation (intent only)
    mock_llm_eval = MagicMock()

    intent_response = MagicMock()
    intent_response.content = (
        "I would probably purchase this product as it fits my needs"
    )

    mock_llm_eval.invoke.return_value = intent_response

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
        # Generate personas
        mock_chat.return_value = mock_llm_personas
        personas_result = generate_personas(
            num_personas=1, config={"model": "gemma3:12b"}
        )
        personas = personas_result["personas"]

        # Evaluate product
        mock_chat.return_value = mock_llm_eval
        evaluations = []
        for persona in personas:
            # Get intent
            intent_result = get_purchase_intent(
                persona=persona,
                product_name="Smart Watch",
                product_description="Fitness tracking smartwatch",
                config={"model": "gemma3:12b"},
            )
            intent_text = intent_result["intent_text"]

            # Calculate metrics
            eval_result = calculate_persona_metrics(
                persona=persona,
                intent_text=intent_text,
                config={"embedding_model": "nomic-embed-text"},
            )
            evaluations.append(eval_result["evaluation"])

        # Analyze demand
        metrics_result = analyze_demand(
            evaluations=evaluations, product_name="Smart Watch", config={}
        )
        metrics = metrics_result["metrics"]

        # Save report
        report_path = tmp_path / "reports"
        report_result = save_report(
            product_name="Smart Watch",
            product_description="Fitness tracking smartwatch",
            num_personas=1,
            metrics=metrics,
            report_path=str(report_path),
            config={},
        )

        # Verify report was created
        assert report_result["final_metrics"] == metrics
        assert report_path.exists()
        report_files = list(report_path.glob("demand_eval_*.md"))
        assert len(report_files) == 1

        # Verify report content
        report_content = report_files[0].read_text(encoding="utf-8")
        assert "Smart Watch" in report_content
        assert "Fitness tracking smartwatch" in report_content


def test_demand_eval_workflow_e2e(tmp_path):
    """End-to-end test of the demand evaluation workflow with mocked functions."""

    # Create mock personas
    mock_personas = [
        Persona(
            age=28,
            gender="Female",
            income_level="High",
            education="Bachelor's Degree",
            occupation="Software Engineer",
            location="Urban",
            lifestyle="Tech-savvy professional",
            values=["Innovation", "Quality"],
        ),
        Persona(
            age=45,
            gender="Male",
            income_level="Medium",
            education="Master's Degree",
            occupation="Teacher",
            location="Suburban",
            lifestyle="Family-oriented",
            values=["Education", "Value"],
        ),
    ]

    # Create mock evaluations
    mock_evaluations = [
        PersonaEvaluation(
            persona=mock_personas[0],
            purchase_intent=4.5,
            intent_text="I would definitely purchase this product",
            similarity_score=0.85,
            pmfs=[0.05, 0.10, 0.15, 0.30, 0.40],
        ),
        PersonaEvaluation(
            persona=mock_personas[1],
            purchase_intent=3.2,
            intent_text="I might consider purchasing this product",
            similarity_score=0.70,
            pmfs=[0.10, 0.20, 0.35, 0.25, 0.10],
        ),
    ]

    # Create mock metrics
    mock_metrics = DemandMetrics(
        mean_purchase_intent=3.85,
        std_purchase_intent=0.65,
        high_intent_percentage=50.0,
        medium_intent_percentage=50.0,
        low_intent_percentage=0.0,
        demographic_insights={
            "age_18-35": 4.5,
            "age_36-55": 3.2,
            "income_High": 4.5,
            "income_Medium": 3.2,
            "location_Urban": 4.5,
            "location_Suburban": 3.2,
        },
        total_personas=2,
        mean_pmfs=[0.075, 0.15, 0.25, 0.275, 0.25],
    )

    # Mock functions for the workflow
    def mock_generate_personas(num_personas: int, config: dict) -> dict:
        return {"personas": mock_personas}

    def mock_process_next_persona(
        personas: list | None, initial_personas: list, config: dict
    ) -> dict:
        personas_to_process = personas if personas is not None else initial_personas
        if not personas_to_process:
            return {
                "current_persona": {},
                "remaining_personas": [],
                "no_personas_left": True,
            }
        return {
            "current_persona": personas_to_process[0],
            "remaining_personas": personas_to_process[1:],
            "no_personas_left": False,
        }

    def mock_get_purchase_intent(
        persona: Persona, product_name: str, product_description: str, config: dict
    ) -> dict:
        # Return different intent text based on persona
        if persona.age < 35:
            return {"intent_text": "I would definitely purchase this product"}
        else:
            return {"intent_text": "I might consider purchasing this product"}

    def mock_calculate_persona_metrics(
        persona: Persona, intent_text: str, config: dict
    ) -> dict:
        # Return different evaluation based on persona
        if persona.age < 35:
            return {"evaluation": mock_evaluations[0]}
        else:
            return {"evaluation": mock_evaluations[1]}

    def mock_collect_evaluations(
        evaluation: PersonaEvaluation | None,
        remaining_personas: list | None,
        no_personas_left: bool | None,
        config: dict,
    ) -> dict:
        if no_personas_left:
            return {"is_done": True, "evaluations": []}
        remaining = remaining_personas or []
        is_done = len(remaining) == 0
        return {
            "is_done": is_done,
            "evaluations": [evaluation] if evaluation else [],
        }

    def mock_analyze_demand(evaluations: list, product_name: str, config: dict) -> dict:
        return {"metrics": mock_metrics}

    def mock_save_report(
        product_name: str,
        product_description: str,
        num_personas: int,
        metrics: DemandMetrics,
        report_path: str,
        config: dict,
    ) -> dict:
        # Create the report file for testing
        from pathlib import Path
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_product_name = "".join(
            c if c.isalnum() or c in ("-", "_") else "_" for c in product_name
        )
        filename = f"demand_eval_{safe_product_name}_{timestamp}.md"
        report_dir = Path(report_path)
        report_dir.mkdir(parents=True, exist_ok=True)
        report_file = report_dir / filename
        report_file.write_text("# Mock Report\n", encoding="utf-8")
        return {"final_metrics": metrics}

    # Function mapping for the workflow
    FN_MAP = {
        "generate_personas": mock_generate_personas,
        "process_next_persona": mock_process_next_persona,
        "get_purchase_intent": mock_get_purchase_intent,
        "calculate_persona_metrics": mock_calculate_persona_metrics,
        "collect_evaluations": mock_collect_evaluations,
        "analyze_demand": mock_analyze_demand,
        "save_report": mock_save_report,
    }

    # Run the workflow
    report_path = tmp_path / "reports"
    result = run_workflow(
        "workflow_definitions/demand_eval_workflow/demand_eval_workflow.wirl",
        fn_map=FN_MAP,
        params={
            "product_name": "Smart Watch",
            "product_description": "Advanced fitness tracking smartwatch",
            "num_personas": 2,
            "report_path": str(report_path),
        },
    )

    # Assert workflow outputs
    assert "AnalyzeDemand.metrics" in result
    metrics = result["AnalyzeDemand.metrics"]
    assert metrics.mean_purchase_intent == 3.85
    assert metrics.total_personas == 2
    assert metrics.high_intent_percentage == 50.0

    # Assert evaluations were collected
    assert "EvaluationLoop.evaluations" in result
    evaluations = result["EvaluationLoop.evaluations"]
    assert len(evaluations) == 2
    assert evaluations[0].purchase_intent == 4.5
    assert evaluations[1].purchase_intent == 3.2

    # Assert report was created
    assert report_path.exists()
    report_files = list(report_path.glob("demand_eval_*.md"))
    assert len(report_files) == 1
