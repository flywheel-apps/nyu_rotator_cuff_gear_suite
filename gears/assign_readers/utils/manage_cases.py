import logging
import os
import re
import shutil
from pathlib import Path

import flywheel
import numpy as np
import pandas as pd
import requests

from .container_operations import create_project, export_session, find_or_create_group

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


def define_reader_csv(context):
    """
    Loads, updates or creates a csv file based on gear input and configuration

    If the reader_csv is specified in the gear configuration (and is valid) it is
    loaded as a pandas dataframe.

    If a specified reader is valid (email, firstname, lastname) it is appended
    to the pandas dataframe (if invalid, skipped).

    Without the reader_csv (or invalid) the specified reader is validated and saved to
    a csv file in the context.work directory.  If specified reader is invalid,
    None is returned.

    Args:
        context (gear_toolkit.GearContext): The gear context

    Raises:
        InvalidInputError: If neither the configuration (email, firstname, lastname) nor
            the input (csv with fields email, firstname, lastname, max_cases) is valid
            then this Error is thrown and the gear fails with message.

    Returns:
        str: The path of the resultant csv file or None (fail)
    """
    readers_df = []
    # regex for checking validity of readers email
    regex = r"^[a-zA-Z0-9.]+[\._]?[a-zA-Z0-9.]+[@]\w+[.]\w{2,3}$"
    # Ensure valid inputs and act consistently
    reader_csv_path = context.get_input_path("reader_csv")
    if reader_csv_path:
        readers_df = pd.read_csv(reader_csv_path)
        # Validate that dataframe has required columns before proceeding
        req_columns = ["email", "first_name", "last_name", "max_cases"]
        if not all([(c in readers_df.columns) for c in req_columns]):
            log.warning(
                'The csv-file "%s" did not have the required columns("%s").'
                + "Proceeding without reader CSV.",
                Path(reader_csv_path).name,
                '", "'.join(req_columns),
            )
            reader_csv_path = None
        else:
            # if we have a reader email, check for existence in csv (update),
            # otherwise we need to create (if all conditions are satisfied)
            if context.config.get("reader_email"):
                reader_email = context.config.get("reader_email")
                # if we find the reader's email in the dataframe,
                if len(readers_df[readers_df.email == reader_email]) > 0:
                    indx = readers_df[readers_df.email == reader_email].index[0]
                    # Update the max_cases in the dataframe
                    readers_df.loc[indx, "max_cases"] = context.config["max_cases"]
                    # This will trigger an update in the metadata on assign-cases
                # else if we have reader's email, firstname, and lastname
                elif (
                    context.config.get("max_cases")
                    and (context.config.get("max_cases") > 0)
                    and (context.config.get("max_cases") < 600)
                    and context.config.get("reader_email")
                    and re.search(regex, context.config.get("reader_email"))
                    and context.config.get("reader_firstname")
                    and context.config.get("reader_lastname")
                ):
                    readers_df = readers_df.append(
                        {
                            "email": context.config.get("reader_email"),
                            "first_name": context.config.get("reader_firstname"),
                            "last_name": context.config.get("reader_lastname"),
                            "max_cases": context.config.get("max_cases"),
                        },
                        ignore_index=True,
                    )
                # else the indicated reader is invalid
                else:
                    log.warning(
                        "The specified reader is not configured correctly. "
                        'Proceeding without specified reader ("%s").',
                        '", "'.join(
                            [
                                str(context.config.get("reader_email")),
                                str(context.config.get("reader_firstname")),
                                str(context.config.get("reader_lastname")),
                            ]
                        ),
                    )

            # Check the whole DataFrame for compliance to the regex on emails
            if not all([re.search(regex, X) is not None for X in readers_df.email]):
                raise InvalidInputError(
                    "Cannot proceed without a valid CSV file or valid specified reader!"
                )

            # Create a csv and return its path
            work_csv = context.work_dir / Path(reader_csv_path).name
            readers_df.to_csv(work_csv, index=False)
            return work_csv

    # if the csv is not provided and we have a valid reader entry
    if not reader_csv_path and (
        context.config.get("max_cases")
        and (context.config.get("max_cases") > 0)
        and (context.config.get("max_cases") < 600)
        and context.config.get("reader_email")
        and re.search(regex, context.config.get("reader_email"))
        and context.config.get("reader_firstname")
        and context.config.get("reader_lastname")
    ):
        # create that dataframe
        readers_df = pd.DataFrame(
            data={
                "email": context.config.get("reader_email"),
                "first_name": context.config.get("reader_firstname"),
                "last_name": context.config.get("reader_lastname"),
                "max_cases": context.config.get("max_cases"),
            },
            index=[0],
        )
        # save it to the work directory
        work_csv = context.work_dir / "temp.csv"
        readers_df.to_csv(work_csv, index=False)
        return work_csv
    else:
        raise InvalidInputError(
            "Cannot proceed without a valid CSV file or valid specified reader!"
        )


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

    # If the session has features, remove them for now.  Restore them after export
    if session.info.get("session_features"):
        session.delete_info("session_features")

    return session_features


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


def update_reader_projects_metadata(fw_client, group_projects, readers_df):
    """
    Update reader group projects' metadata according to the csv/dataframe contents

    Contraints are as follows:
    1) if project.max_cases < df.max_cases, project.max_cases = df.max_cases
    2) if project.max_cases > df.max_cases, project.max_cases = min
        (df.max_cases, project.num_assigned_cases)

    Function loops through the DataFrame and applies updates only to those that
    exist in the DataFrame and as a reader project.

    Args:
        group_projects (list): List of Flywheel Projects
        readers_df (pandas.DataFrame): Pandas Dataframe containing columns:
            "email", "first_name", "last_name", and "max_cases"
    """

    # Valid roles for readers are "read-write" and "read-only"
    proj_roles = [
        role.id
        for role in fw_client.get_all_roles()
        if role.label in ["read-write", "read-only"]
    ]

    group_reader_ids = [
        [
            perm.id
            for perm in proj.permissions
            if set(perm.role_ids).intersection(proj_roles)
        ][0]
        for proj in group_projects
    ]

    for index in readers_df.index:
        reader_id = readers_df.email[index]
        # if the csv reader_id is not in the current reader projects, skip
        if reader_id not in group_reader_ids:
            continue

        reader_project = [
            proj
            for proj in group_projects
            if reader_id in [perm.id for perm in proj.permissions]
        ][0].reload()

        csv_max_cases = int(readers_df.max_cases[index])
        project_info = reader_project.info
        project_max_cases = (
            project_info["project_features"]["max_cases"]
            if (
                project_info.get("project_features")
                and project_info["project_features"].get("max_cases")
            )
            else 0
        )

        if csv_max_cases > project_max_cases:
            project_info["project_features"]["max_cases"] = csv_max_cases
        # else check the number of assigned sessions... never set max_cases
        # to less than this (* see todo below *)
        elif csv_max_cases < project_max_cases:
            project_info["project_features"]["max_cases"] = max(
                len(reader_project.sessions()), csv_max_cases
            )
        # update if csv.max_cases and info.max_cases are different
        if csv_max_cases is not project_max_cases:
            reader_project.update_info(project_info)


def instantiate_new_readers(fw_client, group, readers_df):
    """
    Instantiate and grant permissions to new readers found in readers_df

    Args:
        fw_client (flywheel.Client): The Flywheel client
        group (flywheel.Group): The flywheel group that reader projects are created in
        group_readers (list): ids for each reader with ro/rw permission to the group
        readers_df (pandas.DataFrame): DataFrame for reader updates and creation

    Returns:
        list: A list of reader ids (emails) from the csv requiring a new project
    """
    readers_to_instantiate = []

    # All Flywheel users on instance.
    users_ids = [user.id for user in fw_client.users()]

    # check if the new readers need to be added as new FW users
    new_users = readers_df[~readers_df.email.isin(users_ids)]

    for indx in new_users.index:
        new_user = new_users.loc[indx, :]
        fw_user = flywheel.User(
            id=new_user.email,
            email=new_user.email,
            firstname=new_user.first_name,
            lastname=new_user.last_name,
        )
        fw_client.add_user(fw_user)

    # A Reader Project will have only one rw/ro user
    proj_roles = [
        role.id
        for role in fw_client.get_all_roles()
        if role.label in ["read-write", "read-only"]
    ]

    project_readers = [
        [
            perm.id
            for perm in proj.permissions
            if set(perm.role_ids).intersection(proj_roles)
        ][0]
        for proj in group.projects()
    ]
    for indx in readers_df[~readers_df.email.isin(project_readers)].index:
        readers_to_instantiate.append(
            (readers_df.email[indx], int(readers_df.max_cases[indx]))
        )
    return readers_to_instantiate


def create_or_update_reader_projects(
    fw_client, group, master_project, readers_csv=None
):
    """
    Updates the number and attributes of reader projects to reflect constraints

    These constraints are:
    1) A reader project must exist for every reader(user) with 'ro' or 'rw' permissions
        in the reader group.
    2) A reader project has a maximum number of cases (max_cases) that the reader will
        review
    3) Readers listed in the reader_csv will exist
        a) As a Flywheel user
        b) As a reader with 'ro' or 'rw' permissions in the reader group
        c) As a sole ro/rw user on a reader project
        d) Has a maximum number cases (max_cases) assigned to the reader project
            according to some additional constraints.

    Args:
        fw_client (flywheel.Client): Flywheel Client object instantiated on instance
        group (flywheel.Group): The group ("readers") to update the reader projects for
        master_project (flywheel.Project): The project we are copying sessions, files,
            and metadata from.
        readers_csv (str, optional): A filepath to the CSV input containing
            reader emails, names, and max_cases for assignment or updating.
                Defaults to None.

    Returns:
        list: A list of created reader projects described as a dictionary with tags
            "container", "id", and "new" as described in define_container above.
    """

    # Generate list of all projects in this group
    group_projects = fw_client.projects.find(f'group="{group.id}"')

    # Keep track of the created containers, in case of "rollback"
    created_data = []

    # Keep track of the reader projects we need to create and the max_cases for each
    readers_to_instantiate = []

    # Update or create reader-projects from a provided csv file
    # readers_csv is a path to a csv file with columns:
    # "email", "first_name", "last_name", and "max_cases"
    if readers_csv and os.path.exists(readers_csv):

        # Load dataframe from file
        readers_df = pd.read_csv(readers_csv)

        # Validate that dataframe has required columns before proceeding
        req_columns = ["email", "first_name", "last_name", "max_cases"]
        if all([(c in readers_df.columns) for c in req_columns]):
            # update max_cases for existing projects in the reader group according to
            # csv data
            update_reader_projects_metadata(fw_client, group_projects, readers_df)

            # identify new readers, instantiate, give group permissions
            readers_to_instantiate = instantiate_new_readers(
                fw_client, group, readers_df
            )

        else:
            log.warning(
                'The csv-file "%s" did not have the required columns("%s"). '
                "Proceeding without reader CSV.",
                readers_csv,
                '", "'.join(req_columns),
            )

    ohif_config_path = None
    if readers_to_instantiate:
        ohif_config_path = "/tmp/ohif_config.json"
        if master_project.get_file("ohif_config.json"):
            master_project.download_file("ohif_config.json", ohif_config_path)
        else:
            shutil.copyfile(OHIF_CONFIG, ohif_config_path)
            master_project.upload_file(ohif_config_path)

    for reader, _max_cases in readers_to_instantiate:
        reader_number = len(group.projects()) + 1
        project_label = "Reader " + str(reader_number)
        project_info = {
            "project_features": {"assignments": [], "max_cases": _max_cases}
        }

        new_project, created_container = create_project(
            fw_client, project_label, group, reader, project_info
        )
        if ohif_config_path and os.path.exists(ohif_config_path):
            new_project.upload_file(ohif_config_path)

        created_data.append(created_container)

    return created_data


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
    for reader_proj in fw_client.projects.find(f'group="{reader_group.id}"'):
        reader_proj = reader_proj.reload()
        project_features = reader_proj.info["project_features"]
        # Valid roles for readers are "read-write" and "read-only"
        proj_roles = [
            role.id
            for role in fw_client.get_all_roles()
            if role.label in ["read-write", "read-only"]
        ]
        reader_id = [
            perm.id
            for perm in reader_proj.permissions
            if set(perm.role_ids).intersection(proj_roles)
        ][0]
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
            assigned sesions

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


def distribute_cases_to_readers(
    fw_client, src_project, reader_group_id, case_coverage, max_cases, reader_csv=None,
):
    """
    Distribute cases (sessions) from a source project to multiple reader projects.

    Reader Projects are prepared in the following manner:
    1) If readers (users) have permissions listed in the reader_group, existence of a
       reader project is checked and created if absent. Each of these readers is
       assigned max_cases as set from the ui.
    2) If a reader_csv is provided (with the required fields), each reader (user)
       listed is checked:
        a) for existence as a Flywheel user, created if absent
        b) for permissions in the reader_group, added if absent
        c) for the presence of a reader_project, created if absent. csv.max_cases set
           for each user.

    Once reader projects are instantiated (as above), each case (session) is exported
    to case_coverage readers until the max_cases of each reader is achieved or all
    sessions have been distributed. Readers are selected from a pool of available
    readers (readers that have less than reader.max_cases assigned) without replacement.
    Readers with the least number of sessions assigned are assigned new sessions first.

    This function can be run multiple times with new sessions in the source project and
    new users designated in the reader_group permissions or the reader_csv.

    Args:
        fw_client (flywheel.Client): An instantiated Flywheel Client to the
            host instance
        src_project_label (str): The label of the source project for all sessions
        reader_group_id (str): The Flywheel container id for the group in question
        case_coverage (int): The default number of readers assigned to each session
        max_cases (int): The default maximum number of sessions for each new reader
            project, unless specified in a reader_csv.
        reader_csv (str): Path to csv file with "email", "first_name", "last_name", and
            "max_cases" columns.

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

    src_sessions = src_project.sessions()

    # Keep track of all the exported and created data
    # On Failure, remove contents of created_data from instance.
    exported_data = []
    created_data = []

    # Find or create reader group
    reader_group, _created_data = find_or_create_group(
        fw_client, reader_group_id, "Readers"
    )
    created_data.extend(_created_data)

    # Create or update reader projects
    _created_data = create_or_update_reader_projects(
        fw_client, reader_group, src_project, readers_csv=reader_csv
    )
    created_data.extend(_created_data)

    # Initialize dataframes used to select sessions and readers without replacement
    source_sessions_df, dest_projects_df = initialize_dataframes(
        fw_client, reader_group
    )

    # for each session in the sessions found
    for src_session in src_sessions:
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
        for project_id in assign_reader_projs:
            # grab the reader_id from the selected project
            project = fw_client.get(project_id)

            proj_roles = [
                role.id
                for role in fw_client.get_all_roles()
                if role.label in ["read-write", "read-only"]
            ]

            reader_id = [
                perm.id
                for perm in project.permissions
                if set(perm.role_ids).intersection(proj_roles)
            ][0]
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

        # if there something to update to the src_session.info
        if len(assign_reader_projs) > 0:
            src_session.update_info(session_info)
        # always record the state in the dataframe.
        session_features["id"] = src_session.id
        session_features["label"] = src_session.label
        source_sessions_df = source_sessions_df.append(
            session_features, ignore_index=True
        )

        project_session_attributes = set_project_session_attributes(session_features)

        project_features["case_states"].append(project_session_attributes)

    src_project.update_info({"project_features": project_features})

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
