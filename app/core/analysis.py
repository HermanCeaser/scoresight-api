import asyncio
import pandas as pd
import math
import re
from typing import List, Dict, Tuple

from .openai_client import openai_client


async def detect_common_misconceptions(
    question: str,
    wrong_answers: List[str],
    correct_answers_sample: List[str],
) -> Tuple[str, int]:
    """Detect common misconceptions from wrong answers using OpenAI LLM asynchronously."""
    result = await openai_client.get_common_misconceptions(
        question, wrong_answers, correct_answers_sample
    )
    return result.get("misconception", ""), result.get("count", 0)


def get_main_question_no(q_no: str) -> str:
    """Extract main question number from question number string."""
    if "(" in q_no:
        return q_no.split("(")[0]
    return q_no


def get_sub_question_no(q_no: str) -> str:
    """Extract sub-question number (up to second level) from question number string."""
    if "(" in q_no:
        parts = q_no.split("(")
        return parts[0] + "(" + parts[1].split(")")[0] + ")"
    return q_no


def analyse_results(data: pd.DataFrame) -> pd.DataFrame:
    """Analyze exam results and return a DataFrame with aggregated statistics."""
    # Placeholder for analysis logic
    return data


async def analyze_misconceptions(data: pd.DataFrame) -> pd.DataFrame:
    """Analyze misconceptions in exam data asynchronously."""
    data["Main Question No"] = data["Question No"].apply(get_main_question_no)
    data["Sub Question No"] = data["Question No"].apply(get_sub_question_no)

    grouped = data.groupby(["Sub Question No"])

    results = []

    for name, group in grouped:
        sub_question_no = name
        main_question_no = group["Main Question No"].iloc[0]
        question_text = group["Question"].iloc[0]
        attempts = len(group)
        distinct_students = group["Student Name"].nunique()
        correct_answers = (group["Grading"] == "Correct").sum()
        correct_percentage = (correct_answers / attempts) * 100 if attempts > 0 else 0

        wrong_answers = group[
            (group["Grading"] != "Correct")
            & (pd.notna(group["Answer"]))
            & (group["Answer"].str.strip() != "")
        ]["Answer"].tolist()

        try:
            correct_answers_sample = (
                group[
                    (group["Grading"].str.contains("correct", case=False, na=False))
                    & (pd.notna(group["Answer"]))
                    & (group["Answer"].str.strip() != "")
                ]["Answer"]
                .sample(n=min(10, correct_answers), random_state=1)
                .tolist()
            )
        except ValueError:
            correct_answers_sample = ["No correct answer transcribed"]

        if wrong_answers:
            misconception, frequency = await detect_common_misconceptions(
                question_text, wrong_answers, correct_answers_sample
            )
        else:
            misconception = None
            frequency = 0

        results.append(
            {
                "Main Question No": main_question_no,
                "Question": question_text,
                "Sub Question No": sub_question_no,
                "Attempts": attempts,
                "Distinct Students": distinct_students,
                "Correct Answers": correct_answers,
                "Correct %": f"{correct_percentage:.1f}",
                "Most Common Misconception": misconception,
                "Misconception Frequency": frequency,
            }
        )

    return pd.DataFrame(results)


def analyze_misconceptions_sync(data: pd.DataFrame) -> pd.DataFrame:
    """Synchronous wrapper for analyze_misconceptions async function."""
    return asyncio.run(analyze_misconceptions(data))


def correct_question_number(question_number: str) -> str:
    """
    Correct and format the question number string to a standard format.
    """
    corrected = re.sub(r"(\d+)\.([a-z]+)\.([ivx]+)", r"\1(\2)(\3)", question_number)
    corrected = re.sub(r"(\d+)\.([a-z]+)", r"\1(\2)", corrected)
    corrected = re.sub(r"(\d+)\.\(([a-z])\)\.([ivx]+)", r"\1(\2)(\3)", corrected)
    corrected = re.sub(r"\.\(", "(", corrected)
    corrected = corrected.replace(" ", "")
    return corrected.strip()


def standardize_question_number(question_number: str) -> str:
    """
    Standardize question number formats to a canonical form.
    """
    question_number = re.sub(r"(\d+)([a-z])\((i{1,3}|iv|v{1,2})\)", r"\1(\2)(\3)", question_number)
    question_number = re.sub(r"(\d+)([a-z])", r"\1(\2)", question_number)
    return question_number


def clean_transcribed_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean and standardize transcribed exam data DataFrame.
    """
    df = df.copy()
    df["ClassName"] = df["ClassName"].str.replace(r"[\(\)\[\]\']", "", regex=True)
    df["SubjectName"] = df["SubjectName"].str.replace(r"[\(\)\[\]\']", "", regex=True)
    df["ScanPageNo"] = df["ScanPageNo"].astype(int)
    df["Question No"] = df["Question No"].apply(lambda x: correct_question_number(str(x)))
    df["Question No"] = df["Question No"].apply(standardize_question_number)
    df = df[~df["Question"].str.contains("Question No", na=False)]
    df = df.dropna(subset=["Question"])
    return df


def clean_question_list(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean question list to extract only unique questions and question numbers.
    
    Args:
        df: DataFrame containing questions data
        
    Returns:
        DataFrame with unique questions only
    """
    expected_cols = {'Question No', 'Question'}
    if not expected_cols.issubset(df.columns):
        column_mapping = {}
        for col in df.columns:
            col_lower = col.lower().strip()
            if 'question' in col_lower and 'no' in col_lower:
                column_mapping[col] = 'Question No'
            elif 'question' in col_lower and 'no' not in col_lower:
                column_mapping[col] = 'Question'
        
        if column_mapping:
            df = df.rename(columns=column_mapping)
        else:
            raise ValueError(f"Input file must contain columns: {expected_cols}")

    clean_questions = (
        df.dropna(subset=["Question No", "Question"])
        .assign(**{
            "Question No": lambda df: df["Question No"]
            .apply(lambda x: str(int(x)) if pd.notnull(x) and str(x).replace('.0','').isdigit() else str(x))
        })
    )
    
    unique_by_text = clean_questions.drop_duplicates(subset=["Question"], keep="first").copy()

    def get_base_question_no(q_no: str) -> str:
        q_no_str = str(q_no).strip()
        return re.sub(r'[\s_]*(\([ivx]+\)|[ivx]+)$', '', q_no_str).strip()

    unique_by_text["Question No"] = unique_by_text["Question No"].apply(get_base_question_no)
    
    unique_questions = unique_by_text[["Question No", "Question"]].drop_duplicates()
    
    return unique_questions
