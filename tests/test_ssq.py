import pandas as pd

from questset_analysis.core import SSQ_COLUMNS, compute_ssq_scores


def test_all_zero_ssq_is_zero():
    row = {"ID": "group1_order1_user0", "Questionnaire number": 1}
    row.update({column: "None" for column in SSQ_COLUMNS.values()})
    result = compute_ssq_scores(pd.DataFrame([row]))
    assert result.loc[0, "SSQ_Total"] == 0
    assert result.loc[0, "SSQ_Nausea"] == 0
