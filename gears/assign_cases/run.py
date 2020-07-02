#!/usr/bin/env python3
"""
This gear, assign-cases, assigns cases to individual reader projects.  Reader projects 
are created with the assign-readers gear.
"""

import logging
import os

from gear_toolkit import gear_toolkit_context

from utils.check_jobs import (
    DuplicateJobError,
    InsufficientPermissionsError,
    check_for_duplicate_execution,
    verify_user_permissions,
)
from utils.manage_cases import InvalidGroupError, distribute_cases_to_readers

log = logging.getLogger(__name__)


def main(context):
    try:
        fw_client = context.client

        verify_user_permissions(fw_client, context)
        check_for_duplicate_execution(fw_client)

        destination_id = context.destination["id"]
        analysis = fw_client.get(destination_id)
        source_project = fw_client.get(analysis.parents["project"])
        reader_group_id = "readers"

        # If gear is run within the Readers group, error and exit
        if analysis.parents["group"] == reader_group_id:
            raise InvalidGroupError(
                'This gear cannot be run from within the "Readers" group!'
            )

        source_sess_df, dest_proj_df, exported_data_df = distribute_cases_to_readers(
            fw_client, source_project, reader_group_id, context.config["case_coverage"],
        )

        source_sess_df.to_csv(str(context.output_dir / "master_project_case_data.csv"))
        dest_proj_df.to_csv(str(context.output_dir / "reader_project_case_data.csv"))
        exported_data_df.to_csv(str(context.output_dir / "exported_data.csv"))
    except (DuplicateJobError, InsufficientPermissionsError, InvalidGroupError,) as e:
        log.error(e.message)
        log.fatal("Error executing assign-readers.",)
        return 1
    except Exception as e:
        log.exception(e,)
        log.fatal("Error executing assign-cases.",)
        return 1

    log.info("assign-cases completed Successfully!")
    return 0


if __name__ == "__main__":
    # TODO: Eliminate for site-testing.
    tst_dir = "/home/joshuajacobs/Projects/2020.03.13.NYU.Tear_Assessment/Data/assign-cases-0.0.2-dev-d_5efa219b4a97dc035c87f963"
    with gear_toolkit_context.GearToolkitContext(tst_dir) as gear_context:
        gear_context.init_logging()
        exit_status = main(gear_context)

    log.info("exit_status is %s", exit_status)
    os.sys.exit(exit_status)
