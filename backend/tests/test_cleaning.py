import pandas as pd

from app.services.cleaning import apply_cleaning, build_cleaning_proposal


def test_build_and_apply_cleaning_proposal():
    frame = pd.DataFrame(
        {
            " Sales Value ": [10.0, 12.0, None, 12.0],
            "region": ["East", "West", "East", "West"],
        }
    )
    proposal = build_cleaning_proposal(frame)
    suggestion_ids = {item["id"] for item in proposal["suggestions"]}
    assert "normalize_columns" in suggestion_ids
    assert "fill_missing:: Sales Value " in suggestion_ids

    cleaned, log = apply_cleaning(frame, ["normalize_columns", "fill_missing:: Sales Value "])
    assert "sales_value" in cleaned.columns
    assert cleaned["sales_value"].isna().sum() == 0
    assert len(log) == 2

