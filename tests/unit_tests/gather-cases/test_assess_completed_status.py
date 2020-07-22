import json
import shutil
import tempfile
from pathlib import Path

import pandas as pd
import pytest
from gear_toolkit import gear_toolkit_context

from gears.gather_cases.utils.manage_cases import assess_completed_status

DATA_ROOT = Path(__file__).parents[2] / "data"


def test_assessment_status():
    measurements = json.load(open(DATA_ROOT / "gather_cases/measurements.json", "r"))
    assessment_keys = [
        "no_tear",
        "low_partial_tear",
        "high_partial_tear",
        "full_tear",
        "full_contig",
    ]
