import json
import tempfile
from pathlib import Path

import flywheel
import pandas as pd
import pytest

from suite_common import init_gear, purge_reader_group, run_gear_w_config

DATA_ROOT = Path(__file__).parents[1] / "data"


def test_valid_config():
    fw_client, assign_readers_gear = init_gear("assign-readers")

    job, _, config, _ = run_gear_w_config(
        fw_client,
        assign_readers_gear,
        DATA_ROOT / "config2/config.json",
        clear_input=True,
    )

    assert job.state == "complete"

    # Test project count of Reader Group:
    group = fw_client.get("readers").reload()
    project = group.projects()[0].reload()
    permissions = project.permissions
    proj_roles = [
        role.id
        for role in fw_client.get_all_roles()
        if role.label in ["read-write", "read-only"]
    ]

    reader_role = [
        perm.role_ids[0] for perm in permissions if perm.id == config["reader_email"]
    ][0]

    expected_info = {
        "project_features": {"assignments": [], "max_cases": config["max_cases"]}
    }

    assert len(group.projects()) == 1
    assert config["reader_email"] in [perm.id for perm in permissions]
    assert reader_role in proj_roles
    assert project.info == expected_info

    # Cleanup
    purge_reader_group(fw_client)


def test_invalid_config():
    fw_client, assign_readers_gear = init_gear("assign-readers")
    job, _, _, _ = run_gear_w_config(
        fw_client,
        assign_readers_gear,
        DATA_ROOT / "invalid_config/config.json",
        clear_input=True,
    )

    assert job.state == "failed"


def test_valid_csv():
    fw_client, assign_readers_gear = init_gear("assign-readers")

    job, _, _, inputs = run_gear_w_config(
        fw_client,
        assign_readers_gear,
        DATA_ROOT / "config2/config.json",
        clear_config=True,
    )

    assert job.state == "complete"

    # Test results
    group = fw_client.get("readers").reload()
    projects = group.projects()
    expected_info = []
    permissions = []
    reader_roles = []
    proj_roles = [
        role.id
        for role in fw_client.get_all_roles()
        if role.label in ["read-write", "read-only"]
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        csv_filename = inputs["reader_csv"].ref()["name"]
        container = fw_client.get(inputs["reader_csv"].ref()["id"])
        container.download_file(csv_filename, Path(tmpdir) / csv_filename)
        csv_df = pd.read_csv(Path(tmpdir) / csv_filename)

    for i in range(len(projects)):
        projects[i] = projects[i].reload()
        permissions.append(projects[i].permissions)
        reader_roles.append(
            [perm.role_ids[0] for perm in permissions[i] if perm.id == csv_df.email[i]][
                0
            ]
        )
        expected_info.append(
            {"project_features": {"assignments": [], "max_cases": csv_df.max_cases[i]}}
        )

    assert len(projects) == 3
    for i in range(len(projects)):
        assert csv_df.email[i] in [perm.id for perm in permissions[i]]
        assert reader_roles[i] in proj_roles
        assert projects[i].info == expected_info[i]

    # Cleanup
    purge_reader_group(fw_client)


def test_invalid_csv():
    fw_client, assign_readers_gear = init_gear("assign-readers")

    job, _, _, _ = run_gear_w_config(
        fw_client,
        assign_readers_gear,
        DATA_ROOT / "invalid_csv/config.json",
        clear_config=True,
    )

    assert job.state == "failed"


def test_no_config_no_input():
    fw_client, assign_readers_gear = init_gear("assign-readers")

    job, _, _, _ = run_gear_w_config(
        fw_client,
        assign_readers_gear,
        DATA_ROOT / "config2/config.json",
        clear_config=True,
        clear_input=True,
    )

    assert job.state == "failed"


def test_valid_csv_update_w_config():
    fw_client, assign_readers_gear = init_gear("assign-readers")

    job, _, config, inputs = run_gear_w_config(
        fw_client,
        assign_readers_gear,
        DATA_ROOT / "config2/config.json",
        clear_config=True,
    )

    assert job.state == "complete"

    with tempfile.TemporaryDirectory() as tmpdir:
        csv_filename = inputs["reader_csv"].ref()["name"]
        container = fw_client.get(inputs["reader_csv"].ref()["id"])
        container.download_file(csv_filename, Path(tmpdir) / csv_filename)
        csv_df = pd.read_csv(Path(tmpdir) / csv_filename)

    # Update the config for resetting the max_cases
    config["reader_email"] = csv_df.email[0]
    config["reader_firstname"] = csv_df.first_name[0]
    config["reader_lastname"] = csv_df.last_name[0]
    config["max_cases"] = 6
    csv_df.max_cases[0] = 6

    job, _, _, _ = run_gear_w_config(
        fw_client,
        assign_readers_gear,
        DATA_ROOT / "config2/config.json",
        clear_config=True,
        clear_input=True,
        replace_config=config,
    )

    assert job.state == "complete"
    # Test results
    group = fw_client.get("readers").reload()
    projects = group.projects()
    expected_info = []
    permissions = []
    reader_roles = []
    proj_roles = [
        role.id
        for role in fw_client.get_all_roles()
        if role.label in ["read-write", "read-only"]
    ]

    for i in range(len(projects)):
        projects[i] = projects[i].reload()
        permissions.append(projects[i].permissions)
        reader_roles.append(
            [perm.role_ids[0] for perm in permissions[i] if perm.id == csv_df.email[i]][
                0
            ]
        )
        expected_info.append(
            {"project_features": {"assignments": [], "max_cases": csv_df.max_cases[i]}}
        )

    assert len(projects) == 3
    for i in range(len(projects)):
        assert csv_df.email[i] in [perm.id for perm in permissions[i]]
        assert reader_roles[i] in proj_roles
        assert projects[i].info == expected_info[i]

    # Cleanup
    purge_reader_group(fw_client)
