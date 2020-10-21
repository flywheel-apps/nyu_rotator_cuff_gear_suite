# assign-batch-cases

The `assign-batch-cases` gear is used to assign cases to readers using the rows of `csv` file for each specific "assignment". Each case and reader must exist for the assignment to be successful. Furthermore, each reader must be available for that assignment (number of assignments less than **max_cases**) and each case must me assigned to less than **case_coverage** readers.

The **batch_csv** file, used as an input, must have `session_id`, `session_label`, and `reader_email` as columns. The sessions referenced may come from any "Master Project" and must not come from a "Reader Project". On assignment, each case along with its acquisitions, files, and metadata is copied to a reader's project for assessment by that reader.

On completion of this Gear any remaining coordination data is recorded in the associated Master Project and reader projects.

## Prerequisite

Successfully executing the `assign-readers` gear is a prerequisite for this gear to operate successfully.  The `assign-readers` gear creates, initializes, and modifies the reader projects that will receive the exported sessions.

## Website

[https://github.com/flywheel-apps/nyu_rotator_cuff_gear_suite](https://github.com/flywheel-apps/nyu_rotator_cuff_gear_suite)

## Usage Notes

The `assign-batch-cases` gear assigns multiple cases as specified in a user-supplied `csv` file. Each assignment is validated by the availability of the specified reader (i.e. the readers number of assignments is less than their maximum number of cases). On execution, the gear distributes each case to the readers specified in the csv. 

### Requirements

The **batch_csv** file, used as an input, must have `session_id`, `session_label`, and `reader_email` as columns.

* The **session_id** must be a valid Flywheel session in a "Master Project". 
* The **reader_email** must be a valid Flywheel user and have an existing reader project


NOTE: This gear assumes that you are running it from within a "Master Project".  Attempting to execute this gear from within a reader project or at the session level will fail.

### Gear Configuration

* **case_coverage** (required): The number of readers each case will be assigned to.  (Default *3*).

### Expected Output

On successful execution of the `assign-batch-cases` gear, the following output will be produced.  The following csv (comma-separated-values) files are intended as record-keeping for the actions performed and the state of all assessments. They are not intended to be edited or to be easily human-readable reports.

On full or partial failure over all assignments in **batch_csv**, a **batch_results.csv** file will be created reporting on reasons for the failures.

* **batch_results.csv**: A csv file that reports on the success or failure of each attempted assignment specified in the original **batch_csv**. On failure, a `message` is given reporting on the reason for failure. Two additional fields are appended to those of **batch_csv**::

  * `passed`: The `True`/`False` value indicating success or failure of a particular assignment
  * `message`: If `passed=False` a message reporting on the cause of failure.
  
* **master_project_case_data.csv**: A csv file that indicates the readers assigned to each case and the state of completion for that case. The fields of the csv are as follows:

  * `id`: the id of the session (case) assessed.
  * `label`: The label of the session in Flywheel.
  * `assignments`: A list of `json` data elements indicating who the case was assigned to.
  * `assigned_count`: The number of assignments for each case (up to **case_coverage**).
  * `case_coverage`: The desired coverage for this cases.  This may change if there is a tie in the assessment across readers.

* **reader_project_case_data.csv**: A csv file that indicates the cases assigned to each reader. This includes the maximum cases they will review (**max_cases**) and the number of current assignments (**num_assignments**).  The fields of the CSV are as follows:

  * `id`: The Flywheel id of the reader project.
  * `label`: The label of the reader project.
  * `reader_id`: The email of the reader assigned to the project.
  * `assignments`: A list of `json` data elements describing the source of each assignment.
  * `max_cases`: The maximum number of cases a reader will assess.  This can change on the request of the reader.
  * `num_assignments`: The current number of cases assigned to this reader.

* **exported_data.csv**: A csv detailing all of the case data that was exported during the execution of the `assign-cases` gear. The fields of the csv are as follows:

  * `container`: The type of Flywheel container exported (e.g. session, acquisition, ...)
  * `name`: The name of the container exported
  * `status`: The status of "created" if successful
  * `origin_path`: The resolver path of the source data
  * `export_path`: The resolver path of the destination data
  * `archive_path`: The resolver path of archived data (not used here)
