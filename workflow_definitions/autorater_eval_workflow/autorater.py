from typing import Literal

from langchain_ollama import ChatOllama
from pydantic import BaseModel, Field


class EvaluationResult(BaseModel):
    explanation: str = Field(
        description="Step-by-step explanation of the evaluation process"
    )
    result: Literal["sufficient", "insufficient"] = Field(
        description="Whether the context is sufficient or insufficient to infer the answer to the question"
    )


def get_prompt(question: str, context: str) -> str:
    return f"""You are an expert LLM evaluator that excels at evaluating a QUESTION and REFERENCES.
Consider the following criteria:
Sufficient Context: "sufficient" IF the CONTEXT is sufficient to infer the answer to the question and "insufficient"
IF the CONTEXT cannot be used to infer the answer to the question
Assume the queries have timestamp <TIMESTAMP>.
First, output a list of step-by-step questions that would be used to arrive at a label for the
criteria. Make sure to include questions about assumptions implicit in the QUESTION.
Include questions about any mathematical calculations or arithmetic that would be required.
Next, answer each of the questions. Make sure to work step by step through any required
mathematical calculations or arithmetic. Finally, use these answers to evaluate the criteria.
Output the ### EXPLANATION (Text). Then, use the EXPLANATION to output the ###
EVALUATION (JSON)
EXAMPLE:
### QUESTION
In which year did the publisher of Roald Dahl's Guide to Railway Safety cease to exist?
### References
Roald Dahl's Guide to Railway Safety was published in 1991 by the British Railways Board.
The British Railways Board had asked Roald Dahl to write the text of the booklet, and
Quentin Blake to illustrate it, to help young people enjoy using the railways safely. The
British Railways Board (BRB) was a nationalised industry in the United Kingdom that
operated from 1963 to 2001. Until 1997 it was responsible for most railway services in Great
Britain, trading under the brand name British Railways and, from 1965, British Rail. It
did not operate railways in Northern Ireland, where railways were the responsibility of the
Government of Northern Ireland.
### EXPLANATION
The context mentions that Roald Dahl's Guide to Railway Safety was published by the
British Railways Board. It also states that the British Railways Board operated from 1963 to
2001, meaning the year it ceased to exist was 2001. Therefore, the context does provide a
precise answer to the question.
### JSON with "result" field with value "sufficient" or "insufficient"
Remember the instructions: You are an expert LLM evaluator that excels at evaluating a
QUESTION and REFERENCES. Consider the following criteria:
Sufficient Context: "sufficient" IF the CONTEXT is sufficient to infer the answer to the question and "insufficient"
IF the CONTEXT cannot be used to infer the answer to the question
Assume the queries have timestamp TIMESTAMP.
First, output a list of step-by-step questions that would be used to arrive at a label for the
criteria. Make sure to include questions about assumptions implicit in the QUESTION
Include questions about any mathematical calculations or arithmetic that would be required.
Next, answer each of the questions. Make sure to work step by step through any required
mathematical calculations or arithmetic. Finally, use these answers to evaluate the criteria.
Output the ### EXPLANATION (Text). Then, use the EXPLANATION to output the ###
EVALUATION (JSON)

### QUESTION\n{question}\n

#### REFERENCES\n{context}\n
"""


def autorate(
    question: str,
    context: str,
    *,
    model: str = "gemma3:12b",
    temperature: float = 0,
    reasoning: bool = False,
) -> Literal["sufficient", "insufficient"]:
    llm = ChatOllama(
        model=model,
        temperature=temperature,
        reasoning=reasoning,
        validate_model_on_init=True,
    )

    llm_with_structure = llm.with_structured_output(
        EvaluationResult, method="json_schema"
    )

    prompt = get_prompt(question, context)

    try:
        result = llm_with_structure.invoke(prompt)
        return result.result  # type: ignore[attr-defined]
    except Exception:
        # Fallback: try regular invoke and parse the response
        response = llm.invoke(prompt)
        text = getattr(response, "content", str(response)).lower()
        if "sufficient" in text:
            return "sufficient"
        return "insufficient"
