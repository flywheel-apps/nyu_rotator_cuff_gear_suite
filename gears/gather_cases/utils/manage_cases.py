import logging
from ast import literal_eval as leval
from pathlib import Path

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
    "infraspinatusTear": None,
    "infraspinatusDifficulty": None,
    "infraspinatusRetraction": None,
    "infraspinatus_anteroposterior_seriesDescription": None,
    "infraspinatus_anteroposterior_seriesInstanceUid": None,
    "infraspinatus_anteroposterior_Length": None,
    "infraspinatus_anteroposterior_Voxel_Start": None,
    "infraspinatus_anteroposterior_Voxel_End": None,
    "infraspinatus_anteroposterior_RAS_Start": None,
    "infraspinatus_anteroposterior_RAS_End": None,
    "infraspinatus_anteroposterior_ijk_to_RAS": None,
    "infraspinatus_mediolateral_seriesDescription": None,
    "infraspinatus_mediolateral_seriesInstanceUid": None,
    "infraspinatus_mediolateral_Length": None,
    "infraspinatus_mediolateral_Voxel_Start": None,
    "infraspinatus_mediolateral_Voxel_End": None,
    "infraspinatus_mediolateral_RAS_Start": None,
    "infraspinatus_mediolateral_RAS_End": None,
    "infraspinatus_mediolateral_ijk_to_RAS": None,
    "subscapularisTear": None,
    "subscapularisDifficulty": None,
    "subscapularisRetraction": None,
    "subscapularis_mediolateral_seriesDescription": None,
    "subscapularis_mediolateral_seriesInstanceUid": None,
    "subscapularis_mediolateral_Length": None,
    "subscapularis_mediolateral_Voxel_Start": None,
    "subscapularis_mediolateral_Voxel_End": None,
    "subscapularis_mediolateral_RAS_Start": None,
    "subscapularis_mediolateral_RAS_End": None,
    "subscapularis_mediolateral_ijk_to_RAS": None,
    "subscapularis_craniocaudal_seriesDescription": None,
    "subscapularis_craniocaudal_seriesInstanceUid": None,
    "subscapularis_craniocaudal_Length": None,
    "subscapularis_craniocaudal_Voxel_Start": None,
    "subscapularis_craniocaudal_Voxel_End": None,
    "subscapularis_craniocaudal_RAS_Start": None,
    "subscapularis_craniocaudal_RAS_End": None,
    "subscapularis_craniocaudal_ijk_to_RAS": None,
    "supraspinatusTear": None,
    "supraspinatusDifficulty": None,
    "supraspinatusRetraction": None,
    "supraspinatus_anteroposterior_seriesDescription": None,
    "supraspinatus_anteroposterior_seriesInstanceUid": None,
    "supraspinatus_anteroposterior_Length": None,
    "supraspinatus_anteroposterior_Voxel_Start": None,
    "supraspinatus_anteroposterior_Voxel_End": None,
    "supraspinatus_anteroposterior_RAS_Start": None,
    "supraspinatus_anteroposterior_RAS_End": None,
    "supraspinatus_anteroposterior_ijk_to_RAS": None,
    "supraspinatus_mediolateral_seriesDescription": None,
    "supraspinatus_mediolateral_seriesInstanceUid": None,
    "supraspinatus_mediolateral_Length": None,
    "supraspinatus_mediolateral_Voxel_Start": None,
    "supraspinatus_mediolateral_Voxel_End": None,
    "supraspinatus_mediolateral_RAS_Start": None,
    "supraspinatus_mediolateral_RAS_End": None,
    "supraspinatus_mediolateral_ijk_to_RAS": None,
    "additionalNotes": None,
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


def io_proxy_acquire_coords(fw_client, project_id, Length):
    """
    Acquires coordinates and conversion matrix from dicom tags in io-proxy

    Args:
        fw_client (flywheel.Client): The active flywheel client
        project_id (str): The project id to inquire dicom tags for
        Length (dict): The ohif-derived json from a single measurement

    Returns:
        tuple: start/stop coordinates in voxel/RAS-space plus conversion matrix
    """
    host = fw_client._fw.api_client.configuration.host[:-8]
    api_key_prefix = fw_client._fw.api_client.configuration.api_key_prefix[
        "Authorization"
    ]
    api_key_hash = fw_client._fw.api_client.configuration.api_key["Authorization"]
    api_key = ":".join([host.split("//")[1], api_key_hash])

    voxel_start = np.ones((4, 1))
    voxel_end = np.ones((4, 1))
    ras_start = np.zeros((4, 1))
    ras_end = np.zeros((4, 1))
    ijk_RAS_matrix = np.zeros((4, 4))

    ijk_RAS_matrix[3, 3] = 1.0

    study, series, instance = Length["imagePath"].split("$$$")[:3]

    instances = io_proxy_wado(api_key, api_key_prefix, project_id, study, series)

    # find first instance for the first ImagePosition as image origin
    first_inst = [i for i in instances if i["00200013"]["Value"] == [1]][0]
    # (0020, 0032) Image Position (Patient)
    ImagePosition = first_inst["00200032"]["Value"]

    # The rest of the tags come from the measured slice
    slice_instance = io_proxy_wado(
        api_key, api_key_prefix, project_id, study, series, instance
    )
    # (0020, 0037) Image Orientation (Patient)
    ImageOrientation = slice_instance["00200037"]["Value"]
    # (0028, 0030) Pixel Spacing
    PixelSpacing = slice_instance["00280030"]["Value"]
    # (0018, 0088) Spacing Between Slices
    SpacingBetweenSlices = slice_instance["00180088"]["Value"][0]
    # (0020, 0013) Instance Number
    InstanceNumber = slice_instance["00200013"]["Value"][0]
    # (0008, 103E) Series Description
    SeriesDescription = slice_instance["0008103E"]["Value"][0]

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

    # Create third column from the cross-product of the first two
    ijk_RAS_matrix[:3, 0] = ImageOrientation[:3]
    ijk_RAS_matrix[:3, 1] = ImageOrientation[3:]
    ijk_RAS_matrix[:3, 2] = np.cross(ijk_RAS_matrix[:3, 0], ijk_RAS_matrix[:3, 1])
    ijk_RAS_matrix[:3, 3] = ImagePosition

    # Adjust for the direction of the voxel coordinate system
    ijk_RAS_matrix = np.matmul(np.diag([-1, -1, 1, 1]), ijk_RAS_matrix)

    spacing = np.diag([PixelSpacing[0], PixelSpacing[1], SpacingBetweenSlices, 1])

    ijk_RAS_matrix = np.matmul(ijk_RAS_matrix, spacing)

    ras_start = np.matmul(ijk_RAS_matrix, voxel_start)
    ras_end = np.matmul(ijk_RAS_matrix, voxel_end)

    return (
        voxel_start.reshape((4,))[:3],
        voxel_end.reshape((4,))[:3],
        ras_start.reshape((4,))[:3],
        ras_end.reshape((4,))[:3],
        ijk_RAS_matrix.tolist(),
        SeriesDescription,
    )


def assess_completed_status(ohif_viewer, user_data):
    """
    Assess completion status from the ohif_viewer data and the user data

    Args:
        ohif_viewer (dict): All ohif-viewer data with measurements to check
        user_data (dict): All of the classification data for a particular reader

    Returns:
        boolean: Completion Status (True/False)
    """
    if not user_data:
        completed_status = False
    else:
        completed_status = True
        for tendon in ["infraspinatus", "subscapularis", "supraspinatus"]:
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
    return completed_status


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
                    log.warn(
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
            completed_status = assess_completed_status(ohif_viewer, user_data)

            if completed_status:
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
    fill_reader_case_data [summary]

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
        ohif_viewer = assigned_session_info.get("ohifViewer")
        user_data = []
        if ohif_viewer:
            if ohif_viewer.get("read"):
                reader_id = assignment["reader_id"].replace(".", "_")
                if not ohif_viewer["read"].get(reader_id):
                    reader_id = list(ohif_viewer["read"].keys())[0]
                user_data = ohif_viewer["read"][reader_id]["notes"]
                user_data["completed_timestamp"] = ohif_viewer["read"][reader_id][
                    "date"
                ]
                case_assignment_status.update(user_data)

            completed_status = assess_completed_status(ohif_viewer, user_data)
            case_assignment_status.update({"completed": completed_status})

            if ohif_viewer.get("measurements"):
                if ohif_viewer["measurements"].get("Length"):
                    for Length in ohif_viewer["measurements"]["Length"]:
                        prefix = Length["location"].lower().replace(" - ", "_")
                        case_assignment_status[prefix + "_Length"] = Length["length"]
                        (
                            voxel_start,
                            voxel_end,
                            ras_start,
                            ras_end,
                            ijk_RAS_matrix,
                            seriesDescription,
                        ) = io_proxy_acquire_coords(
                            fw_client, assignment["project_id"], Length
                        )
                        case_assignment_status[
                            prefix + "_seriesDescription"
                        ] = seriesDescription
                        case_assignment_status[prefix + "_seriesInstanceUid"] = Length[
                            "seriesInstanceUid"
                        ]
                        case_assignment_status[prefix + "_Voxel_Start"] = voxel_start
                        case_assignment_status[prefix + "_Voxel_End"] = voxel_end
                        case_assignment_status[prefix + "_RAS_Start"] = ras_start
                        case_assignment_status[prefix + "_RAS_End"] = ras_end
                        case_assignment_status[prefix + "_ijk_to_RAS"] = ijk_RAS_matrix

        case_assignments.append(case_assignment_status)

    return case_assignments


def gather_case_data_from_readers(fw_client, source_project):
    """
    Gather case assessments from the distributed session assignments

    For each session in the master project
    1) Check for assignment status
    2) if assigned, check for completion status (classified, measured)
    3) record completion status in metadata and spreadsheet.

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
