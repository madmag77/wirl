import argparse
import json
from typing import Literal

from llama_index.llms.ollama import Ollama
from llama_index.llms.openai import OpenAI


def get_prompt(question: str, context: str) -> str:
    return f"""You are an expert LLM evaluator that excels at evaluating a QUESTION and REFERENCES.
Consider the following criteria:
Sufficient Context: 1 IF the CONTEXT is sufficient to infer the answer to the question and 0
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
### JSON with one field "Sufficient Context" with value 1 or 0
Remember the instructions: You are an expert LLM evaluator that excels at evaluating a
QUESTION and REFERENCES. Consider the following criteria:
Sufficient Context: 1 IF the CONTEXT is sufficient to infer the answer to the question and 0
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
    model_type: str = "ollama",
    base_url: str = "http://127.0.0.1:1234",
) -> Literal["sufficient", "insufficient"]:
    if model_type.lower() == "lmstudio":
        # For LM Studio, we need to use a generic OpenAI model name
        # since the OpenAI client validates against known OpenAI models
        # LM Studio will ignore the model name and use whatever model is loaded
        llm = OpenAI(
            model="gpt-3.5-turbo",  # Use a valid OpenAI model name as placeholder
            api_base=base_url,
            api_key="lm-studio",  # LM Studio doesn't require a real API key
            json_mode=True,
            request_timeout=120.0,
        )
    else:  # default to ollama
        llm = Ollama(model=model, json_mode=True, request_timeout=120.0)

    prompt = get_prompt(question, context)
    completion = llm.complete(prompt)
    try:
        result = json.loads(completion.model_dump_json())["Sufficient Context"]
        return "sufficient" if int(result) == 1 else "insufficient"
    except Exception:
        text = completion.text.lower()
        if "1" in text:
            return "sufficient"
        return "insufficient"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Classify if context is sufficient")
    parser.add_argument("question", help="Question text")
    parser.add_argument("context", help="Context text")
    parser.add_argument("--model", default="gemma3:12b", help="Model name")
    parser.add_argument(
        "--model-type",
        default="ollama",
        choices=["ollama", "lmstudio"],
        help="Model type: ollama or lmstudio",
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:1234/v1",
        help="Base URL for LM Studio API (default: http://localhost:1234/v1)",
    )
    args = parser.parse_args()
    label = autorate(
        args.question,
        args.context,
        model=args.model,
        model_type=args.model_type,
        base_url=args.base_url,
    )
    print(label)
