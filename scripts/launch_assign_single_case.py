#!/usr/env python3
"""
This script lauches multiple assign-single-case gears in a sequence defined by
the input csv file. Command-line inputs are:
--fw_api_key: Valid API-key for a Flywheel instance running the gears.
--config_csv: CSV file of configuration choices for 'assign-single-case' gear.

Returns:
    int: Returns 0 on success, non-zero on failure.
"""
import argparse
import copy
import logging
import sys
import time

import flywheel
import pandas as pd

log = logging.getLogger(__name__)

VALID_REASONS = ["Assign to Resolve Tie", "Apply Consensus Assessment from Source"]

CONFIG_TEMPLATE = {
    "config": {"reader_email": "sample@sample.com", "assignment_reason": "Sample"},
    "inputs": {},
    "destination": {"type": "analysis", "id": "SAMPLE"},
}


def run_gear_w_config(
    fw_client,
    gear,
    gear_config,
    clear_config=False,
    clear_input=False,
    replace_config=None,
):
    """
    Run a gear with given configuration.

    Args:
        fw_client (flywheel.Client): Active and valid connection to a Flywheel instance.
        gear (flywheel.GearDoc): A gear registered in the above client.
        gear_config (dict): Dictionary representing the gear configuration.
        clear_config (bool, optional): Clear config portion or not. Defaults to False.
        clear_input (bool, optional): Clear input portion or not. Defaults to False.
        replace_config (dict, optional): A replacement configuration. Defaults to None.

    Returns:
        tuple: job, destination, config, inputs
    """
    config = gear_config["config"]
    inputs = gear_config["inputs"]
    if list(inputs.keys()):
        project = fw_client.get(inputs[list(inputs.keys())[0]]["id"])
        destination = project.sessions()[0]
    elif gear_config.get("destination"):
        destination = fw_client.get(gear_config["destination"]["id"])

    if clear_config:
        for key, value in config.items():
            if type(value) == str:
                config[key] = ""

    if clear_input:
        inputs = {}
    else:
        for key, value in inputs.items():
            input_file = [
                fl
                for fl in fw_client.get(value["id"]).files
                if fl.name == value["name"]
            ][0]
            inputs[key] = input_file

    if replace_config:
        config = replace_config

    analysis_id = gear.run(
        config=config,
        analysis_label="Script_Launched",
        inputs=inputs,
        destination=destination,
    )

    job = fw_client.get_analysis(analysis_id).job

    while job.state not in ["complete", "failed", "cancelled"]:
        time.sleep(30)
        job = job.reload()

    return job, destination, config, inputs


def run_seq_gears(fw_api_key, config_csv):
    """
    Run a set of assign-single-case gears in sequential order described in `config_csv`.
    See documentation for assign-single-case gear for constraints.

    Args:
        fw_api_key (str): A string representing the valid API-Key to a
            Flywheel instance.
        config_csv (str): Path to a csv file with fields
            "session_id": The session id (not label) of a source session in Flywheel.
            "reader_email": The email of a reader with rw access to a project.
            "assignment_reason": The reason for the altered assignment. See above.

    Returns:
        int: Returns 0 value on success. Non-zero on failure.
    """
    try:
        fw_client = flywheel.Client(fw_api_key)
    except Exception:
        log.error("Invalid Flywheel API Key.")
        return -1

    try:
        # Ensure validity of CSV file
        config_df = pd.read_csv(config_csv)
        assert "session_id" in config_df.columns
        assert "reader_email" in config_df.columns
        assert "assignment_reason" in config_df.columns
    except Exception:
        log.error("Invalid CSV File.")
        return -1

    try:
        # Ensure gear exists on instance
        gear_name = "assign-single-case"
        assign_single_case_gear = fw_client.gears.find_one(f'gear.name="{gear_name}"')
    except Exception:
        log.error("Cannot find registered gear.")
        return -1

    # Add fields to denote gear job completion status and a link to log.
    config_df["job_status"] = ""
    config_df["job_link"] = ""

    for i in config_df.index:
        session_id = config_df.loc[i, "session_id"]
        reader_email = config_df.loc[i, "reader_email"]
        assignment_reason = config_df.loc[i, "assignment_reason"]

        session = fw_client.get(session_id)
        destination_id = session_id
        gear_config = copy.deepcopy(CONFIG_TEMPLATE)

        gear_config["config"]["reader_email"] = reader_email
        gear_config["config"]["assignment_reason"] = assignment_reason
        gear_config["destination"]["id"] = destination_id

        if assignment_reason in VALID_REASONS:
            job, _, _, _ = run_gear_w_config(
                fw_client, assign_single_case_gear, gear_config, clear_input=True,
            )
            config_df.loc[i, "job_status"] = job.state
            host = fw_client.api_client.configuration.host[:-8]
            config_df.loc[i, "job_link"] = host + "/#/jobslog/job/" + str(job.id)
        else:
            log.error('Invalid "Assignment Reason".')
            config_df.loc[i, "job_status"] = "FAILED"

    config_df.to_csv("results.csv")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fw_api_key",
        type=str,
        required=True,
        help="API key for the Flywheel instance",
    )

    parser.add_argument(
        "--config_csv",
        type=str,
        required=True,
        help="CSV file of configuration choices for 'assign-single-case' gear.",
    )

    args = parser.parse_args()

    sys.exit(run_seq_gears(fw_api_key=args.fw_api_key, config_csv=args.config_csv))
