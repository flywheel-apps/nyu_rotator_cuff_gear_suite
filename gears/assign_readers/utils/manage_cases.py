import logging
import os
import re
from pathlib import Path

import flywheel
import pandas as pd

from .container_operations import create_project

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
        return ohif_config_path
    else:
        master_project.upload_file(OHIF_CONFIG)
        return OHIF_CONFIG


def define_reader_csv(context):
    """
    Loads, updates or creates a csv file based on gear input and configuration

    If the reader_csv is specified in the gear configuration (and is valid) it is
    loaded as a pandas dataframe.

    If a specified reader is valid (email, firstname, lastname) it is appended
    to the pandas dataframe (if invalid, skipped). The email field is converted to all
    lowercase regardless of the configuration or inputs.

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
    regex = r"^[a-z0-9.]+[\._]?[a-z0-9.]+[@]\w+[.]\w{2,3}$"
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
                    and re.search(regex, context.config.get("reader_email").lower())
                    and context.config.get("reader_firstname")
                    and context.config.get("reader_lastname")
                ):
                    readers_df = readers_df.append(
                        {
                            "email": context.config.get("reader_email").lower(),
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
            readers_df.email = readers_df.email.str.lower()
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
        and (context.config.get("max_cases") < 5000)
        and context.config.get("reader_email")
        and re.search(regex, context.config.get("reader_email").lower())
        and context.config.get("reader_firstname")
        and context.config.get("reader_lastname")
    ):
        # create that dataframe
        readers_df = pd.DataFrame(
            data={
                "email": context.config.get("reader_email").lower(),
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


def find_readers_in_project_by_permission(project, reader_roles=None):
    """ finds a user with a specific set of permissions on a flywheel project

    Given a project, this function looks for a user with the roles/permissions
    specified in `reader_roles`, and returns those users.

    Args:
        project (flywheel.Project): a flywheel project to look for user roles on

    Returns:
        reader_ids (list): a list of
    """

    if not reader_roles:
        reader_roles = [
            role.id
            for role in fw_client.get_all_roles()
            if role.label in ["read-write", "read-only"]
        ]

    reader_ids = []
    for perm in project.permissions:
        log.debug(f"Found permission: {perm}")
        role_match = set(perm.role_ids).intersection(reader_roles)
        if role_match:
            log.debug(f"roles match {role_match}")
            reader_ids.append(perm.id)

    return reader_ids


def find_and_add_readers_by_perm(project, reader_roles=None):
    """ Finds a user with the correct flywheel roles/permissions on a given

    project, and adds that user ID to the projects metadata:
    project.info.project_features.reader.id

    Any user that has the roles specified in reader_roles is considered a reader

    Args:
        project (flywheel.Project): a flywheel project to find the reader on
        reader_roles (list): a list of valid reader roles.

    Returns:
        pf_reader (str): the flywheel ID of the reader.

    """
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


def find_readers_in_projects(projects, reader_roles=None):
    """ Finds the reader ids on a set of projects

    Kind of an "interem" function...the old way of doing things was to always
    check the project permissions and find the one user with "read/write"
    access, and that was assumed to be the reader for that project.  But this
    seemed kind of awkward and user-unfriendly.  The NEW way is that on
    assignment, the reader id is stored it the project metadata under:
    project.info.project_features.reader.id

    SO this function looks there for a reader ID.  If it's running on an OLD
    Blind reader deployment, it won't find any value there, so it will call
    the "find and add reader by perm" function, which does what I described
    above, BUT also generates that metadata field and populateds it with
    whichever reader ID it's found with the read/write permission.

    Args:
        projects (list): a list of flywheel projects to get ID's from
        reader_roles (list): a list of flywheel permissions that a reader can have

    Returns:
        reader_ids: (list) a list of reader id's (email addresses)

    """

    if isinstance(projects, flywheel.Project):
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


def find_reader_project_from_id(projects, reader_id, reader_roles=None):
    """ finds a reader's project given a reader ID.

    Given a flywheel user id, find the project that they are a reader on.

    This has legacy functionality.  Ideally reader projects have the reader id
    stored in the metadata key:

    `project.info.project_features.reader.id`

    But if that's not there, we have to use the legacy method of finding the project,
    based on role.  If we find it that way, populate the
    `project.info.project_features.reader.id` metadata key

    Args:
        projects (list): a list of flywheel projects to search through for the reader
        reader_id (string): the email of the reader to locate
        reader_roles (list): a list of flywheel roles that are intended for readers,
            usually read/write and read only

    Returns:
        reader_project (flywheel.Project): the project that the reader specified in
            `reader_id` is assigned to

    """

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

    reader_project = reader_project[0]

    return reader_project


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


    group_reader_ids = find_readers_in_projects(group_projects)


    for index in readers_df.index:
        reader_id = readers_df.email[index]
        # if the csv reader_id is not in the current reader projects, skip
        if reader_id not in group_reader_ids:
            continue

        reader_project = find_reader_project_from_id(group_projects, reader_id, proj_roles)
        reader_project = reader_project.reload()
        # If this reader has no project yet, skip (OR SHOULD THIS ERROR?)
        if reader_project is None:
            log.info(f"skipping reader {reader_id} with no current project")
            continue

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
    reader_roles = [
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

    # project_readers = [
    #     [
    #         perm.id
    #         for perm in proj.permissions
    #         if set(perm.role_ids).intersection(proj_roles)
    #     ][0]
    #     for proj in group.projects()
    # ]

    projects = fw_client.projects.iter_find(f'group={group.id},label=~Reader [0-9][0-9]?[0-9]?', limit=50)
    # Tested on imidex, iters uses pagination by default, this works when a simple finder would fail
    projects = list(projects)
    project_readers = find_readers_in_projects(projects, reader_roles)
                
    # If the readers email (from the dataframe) is not in the project readers list,
    # We will initiate it.
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
    Readers listed in the reader_csv will exist
        a) As a Flywheel user
        b) As a reader with 'ro' or 'rw' permissions in the reader group
        c) As a sole ro/rw user on a reader project
        d) Has a maximum number cases (max_cases) assigned to the reader project
            according to some additional constraints.
    
    Administrative permissions are needed to view the reader projects in the Readers
    group and in the Readers group Project Template. Permissions listed in this template
    will be granted to each project.

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
    group_projects = fw_client.projects.iter_find(f'group={group.id},label=~Reader [0-9][0-9]?[0-9]?', limit=50)
    group_projects = list(group_projects)


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
        ohif_config_path = confirm_or_create_ohif_config(master_project)
    
    for reader, _max_cases in readers_to_instantiate:
        # reader_number = len(group.projects()) + 1
        reader_number = get_reader_number(fw_client, group.id)
        project_label = "Reader " + str(reader_number)
        project_info = {
            "project_features": {"assignments": [], "max_cases": _max_cases, "reader": {"id": reader}}
        }

        new_project, created_container = create_project(
            fw_client, project_label, group, reader, project_info
        )
        if ohif_config_path and os.path.exists(ohif_config_path):
            new_project.upload_file(ohif_config_path)

        created_data.append(created_container)

    return created_data


def get_reader_number(fw_client, group_id):

    projects = fw_client.projects.iter_find(f'group={group_id},label=~Reader [0-9][0-9]?[0-9]?', limit=50)
    numbers = [int(p.label.split('Reader ')[-1]) for p in projects]
    if len(numbers) > 0:
        number = max(numbers)+1
    else:
        number = 1

    return number