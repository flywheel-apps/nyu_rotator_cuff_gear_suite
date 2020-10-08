"""
This set of unit tests evaluate the proper functioning of the "define_reader_csv"
function.  This function takes a gear context as input. Therefore, the configuration
and input files are necessary through a gear directory.
"""
import json
import shutil
import tempfile
from pathlib import Path

import pandas as pd
import pytest
from flywheel_gear_toolkit import GearToolkitContext
from gears.assign_readers.utils.manage_cases import InvalidInputError, define_reader_csv

DATA_ROOT = Path(__file__).parents[2] / "data"


def create_gear_config(email=None, firstname=None, lastname=None, max_cases=30):
    config = {}
    if email:
        config["reader_email"] = email
    if firstname:
        config["reader_firstname"] = firstname
    if lastname:
        config["reader_lastname"] = lastname
    config["max_cases"] = max_cases

    return config


def create_gear_dir(tmp_folder):
    gear_dir = Path(tmp_folder) / "gear"
    shutil.copytree(DATA_ROOT / "assign_readers/unit_test_csv", gear_dir)
    config_tochange = json.load(open(gear_dir / "config.json", "r"))
    input_path = config_tochange["inputs"]["reader_csv"]["location"]["path"]
    input_path = input_path.replace("DATA_DIR", str(gear_dir))
    config_tochange["inputs"]["reader_csv"]["location"]["path"] = input_path

    json.dump(config_tochange, open(gear_dir / "config.json", "w"))

    return gear_dir


def create_invalid_csv(context):
    input_path = context.get_input_path("reader_csv")
    # create an error in the CSV file by altering one of the column names
    readers_df = pd.read_csv(input_path)
    columns = list(readers_df.columns)
    columns[0] = "sbemail"
    readers_df.columns = columns
    readers_df.to_csv(input_path, index=False)


def test_valid_config():
    with tempfile.TemporaryDirectory() as tmp_folder:
        # Create the temporay gear directory
        gear_dir = Path(tmp_folder) / "gear"
        gear_dir.mkdir(parents=True, exist_ok=True)

        # Instantiate a gear context object
        with GearToolkitContext(gear_path=gear_dir, input_args=[]) as context:
            # create a configuration
            config = create_gear_config(
                "test.email@email.com", "test-firstname", "test-lastname", 23
            )
            for k, v in config.items():
                context.config[k] = v

            # Create a reader csv that will be used to populate with one reader
            reader_csv_path = define_reader_csv(context)

            # Assert that these have the expected path
            assert reader_csv_path == context.work_dir / "temp.csv"

            # Load the created csv
            test_df = pd.read_csv(reader_csv_path)

            # Test its values with respects to the config above.
            assert [
                test_df.email[0],
                test_df.first_name[0],
                test_df.last_name[0],
                test_df.max_cases[0],
            ] == [
                config["reader_email"],
                config["reader_firstname"],
                config["reader_lastname"],
                config["max_cases"],
            ]


def test_email_capitalization():
    with tempfile.TemporaryDirectory() as tmp_folder:
        # Create the temporay gear directory
        gear_dir = Path(tmp_folder) / "gear"
        gear_dir.mkdir(parents=True, exist_ok=True)

        # Instantiate a gear context object
        with GearToolkitContext(gear_path=gear_dir, input_args=[]) as context:
            # create a configuration
            config = create_gear_config(
                "Test.Email@email.com", "test-firstname", "test-lastname", 23
            )
            for k, v in config.items():
                context.config[k] = v

            # Create a reader csv that will be used to populate with one reader
            reader_csv_path = define_reader_csv(context)

            # Assert that these have the expected path
            assert reader_csv_path == context.work_dir / "temp.csv"

            # Load the created csv
            test_df = pd.read_csv(reader_csv_path)

            # Test its values with respects to the config above.
            assert [
                test_df.email[0],
                test_df.first_name[0],
                test_df.last_name[0],
                test_df.max_cases[0],
            ] == [
                config["reader_email"].lower(),
                config["reader_firstname"],
                config["reader_lastname"],
                config["max_cases"],
            ]


def test_invalid_config():
    with tempfile.TemporaryDirectory() as tmp_folder:
        # Create the temporay gear directory
        gear_dir = Path(tmp_folder) / "gear"
        gear_dir.mkdir(parents=True, exist_ok=True)

        # Instantiate a gear context object
        with GearToolkitContext(gear_path=gear_dir, input_args=[]) as context:
            # create a configuration
            config = create_gear_config(
                "test.email@email.com", None, "test-lastname", 23
            )
            for k, v in config.items():
                context.config[k] = v

            # Create a reader csv that will be used to populate with one reader
            try:
                reader_csv_path = define_reader_csv(context)

            except InvalidInputError as e:
                assert isinstance(e, InvalidInputError)
                assert (
                    e.message
                    == "Cannot proceed without a valid CSV"
                    + " file or valid specified reader!"
                )


def test_valid_user_csv(tmpdir):
    gear_dir = create_gear_dir(tmpdir)
    with GearToolkitContext(gear_path=gear_dir, input_args=[]) as context:
        reader_csv_path = define_reader_csv(context)
        assert (
            reader_csv_path
            == gear_dir / "work" / context.get_input("reader_csv")["location"]["name"]
        )
        source_df = pd.read_csv(context.get_input_path("reader_csv"))
        source_df.email = source_df.email.str.lower()
        dest_df = pd.read_csv(reader_csv_path)
        assert source_df.equals(dest_df)


def test_valid_csv_with_valid_config(tmpdir):
    gear_dir = create_gear_dir(tmpdir)
    # Instantiate a gear context object
    with GearToolkitContext(gear_path=gear_dir, input_args=[]) as context:
        # create a configuration w/CAPs to test casting embedded in define_reader_csv
        config = create_gear_config(
            "Test.Email@email.com", "test-firstname", "test-lastname", 23
        )
        for k, v in config.items():
            context.config[k] = v

        # Create a reader csv that will be used to populate with one reader
        reader_csv_path = define_reader_csv(context)

        assert (
            reader_csv_path
            == gear_dir / "work" / context.get_input("reader_csv")["location"]["name"]
        )

        source_df = pd.read_csv(context.get_input_path("reader_csv"))
        # add a row to the source_df from the config
        source_df = source_df.append(
            {
                "email": config.get("reader_email"),
                "first_name": config.get("reader_firstname"),
                "last_name": config.get("reader_lastname"),
                "max_cases": config.get("max_cases"),
            },
            ignore_index=True,
        )
        source_df.email = source_df.email.str.lower()
        dest_df = pd.read_csv(reader_csv_path)
        assert source_df.equals(dest_df)


def test_valid_csv_with_duplicate_config(tmpdir):
    gear_dir = create_gear_dir(tmpdir)
    # Instantiate a gear context object
    with GearToolkitContext(gear_path=gear_dir, input_args=[]) as context:
        # create a configuration
        config = create_gear_config("thadbrown@flywheel.io", "Thad", "Brown", 11)
        for k, v in config.items():
            context.config[k] = v

        # Create a reader csv that will be used to populate with one reader
        reader_csv_path = define_reader_csv(context)

        assert (
            reader_csv_path
            == gear_dir / "work" / context.get_input("reader_csv")["location"]["name"]
        )

        source_df = pd.read_csv(context.get_input_path("reader_csv"))
        source_df.email = source_df.email.str.lower()
        # Update duplicate row with max_cases
        source_df.max_cases[2] = 11

        dest_df = pd.read_csv(reader_csv_path)
        assert source_df.equals(dest_df)


def test_invalid_reader_csv(caplog):
    with tempfile.TemporaryDirectory() as tmp_folder:
        gear_dir = create_gear_dir(tmp_folder)

        with GearToolkitContext(gear_path=gear_dir, input_args=[]) as context:
            create_invalid_csv(context)
            try:
                reader_csv_path = define_reader_csv(context)
            except InvalidInputError as e:
                exp_messages = [
                    'The csv-file "users-short.csv" did not have the '
                    'required columns("email", "first_name", "last_name", "max_cases")'
                    ".Proceeding without reader CSV."
                ]

                assert isinstance(e, InvalidInputError)
                assert (
                    e.message
                    == "Cannot proceed without a valid CSV"
                    + " file or valid specified reader!"
                )
                for i in range(len(caplog.records)):
                    assert caplog.records[i].message == exp_messages[i]


def test_valid_csv_with_invalid_config(caplog, tmpdir):
    gear_dir = create_gear_dir(tmpdir)

    with GearToolkitContext(gear_path=gear_dir, input_args=[]) as context:
        # create a configuration
        config = create_gear_config("test.email@email.com", None, "test-lastname", 23)
        for k, v in config.items():
            context.config[k] = v

        reader_csv_path = define_reader_csv(context)

        exp_messages = [
            "The specified reader is not configured correctly. "
            "Proceeding without specified reader "
            '("test.email@email.com", "None", "test-lastname").'
        ]

        for i in range(len(caplog.records)):
            assert caplog.records[i].message == exp_messages[i]

        assert (
            reader_csv_path
            == gear_dir / "work" / context.get_input("reader_csv")["location"]["name"]
        )
        source_df = pd.read_csv(context.get_input_path("reader_csv"))
        source_df.email = source_df.email.str.lower()
        dest_df = pd.read_csv(reader_csv_path)
        assert source_df.equals(dest_df)


def test_invalid_csv_with_valid_config(caplog, tmpdir):
    gear_dir = create_gear_dir(tmpdir)

    with GearToolkitContext(gear_path=gear_dir, input_args=[]) as context:
        # create a configuration
        config = create_gear_config(
            "test.email@email.com", "test-firstname", "test-lastname", 23
        )
        for k, v in config.items():
            context.config[k] = v

        # invalidate csv
        create_invalid_csv(context)
        reader_csv_path = define_reader_csv(context)

        exp_messages = [
            'The csv-file "users-short.csv" did not have the '
            'required columns("email", "first_name", "last_name", "max_cases").'
            "Proceeding without reader CSV."
        ]

        for i in range(len(caplog.records)):
            assert caplog.records[i].message == exp_messages[i]

        # Assert that these have the expected path
        assert reader_csv_path == context.work_dir / "temp.csv"

        # Load the created csv
        test_df = pd.read_csv(reader_csv_path)

        # Test its values with respects to the config above.
        assert [
            test_df.email[0],
            test_df.first_name[0],
            test_df.last_name[0],
            test_df.max_cases[0],
        ] == [
            config["reader_email"],
            config["reader_firstname"],
            config["reader_lastname"],
            config["max_cases"],
        ]
