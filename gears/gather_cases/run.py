#!/usr/bin/env python3

import logging
import os

from gear_toolkit import gear_toolkit_context

from utils.check_jobs import check_for_duplicate_execution
from utils.manage_cases import InvalidGroupError, gather_case_data_from_readers

log = logging.getLogger(__name__)


def main(context):
    try:
        fw_client = context.client

        check_for_duplicate_execution(fw_client, "gather-cases")

        destination_id = context.destination["id"]
        analysis = fw_client.get(destination_id)
        source_project = fw_client.get(analysis.parents["project"])
        reader_group_id = "readers"

        # If gear is run within the Readers group, error and exit
        if analysis.parents["group"] == reader_group_id:
            raise InvalidGroupError(
                'This gear cannot be run from within the "Readers" group!'
            )

        source_sessions_df = gather_case_data_from_readers(fw_client, source_project)
        source_sessions_df.to_csv(
            str(context.output_dir / "master_project_summary_data.csv")
        )

        if source_sessions_df.assigned.sum() == 0:
            log.warning(
                "There are no cases assigned to readers. "
                "Ensure there are cases assigned to readers by running both the "
                "`assign-readers` and `assign-cases` gears with valid configuration."
            )

    except Exception as e:
        log.exception(e,)
        log.fatal("Error executing gather-cases-data.",)
        return 1

    log.info("gather-cases-data completed Successfully!")
    return 0


if __name__ == "__main__":
    with gear_toolkit_context.GearToolkitContext() as gear_context:
        gear_context.init_logging()
        exit_status = main(gear_context)

    log.info("exit_status is %s", exit_status)
    os.sys.exit(exit_status)
