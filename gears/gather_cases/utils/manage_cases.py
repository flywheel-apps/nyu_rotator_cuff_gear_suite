import logging

import pandas as pd

log = logging.getLogger(__name__)


class InvalidGroupError(Exception):
    """Exception raised for using an Invalid Flywheel group for this gear.

    Attributes:
        expression -- input expression in which the error occurred
        message -- explanation of the error
    """

    def __init__(self, message):
        Exception.__init__(self)
        self.message = message


def gather_case_data_from_readers(fw_client, source_project):
    """
    Gather case assessments from the distributed session assignments

    For each session in the master project
    1) Check for assignment status
    2) if assigned, check for completion status (diagnosed, measured)
    3) record completion status in metadata and spreadsheet.

    Args:
        fw_client (flywheel.Client): An instantiated Flywheel Client to the host instance
        source_project (flywheel.Project): The source project for all sessions

    Returns:
        pandas.DataFrame: Pandas DataFrame reporting on the state of each session in
            the project
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
            "diagnosed",
            "measured",
            "completed",
        ]
    )

    # for each session found
    for session in src_sessions:
        log.info("Gathering completion data for session %s", session.label)
        # Reload to capture all metadata
        session = session.reload()

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
            "diagnosed": 0,
            "measured": 0,
            "completed": 0,
        }

        for assignment in session_features["assignments"]:
            assigned_session = fw_client.get(assignment["session_id"])
            assigned_session = assigned_session.reload()
            assigned_session_info = assigned_session.info

            # used to asses No, PartialLow, PartialHigh, Full tear for each
            tear_test = []
            if assigned_session_info.get("ohifViewer"):
                if assigned_session_info["ohifViewer"].get("read"):
                    assignment["read"] = assigned_session_info["ohifViewer"]["read"]
                    assignment["status"] = "Diagnosed"
                    session_attributes["diagnosed"] += 1
                    user = list(assigned_session_info["ohifViewer"]["read"].keys())[0]
                    user_data = assigned_session_info["ohifViewer"]["read"][user][
                        "notes"
                    ]
                    tear_test = [
                        user_data["infraspinatusTear"],
                        user_data["subscapularisTear"],
                        user_data["supraspinatusTear"],
                    ]

                if assigned_session_info["ohifViewer"].get("measurements"):
                    assignment["measurements"] = assigned_session_info["ohifViewer"][
                        "measurements"
                    ]
                    assignment["status"] = "Measured"
                    session_attributes["measured"] += 1
                # mark as complete if tear-status is recorded and if it is a full-tear
                # and measured
                if (
                    assigned_session_info["ohifViewer"].get("read")
                    and "full" not in tear_test
                ) or (
                    assigned_session_info["ohifViewer"].get("read")
                    and "full" in tear_test
                    and assigned_session_info["ohifViewer"].get("measurements")
                ):
                    assignment["status"] = "Completed"
                    session_attributes["completed"] += 1

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

        source_sessions_df = source_sessions_df.append(
            session_attributes, ignore_index=True
        )

    source_project.update_info({"project_features": project_features})

    return source_sessions_df
