#!/usr/bin/env python3
"""
This gear, assign-single-case, assigns a single case to a specified reader.  Reader
projects are created with the assign-readers gear.
"""

import logging
import os

from gear_toolkit import gear_toolkit_context

from utils.check_jobs import check_for_duplicate_execution
from utils.manage_cases import (
    InvalidGroupError,
    InvalidLaunchContainerError,
    assign_single_case,
    check_valid_reader,
)

log = logging.getLogger(__name__)


def main(context):
    try:
        fw_client = context.client

        check_for_duplicate_execution(fw_client, "assign-single-case")

        destination_id = context.destination["id"]
        analysis = fw_client.get(destination_id)

        reader_group_id = "readers"

        # If gear is run within the Readers group, error and exit
        if analysis.parents["group"] == reader_group_id:
            raise InvalidGroupError(
                'This gear cannot be run from within the "Readers" group!'
            )

        if analysis.parents["session"]:
            source_session = fw_client.get(analysis.parents["session"])
        else:
            raise InvalidLaunchContainerError(
                'This gear can only be run at the "Session" level.'
            )

        if check_valid_reader(
            fw_client, context.config["reader_email"], reader_group_id
        ):
            source_sess_df, dest_proj_df, exported_data_df = assign_single_case(
                fw_client,
                source_session,
                reader_group_id,
                context.config["reader_email"],
                context.config["assignment_reason"],
            )

        source_sess_df.to_csv(str(context.output_dir / "master_project_case_data.csv"))
        dest_proj_df.to_csv(str(context.output_dir / "reader_project_case_data.csv"))
        exported_data_df.to_csv(str(context.output_dir / "exported_data.csv"))

    except Exception as e:
        log.exception(e,)
        log.fatal("Error executing assign-single-case.",)
        return 1

    log.info("assign-single-case completed Successfully!")
    return 0


if __name__ == "__main__":
    # TODO: Eliminate for site-testing.
    tst_dir = (
        "/home/joshuajacobs/Projects/2020.03.13.NYU.Tear_Assessment/Data/"
        + "scatter-cases-0.0.1-dev-h_5ebaec31bfda5102456aa0c7"
    )
    with gear_toolkit_context.GearToolkitContext() as gear_context:
        gear_context.init_logging()
        exit_status = main(gear_context)

    log.info("exit_status is %s", exit_status)
    os.sys.exit(exit_status)
