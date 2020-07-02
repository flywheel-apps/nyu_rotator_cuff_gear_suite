import json
import time

import flywheel


def init_gear(gear_name):
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
    with open(config_path, "r") as fl:
        gear_config = json.load(fl)

    config = gear_config["config"]
    inputs = gear_config["inputs"]

    project = fw_client.get(inputs[list(inputs.keys())[0]]["id"])
    session = project.sessions()[0]

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

    job_id = gear.run(
        config=config, analysis_label="E2E Test", inputs=inputs, destination=session
    )
    time.sleep(2)
    job = get_job_from_id(fw_client, job_id)

    while job.state not in ["complete", "failed"]:
        time.sleep(1)
        job = job.reload()

    return job, session, config, inputs


def get_job_from_id(fw_client, job_id):
    job = fw_client.jobs.find_first("_id=" + job_id)
    if job:
        return job
    else:
        job_id = str(hex(int(job_id, 16) + 1))[2:]

    job = fw_client.jobs.find_first("_id=" + job_id)

    if job:
        return job
    else:
        raise Exception("Job Not Found!")


def purge_reader_group(fw_client):
    # it is going to be assumed that the group has been created and populated with
    # appropriate users and permissions... on the other hand... this could be another
    # gear entirely.  A list of users... or an option to this one.***
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
