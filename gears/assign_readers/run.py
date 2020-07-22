#!/usr/bin/env python3

import logging
import os

from gear_toolkit import gear_toolkit_context

from utils.check_jobs import (
    DuplicateJobError,
    InsufficientPermissionsError,
    check_for_duplicate_execution,
    verify_user_permissions,
)
from utils.container_operations import find_or_create_group
from utils.manage_cases import (
    InvalidGroupError,
    InvalidInputError,
    create_or_update_reader_projects,
    define_reader_csv,
)

log = logging.getLogger(__name__)


def main(context):
    try:
        fw_client = context.client

        verify_user_permissions(fw_client, context)
        check_for_duplicate_execution(fw_client)

        created_data = []
        destination_id = context.destination["id"]
        analysis = fw_client.get(destination_id)
        source_project = fw_client.get(analysis.parents["project"])
        reader_group_id = "readers"
        # Find or create reader group
        reader_group, _created_data = find_or_create_group(
            fw_client, reader_group_id, "Readers"
        )
        created_data.extend(_created_data)

        # If gear is run within the Readers group, error and exit
        if analysis.parents["group"] == reader_group_id:
            raise InvalidGroupError(
                'This gear cannot be run from within the "Readers" group!'
            )

        reader_csv_path = define_reader_csv(context)

        _created_data = create_or_update_reader_projects(
            fw_client, reader_group, source_project, readers_csv=reader_csv_path,
        )
        created_data.extend(_created_data)
    except (
        DuplicateJobError,
        InsufficientPermissionsError,
        InvalidGroupError,
        InvalidInputError,
    ) as e:
        log.error(e.message)
        log.fatal("Error executing assign-readers.",)
        return 1
    except Exception as e:
        log.exception(e,)
        log.fatal("Error executing assign-readers.",)
        return 1

    log.info("assign-readers completed successfully!")
    return 0


if __name__ == "__main__":

    with gear_toolkit_context.GearToolkitContext() as gear_context:
        gear_context.init_logging()
        exit_status = main(gear_context)

    log.info("exit_status is %s", exit_status)
    os.sys.exit(exit_status)
