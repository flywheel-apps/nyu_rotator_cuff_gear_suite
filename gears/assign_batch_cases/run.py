#!/usr/bin/env python3
"""
This gear, assign-batch-cases, assigns a batch of cases to readers specified in an
input csv file. Reader projects are created with the assign-readers gear.
"""

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
    ExceededConstraintsError,
    ExistingReaderCaseError,
    InvalidGroupError,
    InvalidLaunchContainerError,
    InvalidReaderError,
    MissingDataError,
    distribute_batch_to_readers,
)
logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)



def main(context):
    try:
        fw_client = context.client

        verify_user_permissions(fw_client, context)
        check_for_duplicate_execution(fw_client)

        destination_id = context.destination["id"]
        analysis = fw_client.get(destination_id)
        source_project = fw_client.get(analysis.parents["project"])
        reader_group_id = context.config.get("reader_group_id")
        dry_run = context.config.get("dry_run", False)

        source_group_id = source_project.group
        if reader_group_id is None:
            reader_group_id = source_group_id

        # If gear is run within the Readers group, error and exit
        # if analysis.parents["group"] == reader_group_id:
        #     raise InvalidGroupError(
        #         'This gear cannot be run from within the "Readers" group!'
        #     )

        # Distribute batch to readers
        (
            source_sess_df,
            dest_proj_df,
            exported_data_df,
            batch_df,
        ) = distribute_batch_to_readers(
            fw_client,
            source_project,
            reader_group_id,
            context.config["case_coverage"],
            context.get_input_path("batch_csv"),
            dry_run,
        )

        batch_df.to_csv(str(context.output_dir / "batch_results.csv"))
        # If no assignments were successful, fail the gear.
        if not any(batch_df.passed):
            raise ExceededConstraintsError("All assignments have failed.")

        source_sess_df.to_csv(str(context.output_dir / "master_project_case_data.csv"))
        dest_proj_df.to_csv(str(context.output_dir / "reader_project_case_data.csv"))
        exported_data_df.to_csv(str(context.output_dir / "exported_data.csv"))

    except (
        DuplicateJobError,
        InsufficientPermissionsError,
        InvalidGroupError,
        InvalidLaunchContainerError,
        InvalidReaderError,
        ExistingReaderCaseError,
        ExceededConstraintsError,
        MissingDataError,
    ) as e:
        log.error(e.message)
        log.fatal("Error executing assign-batch-cases.",)
        return 1
    except Exception as e:
        log.exception(e,)
        log.fatal("Error executing assign-batch-cases.",)
        return 1

    # if there were some failures encountered, mark as "successful" but warn
    if not all(batch_df.passed):
        log.warning("assign-batch-cases completed with some errors.")
        log.warning("Please examine log and output for details.")
        return 0

    log.info("assign-batch-cases completed Successfully!")
    return 0


if __name__ == "__main__":
    with GearToolkitContext() as gear_context:
        gear_context.init_logging('debug')
        exit_status = main(gear_context)

    log.info("exit_status is %s", exit_status)
    os.sys.exit(exit_status)
