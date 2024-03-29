import copy
import json
import time

import flywheel


class JobNotFoundError(Exception):
    """
    Exception raised when submitted Job is not found.

    Args:
        message (str): explanation of the error
    """

    def __init__(self, message):
        Exception.__init__(self)
        self.message = message


def init_gear(gear_name):
    """
    Initializes a gear from name. Returns the flywheel client and gear object.

    Args:
        gear_name (str): Name of gear in instance reference by API-Key.

    Returns:
        tuple: fw_client (flywheel.Client), gear (flywheel.GearDoc)
    """
    fw_client = flywheel.Client()
    gear = fw_client.gears.find_one(f'gear.name="{gear_name}"')

    return fw_client, gear


def run_gear_w_config(
    fw_client,
    gear,
    config_path,
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
    with open(config_path, "r") as fl:
        gear_config = json.load(fl)

    config = gear_config["config"]
    inputs = gear_config["inputs"]
    if inputs.get("destination"):
        destination = fw_client.get(inputs["destination"]["id"])
    elif list(inputs.keys()):
        project = fw_client.get(inputs[list(inputs.keys())[0]]["id"])
        destination = project.sessions()[0]

    if clear_config:
        for key, value in config.items():
            if type(value) == str:
                config[key] = ""

    if clear_input:
        inputs = {}
    else:
        for key, value in copy.deepcopy(inputs).items():
            if value.get("name"):
                input_file = [
                    fl
                    for fl in fw_client.get(value["id"]).files
                    if fl.name == value["name"]
                ][0]
                inputs[key] = input_file
            else:
                inputs.pop(key)

    if replace_config:
        config = replace_config

    analysis_id = gear.run(
        config=config, analysis_label="E2E Test", inputs=inputs, destination=destination
    )

    job = get_job_from_id(fw_client, analysis_id)

    while job.state not in ["complete", "failed", "cancelled"]:
        time.sleep(5)
        job = job.reload()

    return job, destination, config, inputs


def get_job_from_id(fw_client, analysis_id):
    """
    Get a flywheel job object from the job ID.

    The job_id may need to be incremented.

    Args:
        fw_client (flywheel.Client): Valid Flywheel Client to active instance
        analysis_id (str): Analysis id from gear.run

    Raises:
        Exception: If the job is not found

    Returns:
        flywheel.job: Active Flywheel Job object
    """
    analysis = fw_client.get_analysis(analysis_id)

    if not analysis:
        raise JobNotFoundError("Job Not Found!")

    return analysis.job


def purge_reader_group(fw_client):
    """
    Purges all projects from the "readers" group.

    It is assumed that the group has been created and populated with
    appropriate users and permissions... on the other hand... this could be another
    gear entirely.  A list of users... or an option to this one.
    
    Args:
        fw_client (flywheel.Client): Active Flywheel Client.
    """

    group = fw_client.groups.find_first('_id="readers"')

    if group:
        # I want to generate a list of all projects in this group
        group_projects = fw_client.projects.find(f'group="{group.id}"')

        for proj in group_projects:
            proj = proj.reload()
            fw_client._fw.delete_project(proj.id)

        for perm in group.permissions:
            if perm.access != "admin":
                group.delete_permission(perm.id)
        src_projects = fw_client.projects.find('group="msk"')
        src_projects.extend(fw_client.projects.find('group="msk2"'))
        for src_project in src_projects:
            src_sessions = src_project.sessions()
            src_project.delete_info("project_features")
            for session in src_sessions:
                session.delete_info("session_features")
