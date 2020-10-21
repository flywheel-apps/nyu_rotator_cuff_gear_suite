import ast
from pathlib import Path

import pandas as pd
import pytest

from suite_common import init_gear, purge_reader_group, run_gear_w_config

DATA_ROOT = Path(__file__).parents[1] / "data"


def test_no_readers():
    fw_client, assign_cases_gear = init_gear("assign-batch-cases")

    job, _, _, _ = run_gear_w_config(
        fw_client,
        assign_cases_gear,
        DATA_ROOT / "assign_batch_cases/no_errors_config.json",
        clear_config=True,
    )

    assert job.state == "failed"


def test_no_errors():
    fw_client, assign_readers_gear = init_gear("assign-readers")

    job, _, _, _ = run_gear_w_config(
        fw_client,
        assign_readers_gear,
        DATA_ROOT / "assign_readers/config.json",
        clear_config=True,
    )

    assert job.state == "complete"

    fw_client, assign_cases_gear = init_gear("assign-batch-cases")

    job, _, _, _ = run_gear_w_config(
        fw_client,
        assign_cases_gear,
        DATA_ROOT / "assign_batch_cases/no_errors_config.json",
        clear_config=True,
    )

    assert job.state == "complete"
    # Cleanup
    purge_reader_group(fw_client)


def test_each_error_w_one_success(tmpdir):
    fw_client, assign_readers_gear = init_gear("assign-readers")

    job, _, _, _ = run_gear_w_config(
        fw_client,
        assign_readers_gear,
        DATA_ROOT / "assign_readers/config.json",
        clear_config=True,
    )

    assert job.state == "complete"

    # Assign one more reader for testing case_coverage
    job, _, _, _ = run_gear_w_config(
        fw_client,
        assign_readers_gear,
        DATA_ROOT / "assign_readers/config_nancy.json",
        clear_input=True,
    )

    assert job.state == "complete"

    fw_client, assign_cases_gear = init_gear("assign-batch-cases")

    job, container, _, _ = run_gear_w_config(
        fw_client,
        assign_cases_gear,
        DATA_ROOT / "assign_batch_cases/one_success_else_err_config.json",
        clear_config=True,
    )

    assert job.state == "complete"

    # Grab results file
    container = container.reload()

    analysis = [
        analysis for analysis in container.analyses if analysis.job.id == job.id
    ].pop()

    batch_results_csv = "batch_results.csv"
    analysis.download_file(batch_results_csv, tmpdir / batch_results_csv)
    batch_results_df = pd.read_csv(tmpdir / batch_results_csv)

    reader_case_data_csv = "reader_project_case_data.csv"
    analysis.download_file(reader_case_data_csv, tmpdir / reader_case_data_csv)
    reader_case_data_df = pd.read_csv(tmpdir / reader_case_data_csv)

    # Valid Session
    indx = 15
    session_id = batch_results_df.loc[indx, "session_id"]
    reader_email = batch_results_df.loc[indx, "reader_email"]

    message = (
        f"Session with id ({session_id}) is not found in this Master Project. "
        f"Proceeding without making this assignment to reader ({reader_email})."
    )

    assert bool(batch_results_df.loc[indx, "passed"]) is False
    assert batch_results_df.loc[indx, "message"] == message

    # Valid Reader Project
    indx = 16
    reader_email = batch_results_df.loc[indx, "reader_email"]
    message = (
        f"The reader ({reader_email}) has not been established. "
        "Please run `assign-readers` to establish a project for this reader"
    )
    assert bool(batch_results_df.loc[indx, "passed"]) is False
    assert batch_results_df.loc[indx, "message"] == message

    # Existing Session in Reader Project
    indx = 17
    session_id = batch_results_df.loc[indx, "session_id"]
    session = fw_client.get(session_id)
    session_label = session.label
    reader_email = batch_results_df.loc[indx, "reader_email"]
    message = (
        f"Selected session ({session_label}) has already been assigned to "
        f"reader ({reader_email})."
    )
    assert bool(batch_results_df.loc[indx, "passed"]) is False
    assert batch_results_df.loc[indx, "message"] == message

    # Reader is at capacity (num_assignments == max_cases)
    indx = 18

    reader_email = batch_results_df.loc[indx, "reader_email"]
    max_cases = reader_case_data_df[
        reader_case_data_df.reader_id == reader_email
    ].max_cases[0]
    message = (
        f"Cannot assign more than {max_cases} cases to "
        f"reader ({reader_email}). "
        "Consider increasing max_cases for this reader "
        "or choosing another reader."
    )
    assert bool(batch_results_df.loc[indx, "passed"]) is False
    assert batch_results_df.loc[indx, "message"] == message

    # Session at case_coverage
    indx = 19

    session_id = batch_results_df.loc[indx, "session_id"]
    session = fw_client.get(session_id)
    session_label = session.label
    case_coverage = 3
    message = (
        f"Assigning this case ({session_label}) exceeds "
        f"case_coverage ({case_coverage}) for this case."
        "Assignment will not proceed."
    )

    assert bool(batch_results_df.loc[indx, "passed"]) is False
    assert batch_results_df.loc[indx, "message"] == message

    # Cleanup
    purge_reader_group(fw_client)


def test_all_errors():
    fw_client, assign_readers_gear = init_gear("assign-readers")

    job, _, _, _ = run_gear_w_config(
        fw_client,
        assign_readers_gear,
        DATA_ROOT / "assign_readers/config.json",
        clear_config=True,
    )

    assert job.state == "complete"

    fw_client, assign_cases_gear = init_gear("assign-batch-cases")

    job, _, _, _ = run_gear_w_config(
        fw_client,
        assign_cases_gear,
        DATA_ROOT / "assign_batch_cases/all_errs_config.json",
        clear_config=True,
    )

    assert job.state == "failed"

    # Cleanup
    purge_reader_group(fw_client)

