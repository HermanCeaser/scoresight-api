import sys
import pandas as pd
import re
from pathlib import Path

def clean_question_no_old(cell, last_main_number=None, last_contexts=[]):
    """Clean a Question No entry so that after the number, every letter or group
    of roman numerals/letters/words (separated by space, dot, parenthesis, or underscore)
    gets its own parentheses.

    E.g. 54c i → 54(c)(i), 55a ii → 55(a)(ii), 55.a.i → 55(a)(i), etc.
    """
    s = str(cell).strip()
    if pd.isnull(s) or s == "" or s.lower() == 'nan':
        return "", last_main_number, last_contexts

    # Standardize delimiters: replace any sequence of [space . _ ( )] with a single space
    s = re.sub(r'[\s\.\_\)\(]+', ' ', s)
    s = s.strip()

    # Match main number at the start
    main_number_match = re.match(r"^(\d+)", s)
    if main_number_match:
        number = main_number_match.group(1)
        rest = s[len(number):].strip()
        # Split rest by spaces; valid chunks are letters (a-zA-Z), "Either", or roman numerals
        if rest:
            # Handles cases like "a ii", "Either a", "c", "i", "ii", etc.
            contexts = re.findall(r"[A-Za-z]+|Either|[ivxIVX]+", rest)
        else:
            contexts = []
        cleaned_val = number + ''.join(f"({c})" for c in contexts)
        return cleaned_val, number, contexts

    # If the cell doesn't start with a number, try to use the last number context
    if last_main_number:
        # Gather all context chunks
        chunks = re.findall(r"[A-Za-z]+|Either|[ivxIVX]+", s)
        if chunks:
            cleaned_val = last_main_number + ''.join(f"({c})" for c in chunks)
            return cleaned_val, last_main_number, chunks

    # If the cell is just a plain number (shouldn't happen after above, but just in case)
    if re.fullmatch(r"\d+", s):
        return s, s, []

    # Fallback: return as is
    return s, last_main_number, last_contexts


def _split_letter_roman(chunk):
    # If already parenthesized, don't split
    if re.fullmatch(r"\([A-Za-z0-9ivxIVX]+\)", chunk):
        return [chunk]
    # If only roman numerals, or only letters, or "Either", don't split
    if re.fullmatch(r"[ivxIVX]+", chunk) or re.fullmatch(r"[A-Za-z]+", chunk) or chunk == "Either":
        return [chunk]
    # If letter+roman pattern, e.g. 'bii' → ['b', 'ii']
    m = re.fullmatch(r'([a-zA-Z]+)([ivxIVX]+)', chunk)
    if m:
        return [m.group(1), m.group(2)]
    return [chunk]

def clean_question_no(cell, last_main_number=None, last_contexts=[]):
    """
    Clean a Question No entry so that after the number, every letter or group
    of roman numerals/letters/words (separated by space, dot, parenthesis, or underscore)
    gets its own parentheses. Also, split letter-roman combos like 'bii' into (b)(ii).
    """
    s = str(cell).strip()
    if pd.isnull(s) or s == "" or s.lower() == 'nan':
        return "", last_main_number, last_contexts

    # Standardize delimiters: replace any sequence of [space . _ ( )] with a single space
    s = re.sub(r'[\s\.\_\)\(]+', ' ', s)
    s = s.strip()

    # Match main number at the start
    main_number_match = re.match(r"^(\d+)", s)
    if main_number_match:
        number = main_number_match.group(1)
        rest = s[len(number):].strip()
        # Split rest by spaces and detect context chunks
        if rest:
            # Handles things like 'c ii', 'Either a', 'bii', etc.
            raw_contexts = re.findall(r"[A-Za-z]+|Either|[ivxIVX]+|\([A-Za-z0-9ivxIVX]+\)", rest)
        else:
            raw_contexts = []
        # Now enforce the letter+roman split on each chunk
        contexts = []
        for chunk in raw_contexts:
            contexts.extend(_split_letter_roman(chunk))
        cleaned_val = number + ''.join(f"({c})" if not (c.startswith('(') and c.endswith(')')) else c for c in contexts)
        return cleaned_val, number, contexts

    # If the cell doesn't start with a number, try to use the last number context
    if last_main_number:
        raw_contexts = re.findall(r"[A-Za-z]+|Either|[ivxIVX]+|\([A-Za-z0-9ivxIVX]+\)", s)
        contexts = []
        for chunk in raw_contexts:
            contexts.extend(_split_letter_roman(chunk))
        if contexts:
            cleaned_val = last_main_number + ''.join(f"({c})" if not (c.startswith('(') and c.endswith(')')) else c for c in contexts)
            return cleaned_val, last_main_number, contexts

    # If the cell is just a plain number (shouldn't happen after above, but just in case)
    if re.fullmatch(r"\d+", s):
        return s, s, []

    # Fallback: return as is
    return s, last_main_number, last_contexts

def clean_csv(filename):
    df = pd.read_csv(filename)
    cleaned_col = []
    last_main_number = None
    last_contexts = []

    for idx, row in df.iterrows():
        orig = row['Question No']
        cleaned, last_main_number, last_contexts = clean_question_no(
            orig, last_main_number, last_contexts
        )
        cleaned_col.append(cleaned)

    df['Question No'] = cleaned_col
    out_file = f"cleaned_{Path(filename).name}"
    df.to_csv(out_file, index=False)
    print(f"Cleaned file saved as: {out_file}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python clean_question_numbers.py <input_csv>")
        sys.exit(1)
    clean_csv(sys.argv[1])
