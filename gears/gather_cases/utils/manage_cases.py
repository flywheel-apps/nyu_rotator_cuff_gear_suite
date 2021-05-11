import logging
import codecs
from ast import literal_eval as leval
from pathlib import Path
import json


import numpy as np
import pandas as pd
import requests

log = logging.getLogger(__name__)

CASE_ASSESSMENT_REC = {
    "id": None,
    "subject": None,
    "session": None,
    "reader_id": None,
    "completed": False,
    "completed_timestamp": None,
    "reader_project": None
}


class InvalidGroupError(Exception):
    """Exception raised for using an Invalid Flywheel group for this gear.

    Attributes:
        expression -- input expression in which the error occurred
        message -- explanation of the error
    """

    def __init__(self, message):
        Exception.__init__(self)
        self.message = message


class UninitializedGroupError(Exception):
    """Exception raised for using a Flywheel group without initialized projects.

    Attributes:
        expression -- input expression in which the error occurred
        message -- explanation of the error
    """

    def __init__(self, message):
        Exception.__init__(self)
        self.message = message


class MissingDICOMTagError(Exception):
    """Exception raised for an unavailable tag in the dicom file.

    Attributes:
        expression -- input expression in which the error occurred
        message -- explanation of the error
    """

    def __init__(self, message):
        Exception.__init__(self)
        self.message = message


class InvalidWCSStringERROR(Exception):
    """Exception raised for an invalid WCS String.

    Attributes:
        expression -- input expression in which the error occurred
        message -- explanation of the error
    """

    def __init__(self, message):
        Exception.__init__(self)
        self.message = message


class MissingFileError(Exception):
    """Exception raised when expected file not found in container.

    Attributes:
        expression -- input expression in which the error occurred
        message -- explanation of the error
    """

    def __init__(self, message):
        Exception.__init__(self)
        self.message = message


def populate_case_assessment_rec(fw_client, source_project):
    """
    Args:
        fw_client (flywheel.Client): An instantiated Flywheel Client to a host instance
        source_project (flywheel.Project): The source project for all sessions
    """
    ohif_config_path = "/tmp/ohif_config.json"
    if source_project.get_file("ohif_config.json"):
        source_project.download_file("ohif_config.json", ohif_config_path)
        ohif_config_file = codecs.open(ohif_config_path, "r", "utf-8")
        ohif_dict = json.load(ohif_config_file)
        for question in ohif_dict["questions"]:
            key = question["key"]
            CASE_ASSESSMENT_REC[key] = None
    else:
        ErrorMSG = (
            f"The project, {source_project.label}, is missing the expected file, "
            '"ohif_config.json". Ensure its existence and validity before running '
            "this gear again."
        )
        raise MissingFileError(ErrorMSG)


def io_proxy_wado(
    api_key, api_key_prefix, project_id, study=None, series=None, instance=None
):
    """
    Request wrapper for io-proxy api (https://{instance}/io-proxy/docs#/)

    Args:
        api_key (str): Full instance api-key
        api_key_prefix (str): Type of user (e.g. 'scitran-user')
        project_id (str): Project ID to inquire
        study (str, optional): DICOM StudyUID. Defaults to None.
        series (str, optional): DICOM SeriesUID. Defaults to None.
        instance (str, optional): DICOM InstanceUID. Defaults to None.

    Returns:
        dict/list: A dictionary for dicom tags or a list of dictionaries with dicom tags
    """
    base_url = Path(api_key.split(":")[0])
    base_url /= "io-proxy/wado"
    base_url /= "projects/" + project_id
    if study:
        base_url /= "studies/" + study
    if series:
        base_url /= "series/" + series
        base_url /= "instances"
    if instance:
        base_url /= instance
        base_url /= "tags"
    base_url = "https://" + str(base_url)

    headers = {
        "Authorization": api_key_prefix + " " + api_key,
        "accept": "application/json",
    }

    req = requests.get(base_url, headers=headers)

    return leval(req.text)


def change_world_coordinate_system(WCS):
    """
    Change from LPS to the given world coordinate system.

    Args:
        WCS (str): Three letter string L/R, A/P, S/I (e.g. "LPI")

    Raises:
        InvalidWCSStringERROR: Raised if the string is invalid/

    Returns:
        np.Array: Conversion Matrix from LPS to chosen WCS
    """

    LPS = "LPS"
    if (
        (len(WCS) is not 3)
        or (WCS[0] not in ["L", "R"])
        or (WCS[1] not in ["A", "P"])
        or (WCS[2] not in ["S", "I"])
    ):
        raise InvalidWCSStringERROR("Invalid WCS String. Check and try again.")

    vector = [1 if WCS[i] == LPS[i] else -1 for i in range(3)]
    vector.append(1)
    return np.diag(vector)


def create_ijk_to_WCS_matrix(WCS, ImageOrientation, ImagePosition, PixelSpacing):
    """
    create_ijk_to_WCS_matrix [summary]

    Args:
        WCS (str): Three letter string identifying coordinate system (e.g "RAS")
        ImageOrientation (list): A six float list from ImageOrientationPatient tag.
        ImagePosition (dict): A dictionary containing 1, 2, N members of
            ImagePositionPatient tags from all dicoms in series.
        PixelSpacing (list): List from PixelSpacing dicom tag.

    Returns:
        np.Array: A 4x4 numpy array for the voxel to world coordinate system.
    """
    DistanceBetweenSlices = np.linalg.norm(ImagePosition[1] - ImagePosition[2])
    N = list(ImagePosition)[-1]
    # Initialize WCS matrix
    ijk_WCS_matrix = np.zeros((4, 4))

    ijk_WCS_matrix[3, 3] = 1.0
    # Create third column from the cross-product of the first two
    ijk_WCS_matrix[:3, 0] = ImageOrientation[:3]
    ijk_WCS_matrix[:3, 1] = ImageOrientation[3:]
    ijk_WCS_matrix[:3, 2] = (ImagePosition[N] - ImagePosition[1]) / np.linalg.norm(
        ImagePosition[N] - ImagePosition[1]
    )
    # ijk_WCS_matrix[:3, 2] = np.cross(ijk_WCS_matrix[:3, 0], ijk_WCS_matrix[:3, 1])
    ijk_WCS_matrix[:3, 3] = ImagePosition[1]

    # Adjust Matrix for the world coordinate system used
    ijk_WCS_matrix = np.matmul(change_world_coordinate_system(WCS), ijk_WCS_matrix)

    spacing = np.diag([PixelSpacing[0], PixelSpacing[1], DistanceBetweenSlices, 1])

    ijk_WCS_matrix = np.matmul(ijk_WCS_matrix, spacing)

    return ijk_WCS_matrix


def io_proxy_acquire_coords(fw_client, project_id, Length):
    """
    Acquires coordinates and conversion matrix from dicom tags in io-proxy

    Args:
        fw_client (flywheel.Client): The active flywheel client
        project_id (str): The project id to inquire dicom tags for
        Length (dict): The ohif-derived json from a single measurement

    Returns:
        tuple: start/stop coordinates in voxel/WCS-space plus conversion matrix
    """
    # This project requests coordinates in "LPS"-world coordinates
    WCS = "LPS"
    host = fw_client._fw.api_client.configuration.host[:-8]
    api_key_prefix = fw_client._fw.api_client.configuration.api_key_prefix[
        "Authorization"
    ]
    api_key_hash = fw_client._fw.api_client.configuration.api_key["Authorization"]
    api_key = ":".join([host.split("//")[1], api_key_hash])

    voxel_start = np.ones((4, 1))
    voxel_end = np.ones((4, 1))
    wcs_start = np.zeros((4, 1))
    wcs_end = np.zeros((4, 1))

    study, series, instance = Length["imagePath"].split("$$$")[:3]

    instances = io_proxy_wado(api_key, api_key_prefix, project_id, study, series)
    N = len(instances)
    # The rest of the tags come from the measured slice
    slice_instance = [i for i in instances if i["00080018"]["Value"][0] == instance][0]
    # The following is NOT working... finding in instances.
    # io_proxy_wado(
    #     api_key, api_key_prefix, project_id, study, series, instance
    # )

    try:
        # (0020, 0032) Image Position (Patient) of three values
        ImagePosition = {}
        for j in [1, 2, N]:
            ImagePosition[j] = np.array(
                [
                    i["00200032"]["Value"]
                    for i in instances
                    if i["00200013"]["Value"] == [j]
                ][0]
            )

        # (0020, 0037) Image Orientation (Patient)
        ImageOrientation = np.array(slice_instance["00200037"]["Value"])
        # (0028, 0030) Pixel Spacing
        PixelSpacing = np.array(slice_instance["00280030"]["Value"])

        # (0020, 0013) Instance Number
        InstanceNumber = slice_instance["00200013"]["Value"][0]
        # (0008, 103E) Series Description
        SeriesDescription = slice_instance["0008103E"]["Value"][0]

    except Exception as e:
        log.exception(e)
        raise MissingDICOMTagError(
            "One of the following required tags is missing from the DICOM Series:\n"
            "\t(0008, 103E) Series Description,\n"
            "\t(0020, 0013) Instance Number,\n"
            "\t(0028, 0030) Pixel Spacing,\n"
            "\t(0020, 0037) Image Orientation (Patient),\n"
            "\t(0020, 0032) Image Position (Patient)\n"
            "Please replace the DICOM Series with a valid copy."
        )

    # Offsets to turn ohif, one-indexed coordinates to zero and then 1/2-voxel indexed
    # 1/2-voxel indexed makes the center of the origin voxel map to the origin of the
    # patient space.
    one_index_offset = np.array([1.0, 1.0, 1.0, 0]).reshape((4, 1))
    half_voxel_offest = np.array([0.5, 0.5, 0.5, 0]).reshape((4, 1))
    offset = one_index_offset + half_voxel_offest

    voxel_start[:3] = np.array(
        [
            Length["handles"]["start"]["x"],
            Length["handles"]["start"]["y"],
            InstanceNumber,
        ]
    ).reshape((3, 1))

    voxel_end[:3] = np.array(
        [Length["handles"]["end"]["x"], Length["handles"]["end"]["y"], InstanceNumber]
    ).reshape((3, 1))

    ijk_WCS_matrix = create_ijk_to_WCS_matrix(
        WCS, ImageOrientation, ImagePosition, PixelSpacing
    )

    wcs_start = np.matmul(ijk_WCS_matrix, voxel_start - offset)
    wcs_end = np.matmul(ijk_WCS_matrix, voxel_end - offset)

    return (
        voxel_start.reshape((4,))[:3],
        voxel_end.reshape((4,))[:3],
        wcs_start.reshape((4,))[:3],
        wcs_end.reshape((4,))[:3],
        ijk_WCS_matrix.tolist(),
        SeriesDescription,
    )


def assess_completed_status(ohif_viewer, user_data):
    """
    Assess completion status from the ohif_viewer data and the user data

    user_data is a selected subdictionary for the reader of the indicated project. If
    that reader's id is not found as a key in the `read` subdictionary, then the first
    user_id-key is used.

    Args:
        ohif_viewer (dict): All ohif-viewer data with measurements to check
        user_data (dict): All of the classification data for a particular reader

    Returns:
        boolean: Completion Status (True/False)
    """
    try:
        if not user_data:
            completed_status = False
            error_msg = None
        else:
            completed_status = True
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


def fill_session_attributes(fw_client, project_features, session):
    """
    Acquire data from a case to populate the output summary

    Args:
        fw_client (flywheel.Client): The active flywheel client
        project_features (dict): A dictionary representing features of the
            source project
        session (flywheel.Session): The flywheel session object being queried for
            completion status

    Returns:
        dict: Session attributes to populate an output dataframe
    """
    # Each session has a set of features: case_coverage and assignments
    # each assignment consists of {project_id:<uid>, session_id:<uid>, status:<>,
    #    *measurement:{}*, *read: {}*} **if performed, "gathered"
    # if not found, create with defaults

    # Grab session features from each session, if present.
    # If not yet present (session has been added before scattering), prep the
    # session features dictionary for later use.
    session_features = (
        session.info["session_features"]
        if session.info.get("session_features")
        else {
            "case_coverage": project_features["case_coverage"],
            "assignments": [],
            "assigned_count": 0,
        }
    )

    session_attributes = {
        "id": session.id,
        "label": session.label,
        "case_coverage": session_features["case_coverage"],
        "unassigned": session_features["case_coverage"]
        - len(session_features["assignments"]),
        "assigned": len(session_features["assignments"]),
        "classified": 0,
        "measured": 0,
        "completed": 0,
    }

    # This crashes if assigned sessions have been deleted for whatever reason
    for assignment in session_features["assignments"]:
        assigned_session = fw_client.get(assignment["session_id"])
        assigned_session = assigned_session.reload()
        assigned_session_info = assigned_session.info

        user_data = []
        ohif_viewer = assigned_session_info.get("ohifViewer")
        if ohif_viewer:
            if ohif_viewer.get("read"):
                assignment["read"] = ohif_viewer["read"]
                assignment["status"] = "Classified"
                session_attributes["classified"] += 1
                reader_id = assignment["reader_id"].replace(".", "_")
                if not ohif_viewer["read"].get(reader_id):
                    reader_id = list(ohif_viewer["read"].keys())[0]
                    log.warning(
                        "Assigned reader, %s, did not measure this case. "
                        "Most likely an administrator, %s, did.",
                        assignment["reader_id"],
                        reader_id.replace("_", "."),
                    )
                user_data = ohif_viewer["read"][reader_id]["notes"]

            if ohif_viewer.get("measurements"):
                assignment["measurements"] = ohif_viewer["measurements"]
                assignment["status"] = "Measured"
                session_attributes["measured"] += 1

            # Completion status depends on each tendon being
            # 1. Classifed as noTear, lowGradePartialTear, highGradePartialTear w/o
            #    measurements
            # 2. Classified as fullTear having 2 measurements for the indicated tendon
            completed_status, error_msg = assess_completed_status(
                ohif_viewer, user_data
            )

            if completed_status and not error_msg:
                assignment["status"] = "Completed"
                session_attributes["completed"] += 1
                ohif_viewer["read"][reader_id]["readOnly"] = True
                assigned_session.update_info({"ohifViewer": ohif_viewer})

    session.update_info({"session_features": session_features})
    # additional data to put into the project_features["case_states"]
    session_features["id"] = session.id
    session_features["label"] = session.label
    # If the case is already present in the project_features, replace
    case = [
        case
        for case in project_features["case_states"]
        if case["id"] == session_features["id"]
    ]
    if case:
        index = project_features["case_states"].index(case[0])
        project_features["case_states"].pop(index)

    project_features["case_states"].append(session_attributes)

    return session_attributes


def fill_reader_case_data(fw_client, project_features, session):
    """
    Acquire the status and data from each assigned case

    Args:
        fw_client (flywheel.Client): The active flywheel client
        project_features (dict): Valid features for the Master Project.
        session (flywheel.Session): Flywheel session with case assignments

    Returns:
        list: List of assignment status for each assignment in a session
    """
    # Each session has a set of features: case_coverage and assignments
    # each assignment consists of {project_id:<uid>, session_id:<uid>, status:<>,
    #    *measurement:{}*, *read: {}*} **if performed, "gathered"
    # if not found, create with defaults

    # Grab session features from each session, if present.
    # If not yet present (session has been added before scattering), prep the
    # session features dictionary for later use.
    session_features = (
        session.info["session_features"]
        if session.info.get("session_features")
        else {
            "case_coverage": project_features["case_coverage"],
            "assignments": [],
            "assigned_count": 0,
        }
    )
    case_assignments = []
    for assignment in session_features["assignments"]:
        assigned_session = fw_client.get(assignment["session_id"]).reload()
        assigned_session_info = assigned_session.info

        case_assignment_status = CASE_ASSESSMENT_REC.copy()
        case_assignment_status["id"] = session.id
        case_assignment_status["subject"] = session.subject.label
        case_assignment_status["session"] = session.label
        case_assignment_status["reader_id"] = assignment["reader_id"]
        case_assignment_status["reader_project"] = assigned_session.project
        ohif_viewer = assigned_session_info.get("ohifViewer")
        user_data = []
        if ohif_viewer:
            completed_status, error_msg = (False, None)

            if ohif_viewer.get("read"):
                reader_id = assignment["reader_id"].replace(".", "_")
                if not ohif_viewer["read"].get(reader_id):
                    reader_id = list(ohif_viewer["read"].keys())[0]
                user_data = ohif_viewer["read"][reader_id]["notes"]
                user_data["completed_timestamp"] = ohif_viewer["read"][reader_id][
                    "date"
                ]
                completed_status, error_msg = assess_completed_status(
                    ohif_viewer, user_data
                )
                case_assignment_status.update(user_data)

                # Eliminate carriage return and present error message
                additional_notes = case_assignment_status.get("notes", "")
                if isinstance(additional_notes, str):
                    additional_notes = additional_notes.replace("\n", " ")
                if error_msg:
                    additional_notes += error_msg
                case_assignment_status["notes"] = additional_notes

            case_assignment_status.update({"completed": completed_status})

            if ohif_viewer.get("measurements") and not error_msg:
                try:
                    # Eliminating this for now, Doesn't work without the required
                    # Dicom Tags
                    if False:  # ohif_viewer["measurements"].get("Length"):
                        for Length in ohif_viewer["measurements"]["Length"]:
                            prefix = Length["location"].lower().replace(" - ", "_")
                            case_assignment_status[prefix + "_Length"] = Length[
                                "length"
                            ]
                            (
                                voxel_start,
                                voxel_end,
                                wcs_start,
                                wcs_end,
                                ijk_WCS_matrix,
                                seriesDescription,
                            ) = io_proxy_acquire_coords(
                                fw_client, assignment["project_id"], Length
                            )
                            case_assignment_status[
                                prefix + "_seriesDescription"
                            ] = seriesDescription
                            case_assignment_status[
                                prefix + "_seriesInstanceUid"
                            ] = Length["seriesInstanceUid"]
                            case_assignment_status[
                                prefix + "_Voxel_Start"
                            ] = voxel_start
                            case_assignment_status[prefix + "_Voxel_End"] = voxel_end
                            case_assignment_status[prefix + "_WCS_Start"] = wcs_start
                            case_assignment_status[prefix + "_WCS_End"] = wcs_end
                            case_assignment_status[
                                prefix + "_ijk_to_WCS"
                            ] = ijk_WCS_matrix
                except Exception as e:
                    completed_status = False
                    error_msg = (
                        "ERROR: An error occurred in the case assessment. "
                        "Please examine and correct."
                    )
                    log.error(
                        "There was an error in the case assessment data. "
                        "Please examine and correct."
                    )
                    log.exception(e,)

                    case_assignment_status["completed"] = completed_status
                    case_assignment_status["additionalNotes"] += error_msg

        case_assignments.append(case_assignment_status)

    return case_assignments


def gather_case_data_from_readers(fw_client, source_project):
    """
    Gather case assessments from the distributed session assignments

    For each session in the master project
    1) Check for assignment status
    2) if assigned, check for completion status (classified, measured)
    3) record completion status in metadata and spreadsheet.
    4) Generates a summary status sheet.

    Args:
        fw_client (flywheel.Client): An instantiated Flywheel Client to a host instance
        source_project (flywheel.Project): The source project for all sessions

    Returns:
        tuple: a pair of pandas.DataFrame reporting on the state of each session in
            the project and the assessment status from each reader
    """

    source_project = source_project.reload()
    # Grab project-level features, if it does not exist, set defaults
    project_features = (
        source_project.info["project_features"]
        if source_project.info.get("project_features")
        else {"case_coverage": 3, "case_states": []}
    )

    src_sessions = source_project.sessions()

    # Create a DataFrame to represent the states of each session and assignments
    source_sessions_df = pd.DataFrame(
        columns=[
            "id",
            "label",
            "case_coverage",
            "unassigned",
            "assigned",
            "classified",
            "measured",
            "completed",
        ]
    )
    # Populate case assessment record from source project's ohif_config.json
    populate_case_assessment_rec(fw_client, source_project)

    # Create a DataFrame to record the state of each assessment by a reader
    case_assessment_df = pd.DataFrame(columns=CASE_ASSESSMENT_REC.keys())

    # for each session found
    for session in src_sessions:
        log.info("Gathering completion data for session %s", session.label)
        # Reload to capture all metadata
        session = session.reload()
        session_attributes = fill_session_attributes(
            fw_client, project_features, session
        )
        source_sessions_df = source_sessions_df.append(
            session_attributes, ignore_index=True
        )

        case_assignments = fill_reader_case_data(fw_client, project_features, session)
        if case_assignments:
            case_assessment_df = case_assessment_df.append(
                case_assignments, ignore_index=True
            )

    source_project.update_info({"project_features": project_features})

    return source_sessions_df, case_assessment_df


def generate_summary_report(fw_client, case_assessment_df):
    """ Generates a third report summary on reader progress
    
    Generates a progress report summary for each reader, indicating how many cases
    they've been assigned, how many they've completed, and how many they have max.
    
    Args:
        fw_client (flywheel.Client): An instantiated Flywheel Client to a host instance
        source_project (flywheel.Project): The source project for all sessions
        case_assessment_df (pandas.DataFrame): 

    Returns:

    """

    # Initialize a dataframe
    readers = case_assessment_df["reader_id"].unique()
    log.info(f"generating report for readers:\n{readers}")
    progress_report = pd.DataFrame(
        columns=[
            "reader_id",
            "completed_cases",
            "assigned_cases",
            "percent_assigned",
            "max_cases",
            "percent_max",
        ]
    )
    # We will pull the session ID's from the first report to make sure we're getting
    # reader info from the right project.

    for reader in readers:

        # First fill in all the new df stuff:
        log.info(f"looking for reader {reader}")
        # Get the readers summary
        current_reader_df = case_assessment_df[
            case_assessment_df["reader_id"] == reader
        ]

        completed_cases = current_reader_df["completed"].value_counts().get(True, 0)

        sample_id = current_reader_df["reader_project"].iloc[0]
        reader_project = fw_client.get_project(sample_id)
        project_features = reader_project.info.get("project_features", {})
        max_cases = project_features.get("max_cases", "NA")
        log.info(f"max_cases: {max_cases}")
        # max_cases = reader_project.info.get("project_features", {}).get(
        #     "max_cases", "NA"
        # )
        
        assigned_cases = len(
            reader_project.info.get("project_features", {}).get("assignments", [])
        )
        

        if max_cases != "NA" and max_cases != 0 and assigned_cases != 0:
            percent_assigned = round((completed_cases * 100.0) / assigned_cases, 2)
            percent_max = round((completed_cases * 100.0) / max_cases, 2)
        else:
            percent_max = "NA"
            percent_assigned = "NA"

        reader_df = {
            "reader_id": reader,
            "completed_cases": completed_cases,
            "assigned_cases": assigned_cases,
            "percent_assigned_completed": percent_assigned,
            "max_cases": max_cases,
            "percent_max_completed": percent_max,
        }
        
        progress_report = progress_report.append(reader_df, ignore_index=True, sort=False)

    return progress_report
