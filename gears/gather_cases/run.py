#!/usr/bin/env python3

import logging
import os

from flywheel_gear_toolkit import GearToolkitContext

from utils.check_jobs import (
    DuplicateJobError,
    InsufficientPermissionsError,
    check_for_duplicate_execution,
    verify_user_permissions,
)
from utils.manage_cases import (
    InvalidGroupError,
    MissingDICOMTagError,
    UninitializedGroupError,
    gather_case_data_from_readers,
    generate_summary_report,
)


log = logging.getLogger(__name__)
log.setLevel("DEBUG")

def main(context):
    try:
        fw_client = context.client

        verify_user_permissions(fw_client, context)
        check_for_duplicate_execution(fw_client)

        destination_id = context.destination["id"]
        analysis = fw_client.get(destination_id)
        source_project = fw_client.get_project(analysis.parents["project"])
        reader_group_id = source_project.group
        copyroi = context.config["Display Reads In Main Project"]

        # TODO: Make sure this doesn't mess other things up
        # If gear is run within the Readers group, error and exit
        # if analysis.parents["group"] == reader_group_id:
        #     raise InvalidGroupError(
        #         'This gear cannot be run from within the "Readers" group!'
        #     )

        # Check for projects in the reader group
        group = fw_client.get(reader_group_id).reload()
        if len(group.projects.find("label=~Reader [0-9][0-9]?")) == 0:
            
            # For Legacy check for "Readers" groups
            reader_group_id = "readers"
            group = fw_client.get(reader_group_id).reload()
            
            log.debug("Looking for legacy group 'Readers'")
            
            if len(group.projects.find("label=~Reader [0-9][0-9]?")) == 0:
                raise UninitializedGroupError(
                    'The "Readers" group has not been initialized.'
                )

        source_sessions_df, case_assessment_df = gather_case_data_from_readers(
            fw_client, source_project, copyroi
        )

        progress_report = generate_summary_report(fw_client, case_assessment_df)

        progress_report.to_csv(
            str(context.output_dir / "reader_progress_report.csv"), index=False
        )

        source_sessions_df.to_csv(
            str(context.output_dir / "master_project_summary_data.csv"), index=False
        )

        case_assessment_df.to_csv(
            str(context.output_dir / "case_assignment_status_export.csv"), index=False
        )
        if source_sessions_df.assigned.sum() == 0:
            log.warning(
                "There are no cases assigned to readers. "
                "Ensure there are cases assigned to readers by running both the "
                "`assign-readers` and `assign-cases` gears with valid configuration."
            )

    except (
        DuplicateJobError,
        InsufficientPermissionsError,
        InvalidGroupError,
        UninitializedGroupError,
        MissingDICOMTagError,
    ) as e:
        log.error(e.message)
        log.fatal("Error executing assign-readers.",)
        return 1
    except Exception as e:
        log.exception(e,)
        log.fatal("Error executing gather-cases-data.",)
        return 1

    log.info("gather-cases-data completed Successfully!")
    return 0


if __name__ == "__main__":
    with GearToolkitContext() as gear_context:
        gear_context.init_logging()
        exit_status = main(gear_context)

    log.info("exit_status is %s", exit_status)
    os.sys.exit(exit_status)
