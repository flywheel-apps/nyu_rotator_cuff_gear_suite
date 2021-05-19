import json
import shutil
import tempfile
from copy import deepcopy
from pathlib import Path

import pandas as pd
import pytest
from gears.gather_cases.utils.manage_cases import assess_completed_status

DATA_ROOT = Path(__file__).parents[2] / "data"


def get_test_dictionaries(measurements, key):
    ohif_viewer = deepcopy(measurements[key]["ohifViewer"])
    reader_id = list(ohif_viewer["read"].keys())[0]
    user_data = deepcopy(ohif_viewer["read"][reader_id]["notes"])

    return ohif_viewer, user_data


def test_completed_assessment_status():
    measurements = json.load(open(DATA_ROOT / "gather_cases/measurements.json", "r"))
    assessment_keys = [
        "no_tear",
        "low_partial_tear",
        "high_partial_tear",
        "full_tear",
        "full_contig",
    ]
    completion_status = []
    error_msgs = []
    for key in assessment_keys:
        ohif_viewer, user_data = get_test_dictionaries(measurements, key)
        complete, error_msg = assess_completed_status(ohif_viewer, user_data)
        completion_status.append(complete)
        error_msgs.append(error_msg)

    assert completion_status == [True] * len(completion_status)


def test_incomplete_assessment_status():
    measurements = json.load(open(DATA_ROOT / "gather_cases/measurements.json", "r"))
    assessment_keys = [
        "no_tear",
        "low_partial_tear",
        "high_partial_tear",
        "full_tear",
        "full_contig",
    ]

    completion_status = []
    error_msgs = []

    # Remove user_data
    key = "no_tear"
    ohif_viewer, user_data = get_test_dictionaries(measurements, key)
    user_data = None

    complete, error_msg = assess_completed_status(ohif_viewer, user_data)
    completion_status.append(complete)
    error_msgs.append(error_msg)

    # Test for "Meddling"
    key = "no_tear"
    ohif_viewer, user_data = get_test_dictionaries(measurements, key)
    user_data["supraspinatusTear"] = None

    complete, error_msg = assess_completed_status(ohif_viewer, user_data)
    completion_status.append(complete)
    error_msgs.append(error_msg)

    # Remove measurement
    key = "full_tear"
    ohif_viewer, user_data = get_test_dictionaries(measurements, key)
    ohif_viewer.pop("measurements")

    complete, error_msg = assess_completed_status(ohif_viewer, user_data)
    completion_status.append(complete)
    error_msgs.append(error_msg)

    # Remove Length object
    ohif_viewer, user_data = get_test_dictionaries(measurements, key)
    ohif_viewer["measurements"].pop("Length")

    complete, error_msg = assess_completed_status(ohif_viewer, user_data)
    completion_status.append(complete)
    error_msgs.append(error_msg)

    # Remove single Measurement object
    ohif_viewer, user_data = get_test_dictionaries(measurements, key)
    ohif_viewer["measurements"]["Length"].pop(0)

    complete, error_msg = assess_completed_status(ohif_viewer, user_data)
    completion_status.append(complete)
    error_msgs.append(error_msg)

    # Remove fullTear associated with fullContiguous
    key = "full_contig"
    ohif_viewer, user_data = get_test_dictionaries(measurements, key)
    user_data["supraspinatusTear"] = "none"

    complete, error_msg = assess_completed_status(ohif_viewer, user_data)
    completion_status.append(complete)
    error_msgs.append(error_msg)

    # Inject missing "location" error
    key = "full_tear"
    ohif_viewer, user_data = get_test_dictionaries(measurements, key)
    ohif_viewer["measurements"]["Length"][1].pop("location")
    complete, error_msg = assess_completed_status(ohif_viewer, user_data)
    completion_status.append(complete)
    error_msgs.append(error_msg)

    assert completion_status == [False] * len(completion_status)
    assert error_msgs == [None] * (len(error_msgs) - 1) + [
        "ERROR: An error occurred in the case assessment. Please examine and correct."
    ]
