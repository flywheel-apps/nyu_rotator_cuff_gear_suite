import copy
import logging

import pandas as pd

from .container_operations import export_session, find_or_create_group

log = logging.getLogger(__name__)


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


class InvalidLaunchContainerError(Exception):
    """
    Exception raised when gear is launched from an invalid container.

    Args:
        message (str): explanation of the error
    """

    def __init__(self, message):
        Exception.__init__(self)
        self.message = message


class InvalidReaderError(Exception):
    """
    Exception raised for referencing an invalid reader of a project.

    Args:
        message (str): explanation of the error
    """

    def __init__(self, message):
        Exception.__init__(self)
        self.message = message


class ExistingReaderCaseError(Exception):
    """
    Exception raised for attempted re-export of a case.

    Args:
        message (str): explanation of the error
    """

    def __init__(self, message):
        Exception.__init__(self)
        self.message = message


class ExceededConstraintsError(Exception):
    """
    Exception raised when constraints are exceeded.

    Args:
        message (str): explanation of the error
    """

    def __init__(self, message):
        Exception.__init__(self)
        self.message = message


class MissingDataError(Exception):
    """
    Exception raised when required data is missing.

    Args:
        message (str): explanation of the error
    """

    def __init__(self, message):
        Exception.__init__(self)
        self.message = message


def set_session_features(session, case_coverage):
    """
    Gets or sets session features and updates later

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


def check_valid_reader(fw_client, reader_id, group_id):
    """
    Checks for the existing reader project for indicated reader_id.

    Args:
        fw_client (flywheel.Client): Flywheel instance client for api calls.
        reader_id (str): The email of the reader to validate
        group_id (str): The id of the reader group

    Raises:
        InvalidReaderError: If a project is not found assigned to reader, raised to exit

    Returns:
        boolean: Returns `True` if reader has assigned project
    """

    group_projects = fw_client.projects.find(f'group="{group_id}"')

    proj_roles = [
        role.id
        for role in fw_client.get_all_roles()
        if role.label in ["read-write", "read-only"]
    ]

    valid_reader_ids = [
        [
            perm.id
            for perm in proj.permissions
            if set(perm.role_ids).intersection(proj_roles)
        ][0]
        for proj in group_projects
    ]

    if reader_id in valid_reader_ids:
        return True

    raise InvalidReaderError(
        f"The Reader, {reader_id}, has not been instantiated. "
        "Please run `assign-readers` to create a reader project for this user."
    )


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


def assess_completed_status(ohif_viewer, reader_id=None):
    """
    Assess completion status from the ohif_viewer data and the user data

    user_data is a selected subdictionary for the reader of the indicated project. If
    that reader's id is not found as a key in the `read` subdictionary, then the first
    user_id-key is used.

    Args:
        ohif_viewer (dict): All ohif-viewer data with measurements to check
        reader_id (str, optional): If specified, indicated reader is preferred, else
            the first reader encountered is used. Defaults to None.

    Returns:
        boolean: Completion Status (True/False)
    """
    try:
        completed_status = True
        if not reader_id or reader_id not in list(ohif_viewer["read"].keys()):
            reader_id = list(ohif_viewer["read"].keys())[0]

        user_data = ohif_viewer["read"][reader_id]["notes"]
        for tendon in ["infraspinatus", "supraspinatus", "subscapularis"]:
            if user_data[tendon + "Tear"] in [
                "none",
                "lowPartial",
                "highPartial",
            ]:
                completed_status &= True
            elif user_data[tendon + "Tear"] == "full":
                if not (
                    user_data.get(tendon + "Retraction")
                    and user_data[tendon + "Retraction"]
                    in ["minimal", "humeral", "glenoid"]
                ):
                    completed_status &= False

                if ohif_viewer.get("measurements") and ohif_viewer["measurements"].get(
                    "Length"
                ):
                    Lengths = ohif_viewer["measurements"].get("Length")
                    tendon_measures = [
                        tendon_meas
                        for tendon_meas in Lengths
                        if tendon in tendon_meas["location"].lower()
                    ]
                    if len(tendon_measures) != 2:
                        completed_status &= False
                else:
                    completed_status &= False
            elif user_data[tendon + "Tear"] == "fullContiguous":
                if user_data["supraspinatusTear"] == "full":
                    completed_status &= True
                else:
                    completed_status &= False
            else:
                completed_status &= False
            error_msg = None
    except Exception as e:
        completed_status = False
        log.error(
            "There was an error in the case assessment data. "
            "Please examine and correct."
        )
        log.exception(e,)
        error_msg = (
            "ERROR: An error occurred in the case assessment. "
            "Please examine and correct."
        )

    return completed_status, error_msg


def assign_single_case(fw_client, src_session, reader_group_id, reader_id, reason):
    """
    assign_single_case [summary]

    Args:
        fw_client (flywheel.Client): Valid Flywheel Client connecting to active instance
        src_session (flywheel.Session): The source session for a case to assign
        reader_group_id (str): The reader group id "readers"
        reader_id (str): The email of the reader to assign/update a single case
        reason (str): The type of assignment/update

    Raises:
        InvalidReaderError: Raised when a reader is not found
        ExceededConstraintsError: Raised when case_coverage or max_cases constraints
            would be exceeded by an attempted new assignment of a case
        ExistingReaderCaseError: Raised when attempting to export a case over an
            existing case in a reader project.
        MissingDataError: Raised when expected data (dest session or source ohifViewer)
            is not found.

    Returns:
        tuple: Pandas data frames recording source and destination of each case as well
            as every container and file exported in the process:
            source_sessions_df,
            dest_projects_df,
            exported_data_df
    """
    src_project = fw_client.get(src_session.parents["project"]).reload()

    # Grab project-level features, if it does not exist, set defaults
    project_features = (
        src_project.info["project_features"]
        if src_project.info.get("project_features")
        else {"case_coverage": 3, "case_states": []}
    )

    # Keep track of all the exported and created data
    # On Failure, remove contents of created_data from instance.
    exported_data = []
    created_data = []

    # Find or create reader group
    reader_group, _created_data = find_or_create_group(
        fw_client, reader_group_id, "Readers"
    )
    created_data.extend(_created_data)

    # Initialize dataframes used to select sessions and readers without replacement
    source_sessions_df, dest_projects_df = initialize_dataframes(
        fw_client, reader_group
    )

    # retrieve reader project
    try:
        indx = dest_projects_df[dest_projects_df.reader_id == reader_id].index[0]
        project_id = dest_projects_df.id[indx]
        reader_proj = fw_client.get(project_id).reload()
    except Exception as e:
        log.error(
            "The reader (%s) was not found in this project. Ensure you are entering a "
            "valid user.",
            reader_id,
        )
        raise InvalidReaderError("Invalid User")

    session_features = set_session_features(src_session, 3)

    if reason in ["Assign to Resolve Tie", "Individual Assignment"]:
        # Check reader availability
        if dest_projects_df.num_assignments[indx] == dest_projects_df.max_cases[indx]:
            log.error(
                "Cannot assign more than %s cases to %s. "
                "Consider increasing max_cases for this reader "
                "or choosing another reader.",
                dest_projects_df.max_cases[indx],
                reader_id,
            )
            raise ExceededConstraintsError("Max assignments reached.")

        # check for the existence of the selected session in the reader project
        if src_session.label in [sess.label for sess in reader_proj.sessions()]:
            log.error(
                "Selected session (%s) has already been assigned to reader (%s).",
                src_session.label,
                reader_id,
            )
            raise ExistingReaderCaseError("Existing Session in Destination Project.")

        # Increment case_coverage, if necessary
        if session_features["assigned_count"] == session_features["case_coverage"]:
            if reason == "Individual Assignment":
                log.error(
                    "Assigning this case (%s) to reader (%s) exceeds "
                    "case_coverage (%s) for this case.\n"
                    'Change case_coverage or use "Assign to Resolve Tie".',
                    src_session.label,
                    reader_id,
                    session_features["case_coverage"],
                )
                raise ExceededConstraintsError("Assignment exceeds case_coverage.")
            elif session_features["case_coverage"] == 4:
                log.error(
                    "Assigning this case (%s) to reader (%s) exceeds "
                    "maximum allowed case_coverage (%s).\n"
                    "Further increase is not allowed.",
                    src_session.label,
                    reader_id,
                    session_features["case_coverage"],
                )
                raise ExceededConstraintsError("Assignment exceeds case_coverage.")
            else:
                session_features["case_coverage"] += 1
        elif (
            session_features["assigned_count"] < session_features["case_coverage"]
            and session_features["case_coverage"] == 3
            and reason == "Assign to Resolve Tie"
        ):
            log.error(
                "Number of case assignments (%s) is not at the limit (%s) required "
                "to break a tie.",
                session_features["assigned_count"],
                session_features["case_coverage"],
            )
            raise ExceededConstraintsError(
                "Assignment requires case_coverage assignments."
            )

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

    elif reason == "Apply Consensus Assessment from Source":
        # check for the existence of the selected session in the reader project
        if src_session.label not in [sess.label for sess in reader_proj.sessions()]:
            log.error(
                "Selected session (%s) must be assigned to reader (%s) to update.",
                src_session.label,
                reader_id,
            )
            raise MissingDataError("Missing Session in Destination Project.")

        session_info = src_session.info
        if assess_completed_status(session_info.get("ohifViewer"))[0]:
            ohif_viewer = session_info.get("ohifViewer")
            admin_reader = list(ohif_viewer["read"].keys())[0]
            # Find reader_assignment
            assignment = [
                assignment
                for assignment in session_features["assignments"]
                if assignment["reader_id"] == reader_id
            ][0]

            # Set assignment status to "Assigned", remove any acquired assessment data
            assignment["status"] = "Assigned"
            if assignment.get("read"):
                assignment.pop("read")
            if assignment.get("measurements"):
                assignment.pop("measurements")

            _reader_id = reader_id.replace(".", "_")

            dest_session = fw_client.get(assignment["session_id"]).reload()
            if assess_completed_status(dest_session.info.get("ohifViewer"), _reader_id)[
                0
            ]:
                dest_ohifViewer = dest_session.info["ohifViewer"]

                if _reader_id not in list(dest_ohifViewer["read"].keys()):
                    _reader_id = list(dest_ohifViewer["read"].keys())[0]
            else:
                log.warning(
                    "The reader (%s) has not completely assessed "
                    "the assigned session (%s).\n"
                    "The assessment must be completed and valid to be updated.",
                    reader_id,
                    src_session.label,
                )
                raise MissingDataError(
                    "Case Assessment in Destination Case is either missing or invalid."
                )

                dest_ohifViewer = {"read": {_reader_id: {}}}

            reader_ohif_notes = dest_ohifViewer["read"][_reader_id]["notes"]

            # Build the temp dictionary to fill with {tendon}Tear = "full"/"Contiguous"
            temp_dict = {}
            for k, v in ohif_viewer["read"][admin_reader]["notes"].items():
                if ("full" in v) and ("full" not in reader_ohif_notes[k]):
                    temp_dict[k] = v
        else:
            log.error(
                "The original case (%s) needs to have a completed and valid consensus "
                "assessment "
                "for the selected reader (%s) to provide a measurement for.",
                src_session.label,
                reader_id,
            )
            raise MissingDataError("Missing assessment in source session.")

        dest_ohifViewer["read"][_reader_id]["readOnly"] = False
        dest_ohifViewer["read"][_reader_id]["notes"].update(temp_dict)

        dest_session.update_info({"ohifViewer": dest_ohifViewer})

    # Record updates to the source session
    session_info = {"session_features": session_features}
    src_session.update_info(session_info)

    # Iterate through sessions to record system state of Assigned Sessions
    for tmp_session in src_project.sessions():
        tmp_session = tmp_session.reload()
        session_features = set_session_features(tmp_session, 3)
        # always record the state in the dataframe.
        session_features["id"] = tmp_session.id
        session_features["label"] = tmp_session.label
        source_sessions_df = source_sessions_df.append(
            session_features, ignore_index=True
        )

        project_session_attributes = set_project_session_attributes(session_features)

        # Check to see if the case is already present in the project_features
        case = [
            case
            for case in project_features["case_states"]
            if case and (case["id"] == session_features["id"])
        ]
        if case:
            index = project_features["case_states"].index(case[0])
            project_features["case_states"].pop(index)

        # append new or updated case data to project_features
        project_features["case_states"].append(project_session_attributes)

        # This is where we give the "source" the information about where it went
        # later, we will want to use this to query "completed sessions" and get
        # ready for the next phase.
        session_info = {"session_features": session_features}

        # Restore the session_features to the source session
        tmp_session.update_info(session_info)

    src_project.update_info({"project_features": project_features})

    # update reader project from updates to the dataframe
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
