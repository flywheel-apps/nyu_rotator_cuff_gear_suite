"""
A collection of container-specific functions for the creation and management of
groups, projects, sessions, and acquisitions. File operations are handled in a
different module.
"""
import logging
import time

import flywheel

from .file_operations import _export_files

log = logging.getLogger(__name__)

# Used to record the creation of subjects, sessions, and acquisitions
# On failure, a list of these will be parsed and deleted
CREATED_CONTAINER_TEMPLATE = {"container": None, "id": None, "new": None}

# Used to record the succesful export of subjects, session, and acquisitions
# On success, this is delivered to the project to record the exported objects
EXPORTED_CONTAINER_TEMPLATE = {
    "container": "",
    "name": "",
    "status": "",
    "origin_path": "",
    "export_path": "",
    "archive_path": "",
}

SUBJECT_KEYS = [
    "code",
    "cohort",
    "ethnicity",
    "firstname",
    "info",
    "label",
    "lastname",
    "race",
    "sex",
    "species",
    "strain",
    "tags",
    "type",
]

SESSION_KEYS = [
    "age",
    "info",
    "label",
    "operator",
    "timestamp",
    "timezone",
    "weight",
    "uid",
]

ACQUISITION_KEYS = ["info", "label", "timestamp", "timezone", "uid"]


def define_export(fw_client, container, dest_project):
    """
    define an exported container by source and destination paths

    described in EXPORTED_CONTAINER_TEMPLATE

    Args:
        fw_client (flywheel.Client): Flywheel Client object instantiated on instance
        container (flywheel.container): A subject, session, or acquisition container

    Returns:
        dict: The exported container descriptor according to EXPORTED_CONTAINER_TEMPLATE
    """

    export_obj = EXPORTED_CONTAINER_TEMPLATE.copy()
    export_obj["container"] = container.container_type

    source_project = fw_client.get(container.parents["project"])

    if export_obj["container"] is "subject":
        export_obj["name"] = container.code
    else:
        export_obj["name"] = container.label
        export_obj["status"] = "created"

    export_obj["origin_path"] = f"{source_project.group}/{source_project.label}"
    export_obj["export_path"] = f"{dest_project.group}/{dest_project.label}"

    if export_obj["container"] is "subject":
        export_obj["origin_path"] += f"/{container.code}"
        export_obj["export_path"] += f"/{container.code}"
    elif export_obj["container"] is "session":
        subject = fw_client.get(container.parents["subject"])
        export_obj["origin_path"] += f"/{subject.code}/{container.label}"
        export_obj["export_path"] += f"/{subject.code}/{container.label}"
    elif export_obj["container"] is "acquisition":
        subject = fw_client.get(container.parents["subject"])
        session = fw_client.get(container.parents["session"])
        export_obj[
            "origin_path"
        ] += f"/{subject.code}/{session.label}/{container.label}"
        export_obj[
            "export_path"
        ] += f"/{subject.code}/{session.label}/{container.label}"

    return export_obj


def define_created(container):
    """
    Define a created container record according to CREATED_CONTAINER_TEMPLATE

    Args:
        container (flywheel.container): A flywheel container. "subject", "session",
            or "acquisition"

    Returns:
        dict: CREATED_CONTAINER_TEMPLATE
    """
    created_container = CREATED_CONTAINER_TEMPLATE.copy()
    created_container["container"] = container.container_type
    created_container["id"] = container.id
    created_container["new"] = True

    return created_container


def _cleanup(fw_client, created_data):
    """
    In the case of a failure, cleanup all containers that were created.

    Args:
        fw_client (flywheel.Client): The Flywheel Client
        created_data (dict): A list of CREATED_CONTAINER_TEMPLATE instances
    """

    acquisitions = [x for x in created_data if x["container"] == "acquisition"]
    if acquisitions:
        log.info("Deleting %i acquisition containers", len(acquisitions))
        for a in acquisitions:
            log.debug(a)
            fw_client.delete_acquisition(a["id"])

    sessions = [x for x in created_data if x["container"] == "session"]
    if sessions:
        log.info("Deleting %i session containers", len(sessions))
        for s in sessions:
            log.debug(s)
            fw_client.delete_session(s["id"])

    subjects = [x for x in created_data if x["container"] == "subject" and x["new"]]
    if subjects:
        log.info("Deleting %i subject containers", len(subjects))
        for s in subjects:
            log.debug(s)
            fw_client.delete_subject(s["id"])


def find_or_create_group(fw_client, group_id, group_label):
    """
    return an existing group or return a created group with group_id and group_label

    Args:
        fw_client (flywheel.Client): Flywheel Client
        group_id (str): The ID of the group
        group_label (str): The name of the group

    Returns:
        tuple: The tuple of created flywheel.Group and CREATED_CONTAINER_TEMPLATE
    """
    found_groups = fw_client.groups.find(f'_id="{group_id}"')

    if len(found_groups) > 0:
        return found_groups[0].reload(), []

    group_id = fw_client.add_group(flywheel.Group(group_id, group_label))

    group = fw_client.groups.find_first(f'_id="{group_id}"')

    # admin_role = [role for role in fw_client.get_all_roles() if role.label == "admin"][
    #     0
    # ]

    # site_admins = [user for user in fw_client.users() if "site_admin" in user.roles]
    # for admin in site_admins:
    #     if not [perm.id for perm in group.permissions_template if perm.id == admin.id]:
    #         role_assignment = flywheel.RolesRoleAssignment(admin.id, [admin_role.id])
    #         group.permissions_template.append(role_assignment)
    #     if not [perm.id for perm in group.permissions if perm.id == admin.id]:
    #         group.add_permission({"_id": admin.id, "access": "admin"})

    created_container = define_created(group)

    return group.reload(), [created_container]


def apply_group_template_to_project(fw_client, project, group):
    """
    Apply a group's permission template to a given project

    Args:
        project (flywheel.Project): A flywheel project to apply a template
        group (flywheel.Group): A flywheel group with a permissions template
    """
    permissions = group.permissions_template
    all_users = [x.id for x in fw_client.get_all_users()]
    users = [x.id for x in project.permissions]
    for permission in permissions:
        if not isinstance(
            permission, flywheel.models.roles_role_assignment.RolesRoleAssignment
        ):
            permission = flywheel.RolesRoleAssignment(
                permission["id"], permission["role_ids"]
            )
        if (permission.id not in users) and (permission.id in all_users):
            log.info(" Adding {} to {}".format(permission.id, project.label))
            project.add_permission(permission)
        else:
            log.warning(
                " {} will not be added to {}. The user is either already "
                "in the project or not a valid user.".format(
                    permission.id, project.label
                )
            )


def create_project(fw_client, project_label, group, user_id, project_info={}):

    """
    Create a new reader project under group with user_id as only rw-user.

    Reader project will have a maximum number of sessions defined by max_assignments.

    Args:
        fw_client (flywheel.Client): Flywheel Client object instantiated on instance
        project_label (str): A string representing the label of the new project
        group (flywheel.Group): The target group container
        user_id (str): ID of user, identified by email address
        project_info (dict, optional): The "Custom Information" of the project.
            Defaults to {}.

    Returns:
        tuple: new_project (the created project),
            created_container (CREATED_CONTAINER_TEMPLATE)
    """

    new_project = group.add_project({"label": project_label})
    apply_group_template_to_project(fw_client, new_project, group)

    new_project.update_info(project_info)
    new_project = new_project.reload()

    # Get the generic "read-write" role and apply to the user for this project
    rw_role = [
        role for role in fw_client.get_all_roles() if role.label == "read-write"
    ][0]
    user_permission = {"_id": user_id, "role_ids": [rw_role.id]}
    # If the assigner and reader are the same, accomodate for a user with admin role
    # that is automatically given permissions to the project
    if [perm.id for perm in new_project.permissions if perm.id == user_id]:
        new_project.update_permission(user_id, user_permission)
    else:
        new_project.add_permission(user_permission)

    created_container = define_created(new_project)

    return new_project, created_container


def export_or_find_subject(fw_client, source_subject, dest_project):
    """
    Exports source_subject to dest_project.

    If source_subject exists in dest_project the destination subject is returned.

    Args:
        fw_client (flywheel.Client): Flywheel Client object instantiated on instance
        source_subject (flywheel.Subject): The source subject to export
        dest_project (flywheel.Project): The destination project to receive
            the exported subject

    Returns:
        tuple:  dest_subject(flywheel.Subject),
                subj_export(EXPORTED_CONTAINER_TEMPLATE),
                created_container(CREATED_CONTAINER_TEMPLATE)
    """
    subj_export = define_export(fw_client, source_subject, dest_project)

    dest_subject = dest_project.subjects.find_first(f'code="{source_subject.code}"')
    if not dest_subject:
        log.info(
            "Subject %s does not exist in project %s.",
            source_subject.code,
            dest_project.label,
        )
        log.info("CREATING SUBJECT CONTAINER")
        subj_export["status"] = "created"
        subject_metadata = {}
        for key in SUBJECT_KEYS:
            value = source_subject.get(key)
            if value:
                subject_metadata[key] = value

        # Attempt to create the subject. This may fail as a batch-run could
        # result in the subject having been created already, thus we try/except
        # and look for the subject again.
        try:
            dest_subject = dest_project.add_subject(subject_metadata)
            log.info("Created %s in %s", dest_subject.code, dest_project.label)

            created_container = define_created(dest_subject)

        except flywheel.ApiException as e:
            log.warning(
                "Could not generate subject: {} -- {}".format(e.status, e.reason)
            )
            log.info("Attempting to find subject...")
            time.sleep(2)
            dest_subject = dest_project.subjects.find_first(
                f'code="{source_subject.code}"'
            )
            if dest_subject:
                log.info(
                    "... found existing subject %s in project: %s. "
                    "Using existing container.",
                    dest_subject.code,
                    dest_project.label,
                )
                subj_export["status"] = "used existing"
            else:
                raise
    else:
        log.info(
            "Found existing subject %s in project: %s. Using existing container.",
            dest_subject.code,
            dest_project.label,
        )
        subj_export["status"] = "used existing"
        created_container = None

    return dest_subject, subj_export, created_container


def export_session(fw_client, source_session, dest_project, export_info=False):
    """
    Export a session (source_session) to project (dest_project).

    Args:
        fw_client (flywheel.Client): Flywheel Client object instantiated on instance
        source_session (flywheel.Session): The session to be exported.
        dest_project (flywheel.Project): The destination project receiving the
            source session

    Returns:
        tuple:  dest_session(flywheel.Session),
                exported_data(EXPORTED_CONTAINER_TEMPLATE),
                created_data (CREATED_CONTAINER_TEMPLATE)
    """
    exported_data = []

    # specific information about each container created, for ease of deletion on failure
    created_data = []

    source_subject = source_session.subject
    try:
        ########################################################################
        # Create Subject
        # export subject to new project, if the subject exists in that project,
        # use that subject

        dest_subject, subj_export, created_container = export_or_find_subject(
            fw_client, source_subject, dest_project
        )

        exported_data.append(subj_export)

        if created_container:
            created_data.append(created_container)
        ########################################################################
        # Create the dest_session
        log.info(
            "CREATING SESSION CONTAINER %s IN %s/%s",
            source_session.label,
            dest_project.label,
            source_subject.label,
        )
        session_export = define_export(fw_client, source_session, dest_project)

        session_metadata = {}
        for key in SESSION_KEYS:
            if not (key == "info" and export_info is False):
                value = source_session.get(key)
                if value:
                    session_metadata[key] = value

        # Add session to the subject
        dest_session = dest_subject.add_session(session_metadata)
        created_container = define_created(dest_session)

        for tag in source_session.tags:
            dest_session.add_tag(tag)

        exported_data.append(session_export)

        if created_container:
            created_data.append(created_container)
        ########################################################################
        # For each acquisition, create the export_acquisition, upload and modify
        # the files
        num_acq = len(source_session.acquisitions())
        log.info("EXPORTING %i ACQUISITIONS...", num_acq)
        acq_count = 0
        if num_acq == 0:
            log.warning(
                "NO ACQUISITIONS FOUND ON THE SESSION! "
                "Resulting session will have no acquisitions."
            )
        for source_acquisition in source_session.acquisitions():
            acq_count += 1
            log.info("ACQUISITION %i/%i", acq_count, num_acq)
            log.info(
                "CREATING ACQUISITION CONTAINER: [label=%s]", source_acquisition.label
            )
            _, acq_export, created_container = export_acquisition(
                fw_client, source_acquisition, dest_session
            )
            exported_data.append(acq_export)

            if created_container:
                created_data.append(created_container)

        log.info("All acquisitions exported.")
        source_session = source_session.reload()
        # if 'EXPORTED' not in source_session.get('tags', []):
        #     log.info(
        #         'Adding "EXPORTED" tag to %s.',
        #         source_session.label
        #     )
        #     source_session.add_tag('EXPORTED')

        return dest_session, exported_data, created_data
    except Exception as e:
        log.exception("ERRORS DETECTED exporting session, %s", source_session.label)
        log.info("CLEANING UP...")
        _cleanup(fw_client, created_data)
        raise e


def export_acquisition(fw_client, source_acquisition, dest_session):
    """
    exports acquisition object, acquisition metadata, and acquisitions files

    Args:
        fw_client (flywheel.Client): Flywheel Client object instantiated on instance
        source_acquisition (flywheel.Acquisition): Flywheel acquisition to export
        dest_session (flywheel.Session): Flywheel session to receive source acquisition

    Returns:
        tuple:  dest_acquisition(flywheel.Acquisition),
                acquisition_export(EXPORTED_CONTAINER_TEMPLATE),
                created_container(CREATED_CONTAINER_TEMPLATE)
    """
    # source_subject = fw_client.get(source_acquisition.parents['subject'])
    # source_session = fw_client.get(source_acquisition.parents['session'])
    dest_project = fw_client.get(dest_session.project)
    acquisition_export = define_export(fw_client, source_acquisition, dest_project)

    acquisition_metadata = {}
    for key in ACQUISITION_KEYS:
        value = source_acquisition.get(key)
        if value:
            acquisition_metadata[key] = value

    # Add acquisition to the session
    dest_acquisition = dest_session.add_acquisition(acquisition_metadata)

    created_container = define_created(dest_acquisition)

    for tag in source_acquisition.tags:
        dest_acquisition.add_tag(tag)

    # Export the individual files in each acquisition
    log.info("Exporting files to %s...", dest_acquisition.label)
    _export_files(fw_client, source_acquisition, dest_acquisition)

    return dest_acquisition, acquisition_export, created_container
