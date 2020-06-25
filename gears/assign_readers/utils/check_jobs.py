import logging

log = logging.getLogger(__name__)


class DuplicateJobError(Exception):
    """
    Exception raised for attempting to run a duplicate of an atomic gear.

    Args:
        message (str): explanation of the error
    """

    def __init__(self, message):
        Exception.__init__(self)
        self.message = message


class InsufficientPermissionsError(Exception):
    """
    Exception raised for attempting to run a gear with insufficient permissions.

    Args:
        message (str): explanation of the error
    """

    def __init__(self, message):
        Exception.__init__(self)
        self.message = message


def verify_user_permissions(fw_client, context, permitted_roles=["admin"]):
    """
    Verify that the current user has permission in the project to run the gear.

    Args:
        fw_client (flywheel.Client): Flywheel Client object
        context (gear_toolkit.GearToolkitContext): Context object to retrieve project
        permitted_roles (list, optional): Roles permitted to run this gear.
            Represented as a list of role names. Defaults to ["admin"].

    Raises:
        InsufficientPermissionsError: Raised if insufficient permissions to run gear.
    """
    current_user = fw_client.get_current_user()

    permitted = [
        role.id for role in fw_client.get_all_roles() if role.label in permitted_roles
    ]

    destination_id = context.destination["id"]
    analysis = fw_client.get(destination_id)
    source_project = fw_client.get(analysis.parents["project"])

    project_user_perms = [
        perm.role_ids
        for perm in source_project.permissions
        if perm.id == current_user.id
    ]
    if project_user_perms:
        project_user_perms = project_user_perms[0]

    if not set(permitted).intersection(project_user_perms):
        message = "You do not have sufficient permissions to run this gear."
        log.error(message)
        raise InsufficientPermissionsError(message)


def check_for_duplicate_execution(fw_client, gear_name):
    """
    Checks for the existence of a duplicate running gear.

    Args:
        fw_client (flywheel.Client): A flywheel client
        gear_name (str): The name of the running gear

    Raises:
        DuplicateJobError: If a duplicate job is found, raise this error with message
    """
    jobs = [
        job
        for job in fw_client.jobs.find(f"gear_info.name={gear_name}")
        if job.state in ["running", "pending"]
    ]
    if len(jobs) >= 2:
        message = "Two or more concurrent gear executions is not allowed."
        log.error(message)
        raise DuplicateJobError(message)
