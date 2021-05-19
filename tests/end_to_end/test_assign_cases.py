import ast
from pathlib import Path

import pandas as pd
import pytest

from suite_common import init_gear, purge_reader_group, run_gear_w_config

DATA_ROOT = Path(__file__).parents[1] / "data"


def test_no_readers():
    fw_client, assign_cases_gear = init_gear("assign-cases")

    job, _, _, _ = run_gear_w_config(
        fw_client,
        assign_cases_gear,
        DATA_ROOT / "assign_cases/config.json",
        clear_input=True,
    )

    assert job.state == "failed"


def test_valid_config(tmpdir):
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

    session = session.reload()
    analysis = [
        analysis for analysis in session.analyses if analysis.job.id == job.id
    ].pop()

    for an_file in analysis.files:
        analysis.download_file(an_file.name, tmpdir / an_file.name)

    # Test exported_data.csv
    exported_df = pd.read_csv(tmpdir / "exported_data.csv")
    for i in exported_df.index:
        assert fw_client.lookup(exported_df.loc[i, "export_path"])

    # Test reader_project_case_data.csv
    reader_df = pd.read_csv(tmpdir / "reader_project_case_data.csv")
    for i in reader_df.index:
        reader_project = fw_client.get(reader_df.id[i]).reload()
        assert reader_project.info["project_features"][
            "assignments"
        ] == ast.literal_eval(reader_df.assignments[i])
        assert reader_df.max_cases[i] >= reader_df.num_assignments[i]

    # Test master_project_case_data.csv
    cases_df = pd.read_csv(tmpdir / "master_project_case_data.csv")
    for i in cases_df.index:
        case_session = fw_client.get(cases_df.id[i]).reload()
        assert case_session.info["session_features"]["assignments"] == ast.literal_eval(
            cases_df.assignments[i]
        )
        assert cases_df.case_coverage[i] >= cases_df.assigned_count[i]

    assert cases_df.assigned_count.sum() == reader_df.num_assignments.sum()

    # Cleanup
    purge_reader_group(fw_client)


def test_add_new_readers(tmpdir):
    fw_client, assign_readers_gear = init_gear("assign-readers")

    job, _, _, _ = run_gear_w_config(
        fw_client,
        assign_readers_gear,
        DATA_ROOT / "assign_readers/config.json",
        clear_config=True,
    )

    assert job.state == "complete"

    _, assign_cases_gear = init_gear("assign-cases")

    job, _, _, _ = run_gear_w_config(
        fw_client,
        assign_cases_gear,
        DATA_ROOT / "assign_cases/config.json",
        clear_input=True,
    )

    assert job.state == "complete"

    # Assign more readers to projects
    job, _, _, _ = run_gear_w_config(
        fw_client,
        assign_readers_gear,
        DATA_ROOT / "assign_readers/config_more_readers.json",
        clear_config=True,
    )

    assert job.state == "complete"

    # Assign cases to those readers
    job, session, _, _ = run_gear_w_config(
        fw_client,
        assign_cases_gear,
        DATA_ROOT / "assign_cases/config.json",
        clear_input=True,
    )

    assert job.state == "complete"

    session = session.reload()
    analysis = [
        analysis for analysis in session.analyses if analysis.job.id == job.id
    ].pop()

    for an_file in analysis.files:
        analysis.download_file(an_file.name, tmpdir / an_file.name)

    # Test exported_data.csv
    exported_df = pd.read_csv(tmpdir / "exported_data.csv")
    for i in exported_df.index:
        assert fw_client.lookup(exported_df.loc[i, "export_path"])

    # Test reader_project_case_data.csv
    reader_df = pd.read_csv(tmpdir / "reader_project_case_data.csv")
    for i in reader_df.index:
        reader_project = fw_client.get(reader_df.id[i]).reload()

        assert reader_project.info["project_features"][
            "assignments"
        ] == ast.literal_eval(reader_df.assignments[i])
        assert reader_df.max_cases[i] >= reader_df.num_assignments[i]

    # Test master_project_case_data.csv
    cases_df = pd.read_csv(tmpdir / "master_project_case_data.csv")
    for i in cases_df.index:
        case_session = fw_client.get(cases_df.id[i])
        assert case_session.info["session_features"]["assignments"] == ast.literal_eval(
            cases_df.assignments[i]
        )
        assert cases_df.case_coverage[i] >= cases_df.assigned_count[i]

    assert cases_df.assigned_count.sum() == reader_df.num_assignments.sum()

    # Cleanup
    purge_reader_group(fw_client)
