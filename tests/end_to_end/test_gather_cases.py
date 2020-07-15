import ast
import json
import time
from pathlib import Path

import pandas as pd
import pytest

from suite_common import init_gear, purge_reader_group, run_gear_w_config

DATA_ROOT = Path(__file__).parents[1] / "data"


def test_gather_cases_no_readers():
    fw_client, gather_cases_gear = init_gear("gather-cases")

    job, _, _, _ = run_gear_w_config(
        fw_client,
        gather_cases_gear,
        DATA_ROOT / "assign_readers/config.json",
        clear_config=True,
        clear_input=True,
    )
    # this is not failing with respects to non reader projects....
    assert job.state == "failed"


def test_pipeline_injecting_assessment(tmpdir):
    fw_client, assign_readers_gear = init_gear("assign-readers")

    job, _, _, _ = run_gear_w_config(
        fw_client,
        assign_readers_gear,
        DATA_ROOT / "assign_readers/config.json",
        clear_config=True,
    )

    assert job.state == "complete"

    fw_client, assign_cases_gear = init_gear("assign-cases")

    job, session, _, _ = run_gear_w_config(
        fw_client,
        assign_cases_gear,
        DATA_ROOT / "assign_cases/config.json",
        clear_input=True,
    )

    assert job.state == "complete"

    # Wait for the cases to be indexed
    time.sleep(30)

    # inject assessments into the first case of the three readers
    session = session.reload()
    analysis = [
        analysis for analysis in session.analyses if analysis.job.id == job.id
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

    # Run the gather-cases gear
    fw_client, gather_cases_gear = init_gear("gather-cases")

    job, session, _, _ = run_gear_w_config(
        fw_client,
        gather_cases_gear,
        DATA_ROOT / "gather_cases/config.json",
        clear_config=True,
        clear_input=True,
    )

    assert job.state == "complete"

    # check the results
    session = session.reload()
    analysis = [
        analysis for analysis in session.analyses if analysis.job.id == job.id
    ].pop()

    summary_data_csv = "master_project_summary_data.csv"
    analysis.download_file(summary_data_csv, tmpdir / summary_data_csv)

    summary_data_df = pd.read_csv(tmpdir / summary_data_csv)
    # specify the master project from the first source session
    source_session = fw_client.get(summary_data_df.id[0])
    master_project = fw_client.get(source_session.parents.project).reload()
    project_features = master_project.info["project_features"]
    for i in summary_data_df.index:
        source_session = fw_client.get(summary_data_df.id[i])
        session_features = source_session.info["session_features"]
        case_state = project_features["case_states"][i]
        # check master project features
        assert summary_data_df.case_coverage[i] == case_state["case_coverage"]
        assert summary_data_df.assigned[i] == case_state["assigned"]
        assert summary_data_df.unassigned[i] == case_state["unassigned"]
        assert summary_data_df.classified[i] == case_state["classified"]
        assert summary_data_df.measured[i] == case_state["measured"]
        assert summary_data_df.completed[i] == case_state["completed"]
        # check source session features
        assert summary_data_df.assigned[i] == session_features["assigned_count"]
        assert summary_data_df.case_coverage[i] == session_features["case_coverage"]

    # Ensure ohifViewer data was migrated to the correct session
    for i in reader_df.index:
        csv_assignments = ast.literal_eval(reader_df.assignments[i])
        for j in range(5):
            source_session = fw_client.get(
                csv_assignments[j]["source_session"]
            ).reload()
            assignments = source_session.info["session_features"]["assignments"]
            reader_project_id = reader_df.id[i]
            assignment = [
                assignment
                for assignment in assignments
                if assignment["project_id"] == reader_project_id
            ].pop()
            if assignment.get("read"):
                read = measurements[assessment_keys[j]]["ohifViewer"]["read"]
                assert assignment["read"] == read
            if assignment.get("measurements"):
                measurement = measurements[assessment_keys[j]]["ohifViewer"][
                    "measurements"
                ]
                assert assignment["measurements"] == measurement

    # Cleanup
    purge_reader_group(fw_client)
