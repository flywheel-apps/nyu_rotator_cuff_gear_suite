# assign-readers

This gear assigns readers to a new Flywheel project with each reader as the sole user of that project. Should that reader project already exist, the maximum cases may be changed.

Successful execution of this gear is a prerequisite for assigning cases to individual readers (`assign-cases` gear).

Executing the `assign-readers` gear ensures that each reader specified

* is a Flywheel user
* has *read-write* permissions to the "Readers" group.
* has a reader-project created in the "Readers" group.
* has **max_cases** set according to the reader's entry. If the reader has an existing **max_cases** setting, this is resolved by:
  * If the current **max_cases** value is less than the proposed **max_cases**, update to the proposed **max_cases** value
  * If the current **max_cases** is more than the proposed **max_cases**, update **max_cases** to the greater of the current number of cases assigned and the proposed **max_cases**

## Website

[https://github.com/flywheel-apps/nyu_rotator_cuff_gear_suite](https://github.com/flywheel-apps/nyu_rotator_cuff_gear_suite)

## Usage Notes

The "Assign Readers to a Project" gear is executed by ensuring the following inputs and configuration parameters are provided.

For successful execution of the gear one of two optional methods must be used:

1. Provide a comma-separated-value (csv) file, **reader_csv** with the required fields.
2. Provide a reader's email address (**reader_email**), first name (**reader_firstname**), last name (**reader_lastname**), and verify the maximum number of cases they assess (**max_cases** defaults to 30).

If both (1) and (2) are provided, **max_cases** provided will take precedence for the indicated reader rather than an entry in the **reader_csv**.

If neither (1) or (2) are provided, if the email is malformed, or if the csv does not have the required fields then the gear will fail.

### Inputs

* **reader_csv** (optional): A csv file containing email, first_name, last_name, and max_cases of each reader.

### Gear Configuration

* **reader_email** (optional): The email of the reader being assigned to a project or updating that project.
* **reader_firstname** (optional): The first name of the reader being assigned to a project or updating that project.
* **reader_lastname** (optional): The last name of the reader being assigned to a project or updating that project.
* **max_cases** (required): The maximum number of cases the reader will assess. This value takes precedence over an entry in the csv file. (Default *30*).
