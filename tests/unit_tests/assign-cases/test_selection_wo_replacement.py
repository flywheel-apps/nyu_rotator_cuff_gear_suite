import ast
import json
from pathlib import Path

import bson
import numpy as np
import pandas as pd

from gears.assign_cases.utils.manage_cases import select_readers_without_replacement

DATA_ROOT = Path(__file__).parents[2] / "data"


def prelims():
    # Set the random seed
    np.random.seed(3141592653)
    # Testing an unassigned session first
    with open(DATA_ROOT / "session_features.json", "r") as sf_json:
        session_features = json.load(sf_json)
    dest_projects_df = pd.read_csv(DATA_ROOT / "dest_projects_df.csv")
    return session_features, dest_projects_df


def test_unassigned_session():
    session_features, dest_projects_df = prelims()

    assign_reader_projs = select_readers_without_replacement(
        session_features, dest_projects_df
    )

    assert assign_reader_projs == [
        "5eba0eb0bfda5102316aa098",
        "5eba0eb2bfda5102356aa06d",
        "5eba0eb1bfda5102356aa06a",
    ]


def test_reader_assigned_shift():
    session_features, dest_projects_df = prelims()

    dest_projects_df.num_assignments = 1
    dest_projects_df.num_assignments[3] = 0

    assign_reader_projs = select_readers_without_replacement(
        session_features, dest_projects_df
    )

    print(assign_reader_projs)

    assert assign_reader_projs == [
        "5eba0eb1bfda51022d6aa0af",
        "5eba0eb1bfda5102356aa06a",
        "5eba0eb2bfda5102356aa06d",
    ]


def case_df_to_session_features(case):
    return {
        "case_coverage": case.case_coverage,
        "assignments": ast.literal_eval(case.assignments),
        "assigned_count": case.assigned_count,
    }


def assign_cases_to_readers(dest_projects_df, source_sessions_df):
    for sess_indx in source_sessions_df.index:
        session_features = case_df_to_session_features(
            source_sessions_df.loc[sess_indx]
        )
        assign_reader_projs = select_readers_without_replacement(
            session_features, dest_projects_df
        )
        for project_id in assign_reader_projs:
            proj_indx = dest_projects_df[dest_projects_df.id == project_id].index[0]
            reader_id = dest_projects_df.loc[proj_indx, "reader_id"]
            project_id = dest_projects_df.loc[proj_indx, "id"]
            dest_session_id = str(bson.ObjectId())
            lst = ast.literal_eval(dest_projects_df.loc[proj_indx, "assignments"])
            lst.append(
                {
                    "source_session": source_sessions_df.loc[sess_indx].id,
                    "dest_session": dest_session_id,
                }
            )
            dest_projects_df.loc[proj_indx, "assignments"] = str(lst)
            dest_projects_df.loc[proj_indx, "num_assignments"] += 1

            session_features["assigned_count"] += 1
            session_features["assignments"].append(
                {
                    "project_id": project_id,
                    "reader_id": reader_id,
                    "session_id": dest_session_id,
                    "status": "Assigned",
                }
            )

        source_sessions_df.loc[sess_indx, "assigned_count"] = session_features[
            "assigned_count"
        ]
        source_sessions_df.loc[sess_indx, "assignments"] = str(
            session_features["assignments"]
        )


def test_single_master_single_distribution():
    """
    Perform the first method of distributing cases to readers as outlined in README.

    1. Single Master Project with Single Distribution.
    """
    dest_projects_df = pd.read_csv(
        DATA_ROOT / "assign_cases/unit_test_csv" / "reader_project_case_data.csv"
    )
    source_sessions_df = pd.read_csv(
        DATA_ROOT / "assign_cases/unit_test_csv" / "master_project_case_data.csv"
    )

    assign_cases_to_readers(dest_projects_df, source_sessions_df)

    assert dest_projects_df["num_assignments"].sum() == 1560
    assert source_sessions_df["assigned_count"].sum() == 1560
    assert source_sessions_df["assigned_count"].unique() == [3]
    assert dest_projects_df["num_assignments"].unique() == [120]


def test_single_master_multi_distributions():
    """
    Perform the second method of distributing cases to readers as outlined in README.

    2. Single Master Project with Multiple Distributions.
    """
    dest_projects_df = pd.read_csv(
        DATA_ROOT / "assign_cases/unit_test_csv" / "reader_project_case_data.csv"
    )
    source_sessions_df = pd.read_csv(
        DATA_ROOT / "assign_cases/unit_test_csv" / "master_project_case_data.csv"
    )

    max_cases = 0
    np.random.seed(3231)
    for i in range(7):
        max_cases += 20
        max_case = min(max_cases, 120)

        for indx in dest_projects_df.index:
            dest_projects_df.loc[indx, "max_cases"] = max_cases

        assign_cases_to_readers(dest_projects_df, source_sessions_df)

        if dest_projects_df["num_assignments"].sum() == 1560:
            break

    assert dest_projects_df["num_assignments"].sum() == 1560
    assert source_sessions_df["assigned_count"].sum() == 1560
    assert source_sessions_df["assigned_count"].unique() == [3]
    assert dest_projects_df["num_assignments"].unique() == [120]


def test_multi_master_multi_distributions():
    """
    Perform the third method of distributing cases to readers as is outline in README.

    3. Multiple Masters Projects with Multiple Distributions.
    """
    dest_projects_df = pd.read_csv(
        DATA_ROOT / "assign_cases/unit_test_csv" / "reader_project_case_data.csv"
    )
    source_sessions_df = pd.read_csv(
        DATA_ROOT / "assign_cases/unit_test_csv" / "master_project_case_data.csv"
    )

    np.random.seed(2)
    batch_start = 0
    for i in range(7):
        if i % 2 == 0:
            batch_size = 87
        else:
            batch_size = 85

        max_end = min(batch_start + batch_size, source_sessions_df.shape[0])

        batch_df = source_sessions_df.iloc[batch_start:max_end, :].copy()

        assign_cases_to_readers(dest_projects_df, batch_df)

        batch_start += batch_size
        assert batch_df["assigned_count"].unique() == [3]

    assert dest_projects_df["num_assignments"].sum() == 1560
    assert dest_projects_df["num_assignments"].unique() == [120]


def test_multi_master_multi_distributions_w_mixed_max_cases():
    """
    Perform the third method of distributing cases to readers as is outline in README.

    3. Multiple Masters Projects with Multiple Distributions.

    However, demonstrate failure when varying
    A. max_cases across readers and
    B. having two readers start 1 cycle late
    """
    dest_projects_df = pd.read_csv(
        DATA_ROOT / "assign_cases/unit_test_csv" / "reader_project_case_data.csv"
    )
    source_sessions_df = pd.read_csv(
        DATA_ROOT / "assign_cases/unit_test_csv" / "master_project_case_data.csv"
    )

    np.random.seed(2)
    batch_start = 0
    max_cases = 0
    late_readers = [11, 12]
    all_batches_valid = True
    for i in range(7):
        if i % 2 == 0:
            batch_size = 91
            max_cases += 21
        else:
            batch_size = 78
            max_cases += 18

        max_end = min(batch_start + batch_size, source_sessions_df.shape[0])

        for indx in dest_projects_df.index:
            if i < 1 and indx in late_readers:
                dest_projects_df.loc[indx, "max_cases"] = 0
            else:
                dest_projects_df.loc[indx, "max_cases"] = max_cases

        batch_df = source_sessions_df.iloc[batch_start:max_end, :]

        assign_cases_to_readers(dest_projects_df, batch_df)

        batch_start += batch_size

        all_batches_valid = bool(
            all_batches_valid * all(batch_df["assigned_count"].unique() == [3])
        )

    assert dest_projects_df["num_assignments"].sum() is not 1560
    assert dest_projects_df["num_assignments"].unique() is not [120]
    assert not all_batches_valid
