import json
from pathlib import Path

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
