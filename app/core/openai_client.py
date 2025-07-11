import asyncio
import httpx
import json
import os
import random
import time
import re
from typing import Any, Dict, List, Optional

import pandas as pd
from pydantic_settings import BaseSettings


class OpenAISettings(BaseSettings):
    api_key: str = os.getenv("OPENAI_API_KEY", "")
    model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


class OpenAIClient:
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.openai.com/v1/chat/completions"
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    async def ask_llm(
        self,
        prompt: str,
        model: Optional[str] = None,
        max_tokens: int = 850,
        retries: int = 5,
        base_delay: int = 1,
    ) -> Dict[str, Any]:
        model = model or self.model
        for attempt in range(retries):
            try:
                async with httpx.AsyncClient() as client:
                    payload = {
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": max_tokens,
                    }
                    response = await client.post(
                        self.base_url, headers=self.headers, json=payload, timeout=60
                    )
                    response.raise_for_status()
                    content = response.json()["choices"][0]["message"]["content"]

                    # Extract JSON from markdown code block if present
                    match = re.search(r"```(json)?\s*([\s\S]*?)\s*```", content)
                    if match:
                        json_str = match.group(2)
                    else:
                        # Fallback to finding the first and last brace/bracket
                        start = content.find("{")
                        if start == -1:
                            start = content.find("[")

                        end = content.rfind("}") + 1
                        if end == 0:
                            end = content.rfind("]") + 1

                        if start == -1 or end <= start:
                            raise json.JSONDecodeError(
                                "No JSON object found in response", content, 0
                            )
                        json_str = content[start:end].strip()

                    return json.loads(json_str)
            except (httpx.HTTPError, json.JSONDecodeError) as e:
                if attempt == retries - 1:
                    raise
                delay = base_delay * (2**attempt) + random.uniform(0, 1)
                await asyncio.sleep(delay)

    async def get_common_misconceptions(
        self, question: str, wrong_answers: List[str], correct_answers_sample: List[str]
    ) -> Dict[str, Any]:
        wrong_answers_text = "\n".join([str(ans) for ans in wrong_answers if ans])
        correct_answers_sample = list(
            set([str(ans) for ans in correct_answers_sample if ans])
        )
        correct_answers_text = "\n".join(correct_answers_sample)

        prompt = (
            f"The following question had the given wrong answers. "
            f"Identify the common misconception from these answers and provide a paraphrased explanation. Not all the wrong answers are part of the common misconception; the common misconception is a theme repeated among the wrong answers, so it appears as a subset of the given answers.\n\n"
            f"**Question:** {question}\n\n"
            f"**Wrong Answers:**\n{wrong_answers_text}\n\n"
            f"Now, please analyze the wrong answers and output your result as a single JSON object with the following keys:\n"
            f'- "misconception": a brief description of the common misconception.\n'
            f'- "count": the number of times this misconception appears in the list of wrong answers.\n\n'
            f"**Example Output:**\n"
            f'{{"misconception": "The first president of Uganda is Museveni", "count": 5}}\n\n'
            f"Do not include any additional text or formatting; only output the JSON object as shown.\n\n"
            f"Below is a sample of correct answers. It should help guide you to evaluate what the misconceptions above are. Please note that an AI transcriber picked the data above (misconcpetions) and so it could have incorrectly added some to the list.\n"
            f"{correct_answers_text}"
        )

        result = await self.ask_llm(prompt)
        misconception = result.get("misconception", "")
        count = int(result.get("count", 0))
        return {"misconception": misconception, "count": count}

    async def get_question_topics(
        self, questions_chunk: List[Dict], subject_name: str, topics: List[str]
    ) -> List[Dict]:
        prompt = (
            f"Given the following questions from a {subject_name} exam, classify each into one of these topics:\n"
            f"{', '.join(topics)}\n\n"
            "Provide your response as a JSON array, where each object corresponds to a question and has these keys:\n"
            "- question_no: The question number\n"
            "- topic: The most relevant topic from the list above\n"
            "- confidence: A number between 0 and 1 indicating confidence in classification\n"
            "- explanation: A brief explanation of why this topic was chosen\n\n"
            "Questions:\n"
        )

        for q in questions_chunk:
            prompt += f"- Question No: {q['Question No']}, Question: {q['Question']}\n"
        prompt += "\nOutput only the JSON array.\nLeave the Question No as given (e.g., '41(a)', '41(b)(ii)'), and do not convert them to plain integers."

        return await self.ask_llm(prompt, max_tokens=2500)
    
    async def ask_exam_page_image(self, base64_image: str, last_known_student_name: str, retries: int = 6, delay: int = 16) -> Optional[Dict[str, Any]]:
        """Send exam page image to OpenAI with dynamic prompt and retry logic."""
        attempt = 0
        while attempt < retries:
            try:
                prompt_text = (
                    f"In this image, first identify if there is a field at the top of the page explicitly "
                    f"labelled 'Name' followed by a colon or on the right of a label 'Name:' on the same line. "
                    f"If such a label exists and a name immediately follows it on the same line, extract that "
                    f"name and assign it as the value of 'studentName' in the output JSON object. "
                    f"If the Name label is not followed by a name on the same line or if the label does not "
                    f"exist, use '{last_known_student_name}' as the studentName. For the rest of the content, "
                    f"transcribe only the exam questions into an array of entries. Each entry must be a JSON "
                    f"object with exactly the following keys: 'questionNo', 'question', 'answer', and 'grading'. "
                    f"The output must be a valid JSON object with the following structure:\n"
                    f'{{ "studentName": "<Extracted or default name>", "entries": [ {{ "questionNo": "<Question number>", '
                    f'"question": "<Question text>", "answer": "<Answer text>", "grading": "<Correct/Incorrect/Not Graded or '
                    f'empty string>" }}, ... ] }} '
                    f"For questions with multiple parts (e.g., 36(a)), if there are multiple answers, produce a separate entry "
                    f"for each answer, repeating the question text for each part. If a question provides an option to answer "
                    f"either one part or the other, transcribe only the part that was answered. If the student hasn't answered, "
                    f"leave the 'answer' field empty. Grade each answer as 'Correct' if there is a red tick mark. If an answer "
                    f"has any marks other than a red tick mark and does not have a red tick mark, treat it as 'Incorrect'. "
                    f"If an answer contains a red tick mark along with other marks, treat it as 'Correct'. If no mark is present "
                    f"at all, grade it as 'Not Graded'. Ensure no extra spaces are added at the beginning or end of any text values, "
                    f"and ignore any non-exam instructions."
                )

                payload = {
                    "model": "ft:gpt-4o-2024-08-06:personal:my-answersheet-experiment-28-12-2024:AjKchLD0",
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt_text},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{base64_image}",
                                        "detail": "high",
                                    },
                                },
                            ],
                        }
                    ],
                    "max_tokens": 850,
                }

                async with httpx.AsyncClient() as client:
                    response = await client.post(self.base_url, headers=self.headers, json=payload, timeout=60)
                    response.raise_for_status()
                    raw_content = response.json()["choices"][0]["message"]["content"]

                # Extract JSON portion
                start = raw_content.find("{")
                end = raw_content.rfind("}") + 1
                if start == -1 or end <= start:
                    raise json.JSONDecodeError("No JSON found in response", raw_content, 0)

                json_str = raw_content[start:end].strip()
                json_str = json_str.replace("```json", "").replace("```", "").strip()

                parsed_response = json.loads(json_str)

                # Validate keys
                if not ("studentName" in parsed_response and "entries" in parsed_response):
                    raise KeyError("Response missing required keys")

                return parsed_response

            except (httpx.HTTPError, json.JSONDecodeError, KeyError) as e:
                if attempt == retries - 1:
                    raise
                await asyncio.sleep(delay)
                delay *= 2
                attempt += 1

        return None




settings = OpenAISettings()
openai_client = OpenAIClient(settings.api_key, settings.model)


def analyse_results(data: pd.DataFrame) -> pd.DataFrame:
    """Analyze exam results and return a DataFrame with aggregated statistics."""
    # Example aggregation: count answers per grading
    if data.empty:
        return data

    summary = data.groupby(["Grading"]).size().reset_index(name="Count")
    return summary
