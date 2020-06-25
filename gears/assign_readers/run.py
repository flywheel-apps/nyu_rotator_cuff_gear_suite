#!/usr/bin/env python3

import logging
import os
import re
from pathlib import Path

import pandas as pd
from gear_toolkit import gear_toolkit_context

from utils.check_jobs import check_for_duplicate_execution, verify_user_permissions
from utils.container_operations import find_or_create_group
from utils.manage_cases import (
    InvalidGroupError,
    InvalidInputError,
    create_or_update_reader_projects,
)

log = logging.getLogger(__name__)


def define_reader_csv(context):
    """
    Loads, updates or creates a csv file based on gear input and configuration

    If the reader_csv is specified in the gear configuration (and is valid) it is
    loaded as a pandas dataframe.

    If a specified reader is valid (email, firstname, lastname) it is appended
    to the pandas dataframe (if invalid, skipped).

    Without the reader_csv (or invalid) the specified reader is validated and saved to
    a csv file in the context.work directory.  If specified reader is invalid,
    None is returned.

    Args:
        context (gear_toolkit.GearContext): The gear context

    Raises:
        InvalidInputError: If neither the configuration (email, firstname, lastname) nor
            the input (csv with fields email, firstname, lastname, max_cases) is valid
            then this Error is thrown and the gear fails with message.

    Returns:
        str: The path of the resultant csv file or None (fail)
    """
    readers_df = []
    # regex for checking validity of readers email
    regex = r"^[a-zA-Z0-9.]+[\._]?[a-zA-Z0-9.]+[@]\w+[.]\w{2,3}$"
    # Ensure valid inputs and act consistently
    reader_csv_path = context.get_input_path("reader_csv")
    if reader_csv_path:
        readers_df = pd.read_csv(reader_csv_path)
        # Validate that dataframe has required columns before proceeding
        req_columns = ["email", "first_name", "last_name", "max_cases"]
        if not all([(c in readers_df.columns) for c in req_columns]):
            log.warning(
                'The csv-file "%s" did not have the required columns("%s").'
                + "Proceeding without reader CSV.",
                Path(reader_csv_path).name,
                '", "'.join(req_columns),
            )
            reader_csv_path = None
        else:
            # if we have a reader email, check for existence in csv (update),
            # otherwise we need to create (if all conditions are satisfied)
            if context.config.get("reader_email"):
                reader_email = context.config.get("reader_email")
                # if we find the reader's email in the dataframe,
                if len(readers_df[readers_df.email == reader_email]) > 0:
                    indx = readers_df[readers_df.email == reader_email].index[0]
                    # Update the max_cases in the dataframe
                    readers_df.loc[indx, "max_cases"] = context.config["max_cases"]
                    # This will trigger an update in the metadata on assign-cases
                # else if we have reader's email, firstname, and lastname
                elif (
                    context.config.get("max_cases")
                    and (context.config.get("max_cases") > 0)
                    and (context.config.get("max_cases") < 600)
                    and context.config.get("reader_email")
                    and re.search(regex, context.config.get("reader_email"))
                    and context.config.get("reader_firstname")
                    and context.config.get("reader_lastname")
                ):
                    readers_df = readers_df.append(
                        {
                            "email": context.config.get("reader_email"),
                            "first_name": context.config.get("reader_firstname"),
                            "last_name": context.config.get("reader_lastname"),
                            "max_cases": context.config.get("max_cases"),
                        },
                        ignore_index=True,
                    )
                # else the indicated reader is invalid
                else:
                    log.warning(
                        "The specified reader is not configured correctly. "
                        'Proceeding without specified reader ("%s").',
                        '", "'.join(
                            [
                                str(context.config.get("reader_email")),
                                str(context.config.get("reader_firstname")),
                                str(context.config.get("reader_lastname")),
                            ]
                        ),
                    )
            # Create a csv and return its path
            work_csv = context.work_dir / Path(reader_csv_path).name
            readers_df.to_csv(work_csv, index=False)
            return work_csv

    # if the csv is not provided and we have a valid reader entry
    if not reader_csv_path and (
        context.config.get("max_cases")
        and (context.config.get("max_cases") > 0)
        and (context.config.get("max_cases") < 600)
        and context.config.get("reader_email")
        and re.search(regex, context.config.get("reader_email"))
        and context.config.get("reader_firstname")
        and context.config.get("reader_lastname")
    ):
        # create that dataframe
        readers_df = pd.DataFrame(
            data={
                "email": context.config.get("reader_email"),
                "first_name": context.config.get("reader_firstname"),
                "last_name": context.config.get("reader_lastname"),
                "max_cases": context.config.get("max_cases"),
            },
            index=[0],
        )
        # save it to the work directory
        work_csv = context.work_dir / "temp.csv"
        readers_df.to_csv(work_csv, index=False)
        return work_csv
    else:
        raise InvalidInputError(
            "Cannot proceed without a valid CSV file or valid specified reader!"
        )


def main(context):
    try:
        fw_client = context.client

        verify_user_permissions(fw_client, context)
        check_for_duplicate_execution(fw_client, "assign-readers")

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
        max_cases = (
            context.config.get("max_cases") if context.config.get("max_cases") else 30
        )

        _created_data = create_or_update_reader_projects(
            fw_client,
            reader_group,
            source_project,
            max_cases,
            readers_csv=reader_csv_path,
        )
        created_data.extend(_created_data)
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
