import ast
import json
import time
from pathlib import Path

import pandas as pd
import pytest

from suite_common import init_gear, purge_reader_group, run_gear_w_config

DATA_ROOT = Path(__file__).parents[1] / "data"


def test_no_readers():
    fw_client, assign_cases_gear = init_gear("assign-single-case")

    job, _, _, _ = run_gear_w_config(
        fw_client,
        assign_cases_gear,
        DATA_ROOT / "assign_single_case/config.json",
        clear_input=True,
    )

    assert job.state == "failed"


def test_valid_reader():

    # assign reader
    fw_client, assign_readers_gear = init_gear("assign-readers")

    job, _, _, _ = run_gear_w_config(
        fw_client,
        assign_readers_gear,
        DATA_ROOT / "assign_readers/config.json",
        clear_input=True,
    )

    # Assign to valid reader
    fw_client, assign_single_case_gear = init_gear("assign-single-case")
    job, _, _, _ = run_gear_w_config(
        fw_client,
        assign_single_case_gear,
        DATA_ROOT / "assign_single_case/config.json",
        clear_input=True,
    )

    assert job.state == "complete"

    # Assign to invalid reader
    config = {
        "reader_email": "joshuajacobs@flywheel.io",
        "assignment_reason": "Individual Assignment",
    }

    job, _, _, _ = run_gear_w_config(
        fw_client,
        assign_single_case_gear,
        DATA_ROOT / "assign_single_case/config.json",
        clear_input=True,
        replace_config=config,
    )

    assert job.state == "failed"

    # Cleanup
    purge_reader_group(fw_client)


def assign_readers_max_cases(tmpdir):
    fw_client, assign_readers_gear = init_gear("assign-readers")

    _, _, _, _ = run_gear_w_config(
        fw_client,
        assign_readers_gear,
        DATA_ROOT / "assign_readers/config.json",
        clear_config=True,
    )

    fw_client, assign_cases_gear = init_gear("assign-cases")

    job, destination, _, _ = run_gear_w_config(
        fw_client,
        assign_cases_gear,
        DATA_ROOT / "assign_cases/config.json",
        clear_input=True,
    )
    # Inject assessments

    # Wait for the cases to be indexed
    time.sleep(30)

    # inject assessments into the first case of the three readers
    destination = destination.reload()
    analysis = [
        analysis for analysis in destination.analyses if analysis.job.id == job.id
    ].pop()

    measurements = json.load(open(DATA_ROOT / "gather_cases/measurements.json", "r"))
    assessment_keys = [
        "no_tear",
        "low_partial_tear",
        "high_partial_tear",
        "full_tear",
        "full_contig",
    ]

    reader_case_data_csv = "reader_project_case_data.csv"
    analysis.download_file(reader_case_data_csv, tmpdir / reader_case_data_csv)

    reader_df = pd.read_csv(tmpdir / reader_case_data_csv)
    for i in reader_df.index:
        reader_project = fw_client.get(reader_df.id[i]).reload()
        project_features = reader_project.info["project_features"]
        for j in range(5):
            assignment = project_features["assignments"][j]
            dest_session = fw_client.get(assignment["dest_session"])
            dest_session.update_info(measurements[assessment_keys[j]])


def test_indiv_assignment(tmpdir):
    assign_readers_max_cases(tmpdir)

    # assign single reader
    fw_client, assign_readers_gear = init_gear("assign-readers")

    job, _, _, _ = run_gear_w_config(
        fw_client,
        assign_readers_gear,
        DATA_ROOT / "assign_readers/config.json",
        clear_input=True,
    )
    assert job.state == "complete"

    # assign indiv assignment to that reader
    fw_client, assign_single_case_gear = init_gear("assign-single-case")
    job, _, _, _ = run_gear_w_config(
        fw_client,
        assign_single_case_gear,
        DATA_ROOT / "assign_single_case/config.json",
        clear_input=True,
    )

    assert job.state == "complete"

    # attempt to re-assign the same session
    job, _, _, _ = run_gear_w_config(
        fw_client,
        assign_single_case_gear,
        DATA_ROOT / "assign_single_case/config.json",
        clear_input=True,
    )

    assert job.state == "failed"

    # attempt to assign num_cases=case_coverage to new reader
    job, _, _, _ = run_gear_w_config(
        fw_client,
        assign_single_case_gear,
        DATA_ROOT / "assign_single_case/config_full_case.json",
        clear_input=True,
    )
    assert job.state == "failed"

    # attempt to assign case to num_cases=max_cases of full reader
    job, _, _, _ = run_gear_w_config(
        fw_client,
        assign_single_case_gear,
        DATA_ROOT / "assign_single_case/config_full_reader.json",
        clear_input=True,
    )

    assert job.state == "failed"

    # Cleanup
    purge_reader_group(fw_client)


def test_resolve_tie(tmpdir):
    assign_readers_max_cases(tmpdir)

    # assign single reader
    fw_client, assign_readers_gear = init_gear("assign-readers")

    job, _, _, _ = run_gear_w_config(
        fw_client,
        assign_readers_gear,
        DATA_ROOT / "assign_readers/config.json",
        clear_input=True,
    )

    fw_client, assign_single_case_gear = init_gear("assign-single-case")
    # Assign assigned_cases=3=case_coverage to new reader.
    job, _, _, _ = run_gear_w_config(
        fw_client,
        assign_single_case_gear,
        DATA_ROOT / "assign_single_case/config_tie_breaker_1.json",
        clear_input=True,
    )

    assert job.state == "complete"

    # Assign assigned_cases=4=case_coverage to new reader.
    job, _, _, _ = run_gear_w_config(
        fw_client,
        assign_readers_gear,
        DATA_ROOT / "assign_readers/config_nancy.json",
        clear_input=True,
    )

    job, _, _, _ = run_gear_w_config(
        fw_client,
        assign_single_case_gear,
        DATA_ROOT / "assign_single_case/config_tie_breaker_2.json",
        clear_input=True,
    )

    assert job.state == "failed"

    # Assign assigned_cases < 3 to a new reader
    job, _, _, _ = run_gear_w_config(
        fw_client,
        assign_single_case_gear,
        DATA_ROOT / "assign_single_case/config_tie_breaker_3.json",
        clear_input=True,
    )

    assert job.state == "failed"

    # Cleanup
    purge_reader_group(fw_client)


def test_apply_consensus_assignment(tmpdir):
    assign_readers_max_cases(tmpdir)

    fw_client, assign_single_case_gear = init_gear("assign-single-case")
    # test valid and invalid application of consensus assignment

    # Apply existing consensus assessment to particular reader
    job, _, _, _ = run_gear_w_config(
        fw_client,
        assign_single_case_gear,
        DATA_ROOT / "assign_single_case/config_consensus_1.json",
        clear_input=True,
    )

    assert job.state == "complete"

    # Attempt to apply non-existent consensus assessment to particular reader
    job, _, _, _ = run_gear_w_config(
        fw_client,
        assign_single_case_gear,
        DATA_ROOT / "assign_single_case/config_consensus_2.json",
        clear_input=True,
    )

    assert job.state == "failed"

    # Attempt to apply consensus assessment to a reader without the indicated case
    fw_client, assign_readers_gear = init_gear("assign-readers")

    _, _, _, _ = run_gear_w_config(
        fw_client,
        assign_readers_gear,
        DATA_ROOT / "assign_readers/config.json",
        clear_input=True,
    )

    job, _, _, _ = run_gear_w_config(
        fw_client,
        assign_single_case_gear,
        DATA_ROOT / "assign_single_case/config_consensus_3.json",
        clear_input=True,
    )

    assert job.state == "failed"

    # Cleanup
    purge_reader_group(fw_client)
