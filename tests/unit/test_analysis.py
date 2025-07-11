import pandas as pd
from app.core.analysis import clean_transcribed_data

def test_clean_transcribed_data():
    df = pd.DataFrame({
        "ClassName": ["(A)", "[B]"],
        "SubjectName": ["'Math'", "Science"],
        "Question": ["1. a", "Question No"],
        "ScanPageNo": [1, 2],
    })
    cleaned = clean_transcribed_data(df)
    assert "Question No" not in cleaned["Question"].values
    assert all("(" not in c for c in cleaned["ClassName"]])
    assert all("'" not in c for c in cleaned["SubjectName"]])
    assert cleaned.shape[0] == 1
