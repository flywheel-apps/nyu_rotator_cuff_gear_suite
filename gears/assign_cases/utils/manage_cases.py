import logging

import numpy as np
import pandas as pd

from .container_operations import export_session, find_or_create_group

log = logging.getLogger(__name__)

OHIF_CONFIG = "/flywheel/v0/ohif_config.json"


class InvalidGroupError(Exception):
    """
    Exception raised for using an Invalid Flywheel group for this gear.

    Args:
        message (str): explanation of the error
    """

    def __init__(self, message):
        Exception.__init__(self)
        self.message = message


class InvalidInputError(Exception):
    """
    Exception raised for using an Invalid Input for this gear.

    Args:
        message (str): explanation of the error
    """

    def __init__(self, message):
        Exception.__init__(self)
        self.message = message


class NoReaderProjectsError(Exception):
    """
    Exception raised when no reader projects exist to populate.

    Args:
        message (str): explanation of the error
    """

    def __init__(self, message):
        Exception.__init__(self)
        self.message = message


def confirm_or_create_ohif_config(master_project):
    """
    Confirms or creates ohif_config.json in master project.

    The ohif_config.json file determines the functionality and presentation of the
    ohifViewer for this project.

    TODO: Some mechanism to verify that the master project has the most recent
    ohif_config.json.

    Args:
        master_project (flywheel.Project): The Master Project with the ohif_config.json.
    """
    ohif_config_path = "/tmp/ohif_config.json"
    if master_project.get_file("ohif_config.json"):
        master_project.download_file("ohif_config.json", ohif_config_path)
        # TODO: This is where we would compare them.
    else:
        master_project.upload_file(OHIF_CONFIG)


def set_session_features(session, case_coverage):
    """
    Gets or sets session features removes from source, restore later

    Each session has a set of features: case_coverage, assignments, and assignment_count
    each assignment consists of {project_id:<uid>, session_id:<uid>, status:<str>}
    Once diagnosed and measured each assignment will have the additional tags of
    {measurements:{}, read: {}} that are produced as part of the measurement process.
    if not found, create with defaults

    Args:
        session (flywheel.Session): The session to set/retrieve features from
    """

    session_features = (
        session.info["session_features"]
        if session.info.get("session_features")
        else {"case_coverage": case_coverage, "assignments": [], "assigned_count": 0}
    )

    return session_features


def find_readers_in_project_by_permission(project, reader_roles):
    reader_ids = []
    for perm in project.permissions:
        log.debug(f"Found permission: {perm}")
        role_match = set(perm.role_ids).intersection(reader_roles)
        if role_match:
            log.debug(f"roles match {role_match}")
            reader_ids.append(perm.id)

    return reader_ids


def find_and_add_readers_by_perm(project, reader_roles):
    info = project.info
    proj_readers = find_readers_in_project_by_permission(project, reader_roles)

    if len(proj_readers) > 1:
        log.warning("more than one possible reader found.  assuming first")

    if len(proj_readers) == 0:
        log.warning("No suitable reader found.")
        proj_readers = [None]

    pf_reader = proj_readers[0]

    info["project_features"]["reader"] = {"id": pf_reader}
    project.update_info(info)

    return pf_reader


def find_readers_in_projects(projects, reader_roles):
    """

    Args:
        projects:
        reader_roles:

    Returns:
        reader_ids: (list) a list of reader id's (email addresses)

    """

    if not isinstance(projects, list):
        projects = [projects]

    reader_ids = []
    for proj in projects:
        log.debug(f"Finding readers in project {proj.label}")
        info = proj.info

        if "project_features" not in info:
            proj = proj.reload()
            info = proj.info
            if "project_features" not in info:
                log.debug(f'uninitialized project {proj.label}. skipping.')
                continue

        pf_reader = info["project_features"].get("reader", {}).get("id")

        if pf_reader is None:
            pf_reader = find_and_add_readers_by_perm(proj, reader_roles)

        if pf_reader is not None:
            reader_ids.append(pf_reader)

    return reader_ids


def find_reader_project_from_id(projects, reader_id, reader_roles):
    reader_project = []

    for proj in projects:
        proj_readers = find_readers_in_projects(proj, reader_roles)
        if reader_id in proj_readers:
            reader_project.append(proj)

    if len(reader_project) > 1:
        log.warning(f"WARNING {len(reader_project)} projects found for reader {reader_id}:")
        log.warning([p.label for p in reader_project])
        log.warning(f"Returning first project")

    if len(reader_project) == 0:
        log.warning(f"No projects found for reader {reader_id}")
        reader_project = [None]

    return reader_project[0]


def set_project_session_attributes(session_features):
    """
    Return session attributes generated by assigning sessions to reader projects

    Args:
        session_features (dict): The session features (how many assignments) of the
            above session

    Returns:
        dict: The compiled attributes of a session for recording at the project level
    """
    session_attributes = {
        "id": session_features["id"],
        "label": session_features["label"],
        "case_coverage": session_features["case_coverage"],
        "unassigned": session_features["case_coverage"]
        - len(session_features["assignments"]),
        "assigned": len(session_features["assignments"]),
        "diagnosed": len(
            [
                assignment["status"]
                for assignment in session_features["assignments"]
                if assignment["status"] == "Diagnosed"
            ]
        ),
        "measured": len(
            [
                assignment["status"]
                for assignment in session_features["assignments"]
                if assignment["status"] == "Measured"
            ]
        ),
        "completed": len(
            [
                assignment["status"]
                for assignment in session_features["assignments"]
                if assignment["status"] == "Completed"
            ]
        ),
    }

    return session_attributes


def initialize_dataframes(fw_client, reader_group):
    """
    Initializes pandas DataFrames used to select sessions and reader projects

    Args:
        fw_client (flywheel.Client): Flywheel Client object instantiated on instance
        reader_group (flywheel.Group): The reader group

    Returns:
        tuple: a pair of pandas DataFrames representing the source sessions and
            destination projects
    """

    # This dataframe is to keep track of the sessions each reader project has and the
    # total number of those sessions. Initialized below.
    dest_projects_df = pd.DataFrame(
        columns=[
            "id",
            "label",
            "reader_id",
            "assignments",
            "max_cases",
            "num_assignments",
        ],
        dtype="object",
    )

    # Initialize destination projects dataframe
    # for reader_proj in fw_client.projects.find(f'group={reader_group.id}'):
    for reader_proj in fw_client.projects.iter_find(f"group={reader_group.id},label=~Reader [0-9][0-9]?[0-9]?"):
        reader_proj = reader_proj.reload()
        project_features = reader_proj.info["project_features"]
        # Valid roles for readers are "read-write" and "read-only"
        proj_roles = [
            role.id
            for role in fw_client.get_all_roles()
            if role.label in ["read-write", "read-only"]
        ]

        reader_id = find_readers_in_projects(reader_proj, proj_roles)
        reader_id = reader_id[0]

        # reader_id = [
        #     perm.id
        #     for perm in reader_proj.permissions
        #     if set(perm.role_ids).intersection(proj_roles)
        # ][0]
        #

        # Fill the dataframe with project data.
        dest_projects_df.loc[dest_projects_df.shape[0] + 1] = [
            reader_proj.id,
            reader_proj.label,
            reader_id,
            project_features["assignments"],
            project_features["max_cases"],
            len(reader_proj.sessions()),
        ]

    # This dataframe keeps track of each reader project and session each session was
    # exported to.
    source_sessions_df = pd.DataFrame(
        columns=["id", "label", "assignments", "assigned_count"]
    )

    return source_sessions_df, dest_projects_df


def select_readers_without_replacement(session_features, dest_projects_df):
    """
    Select reader projects to export assigned sessions to based on
        "selection without replacement"

    Args:
        session_features (dict): Current session's features used to assign and export
            to multiple reader projects
        dest_projects_df (pandas.DataFrame): Dataframe recording projects and their
            assigned sessions

    Returns:
        list: A list of ids from reader projects to populate with a given session
    """

    # Select case_coverage readers for each case
    # If avail_case_coverage == 0 we don't need to look.  It is all full up.
    avail_case_coverage = session_features["case_coverage"] - len(
        session_features["assignments"]
    )

    # add it to case_coverage distinct readers (projects)
    readers_proj_assigned = [
        assignments["project_id"] for assignments in session_features["assignments"]
    ]

    df_temp = dest_projects_df[
        (dest_projects_df.num_assignments == np.min(dest_projects_df.num_assignments))
        & (dest_projects_df.num_assignments < dest_projects_df.max_cases)
        & ~dest_projects_df.id.isin(readers_proj_assigned)
    ]

    min_avail_coverage = min(avail_case_coverage, df_temp.shape[0])
    # new readers to assign a session
    assign_reader_projs = list(
        np.random.choice(df_temp.id, min_avail_coverage, replace=False)
    )

    if df_temp.shape[0] < avail_case_coverage:
        # save the length of the previous df_temp
        df_temp_len = df_temp.shape[0]
        # Select all but the above readers_proj_assigned
        df_temp = dest_projects_df[
            ~dest_projects_df.id.isin(readers_proj_assigned + assign_reader_projs)
            & (dest_projects_df.num_assignments < dest_projects_df.max_cases)
        ]
        assign_reader_projs.extend(
            list(
                np.random.choice(
                    df_temp.id,
                    # need to choose the minimum of these
                    min(avail_case_coverage - df_temp_len, df_temp.shape[0]),
                    replace=False,
                )
            )
        )

    return assign_reader_projs


def distribute_cases_to_readers(fw_client, src_project, reader_group_id, case_coverage):
    """
    Distribute cases (sessions) from a source project to multiple reader projects.

    Each case (session) is exported to case_coverage selected readers until the
    max_cases of each reader is achieved or all sessions have been distributed.
    Readers are selected from a pool of available readers (readers that have less than
    reader.max_cases assigned) without replacement. Readers with the least number of
    sessions assigned are assigned new sessions first.

    This function can be run multiple times with new sessions in the source project and
    new readers created with the `assign-readers` gear.

    Args:
        fw_client (flywheel.Client): An instantiated Flywheel Client to host instance
        src_project (flywheel.Project): The source project for all sessions
        reader_group_id (str): The Flywheel container id for the group in question
        case_coverage (int): The default number of readers assigned to each session

    Returns:
        tuple: Pandas DataFrames recording source and destination for
            each session exported.
    """

    # Grab project-level features, if it does not exist, set defaults
    project_features = (
        src_project.info["project_features"]
        if src_project.get("project_features")
        else {"case_coverage": case_coverage, "case_states": []}
    )
    # Ensure a valid ohif_config.json file is present for the master project
    confirm_or_create_ohif_config(src_project)

    #src_sessions = src_project.sessions()
    src_sessions = fw_client.sessions.iter_find(f"project={src_project.id}")

    # Keep track of all the exported and created data
    # On Failure, remove contents of created_data from instance.
    exported_data = []
    created_data = []

    # Find or create reader group
    reader_group_label = fw_client.get_group(reader_group_id).label
    reader_group, _created_data = find_or_create_group(
        fw_client, reader_group_id, reader_group_label
    )
    
    log.info(f"Found reader group {reader_group.id}")
    
    created_data.extend(_created_data)

    # Initialize dataframes used to select sessions and readers without replacement
    source_sessions_df, dest_projects_df = initialize_dataframes(
        fw_client, reader_group
    )

    # If the dataframe for destination projects is empty, raise an error.
    if dest_projects_df.shape[0] == 0:
        raise NoReaderProjectsError(
            "Readers have not been added to this project. "
            "Please run `assign-readers` with valid configuration first."
        )

    nses = 0
    # for each session in the sessions found
    for src_session in src_sessions:
        nses += 1
        # Reload to capture all metadata
        src_session = src_session.reload()
        session_features = set_session_features(src_session, case_coverage)

        # select available readers to receive the session
        assign_reader_projs = select_readers_without_replacement(
            session_features, dest_projects_df
        )

        # This is where we record which readers receive the session
        # and export that session to each of those readers.
        # Iterate through the assign_reader_projs, export the session to each of them,
        # record results
        log.debug(f"found {len(assign_reader_projs)} reader projects")
        
        for project_id in assign_reader_projs:
            # grab the reader_id from the selected project
            project = fw_client.get(project_id)

            proj_roles = [
                role.id
                for role in fw_client.get_all_roles()
                if role.label in ["read-write", "read-only"]
            ]


                    
            # Below is the "original" code, which was modified to the code immediately below it.
            # List comprehension is faster, but I have expanded it for better logging, AND also
            # there was a problem with the new flywheel permissions that caused an error with 
            # the old code.  I am leaving it in for now in case any weird problems arise in the
            # future, so we can reference the "original" code quickly in case I missed something
            # 2021-05-18
                    

            # reader_id = [
            #     perm.id
            #     for perm in project.permissions
            #     if set(perm.role_ids).intersection(proj_roles)
            # ][0]

            reader_id = find_readers_in_projects(project, proj_roles)
            reader_id = reader_id[0]
            #
            # for perm in project.permissions:
            #     if set(perm.role_ids).intersection(proj_roles):
            #         reader_id = perm.id
            
            try:
                # export the session to the reader project
                dest_session, _exported_data, _created_data = export_session(
                    fw_client, src_session, fw_client.get(project_id)
                )

                exported_data.extend(_exported_data)
                created_data.extend(_created_data)

            except Exception as e:
                log.warning("Error while exporting a session, %s.", src_session.label)
                log.exception(e)
                log.warning("Examine the data and try again.")
                continue

            # grab the index from the dataframe and record source and dest
            # session ids
            indx = dest_projects_df[dest_projects_df.id == project_id].index[0]
            if not dest_projects_df.loc[indx, "assignments"]:
                dest_projects_df.loc[indx, "assignments"] = [
                    {"source_session": src_session.id, "dest_session": dest_session.id}
                ]
            else:
                dest_projects_df.loc[indx, "assignments"].append(
                    {"source_session": src_session.id, "dest_session": dest_session.id}
                )

            dest_projects_df.loc[indx, "num_assignments"] += 1
            session_features["assigned_count"] += 1
            session_features["assignments"].append(
                {
                    "project_id": project_id,
                    "reader_id": reader_id,
                    "session_id": dest_session.id,
                    "status": "Assigned",
                }
            )

        # This is where we give the "source" the information about where it went
        # later, we will want to use this to query "completed sessions" and get
        # ready for the next phase.
        session_info = {"session_features": session_features}

        # Restore the session_features to the source session
        src_session.update_info(session_info)

        # always record the state in the dataframe.
        session_features["id"] = src_session.id
        session_features["label"] = src_session.label
        source_sessions_df = source_sessions_df.append(
            session_features, ignore_index=True
        )

        project_session_attributes = set_project_session_attributes(session_features)

        # Check to see if the case is already present in the project_features
        case = [
            case
            for case in project_features["case_states"]
            if case["id"] == session_features["id"]
        ]
        if case:
            index = project_features["case_states"].index(case[0])
            project_features["case_states"].pop(index)

        # append new or updated case data to project_features
        project_features["case_states"].append(project_session_attributes)

    src_project.update_info({"project_features": project_features})

    # Todo: fix this damn divide by zero error
    if nses % dest_projects_df.shape[0] != 0:
        log.warning(
            "The number of sessions/cases (%i) in this batch is not divisible by the "
            "number of Readers (%i). This will result in an uneven distribution of "
            "exported sessions across the readers.",
            len(src_sessions),
            dest_projects_df.shape[0],
        )

    # Iterate through all of the readers and update their metadata:
    for indx in dest_projects_df.index:
        project_id = dest_projects_df.loc[indx, "id"]
        reader_proj = fw_client.get(project_id)
        project_info = {
            "project_features": {
                "assignments": dest_projects_df.loc[indx, "assignments"],
                "max_cases": dest_projects_df.loc[indx, "max_cases"],
            }
        }
        reader_proj.update_info(project_info)

    # Create a DataFrame from exported_data and then export
    exported_data_df = pd.DataFrame(data=exported_data)

    return source_sessions_df, dest_projects_df, exported_data_df
