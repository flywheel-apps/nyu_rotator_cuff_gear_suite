# assign-single-case

The `assign-single-case` gear is used for the assignment or reassignment of a single case to a single reader.  With a new assignment, the case data is copied to a reader project for a new assessment of that case.  In this scenario, the **case_coverage** is incremented to allow for the break of a tie.  For a reassignment, the reader’s current assessment is set to incomplete and the user is notified for the reason (e. g. they have a minority classification).

The `assign-single-case` gear distributes a single case from a populated "Master Project" to a reader project given the following constraints: Each reader will be limited to a maximum number of cases (**max_cases**) as defined previously by `assign-readers`. On assignment, each case along with its acquisitions, files, and metadata is copied to a reader's project for assessment by that reader.

Each reader is considered available if they are assigned less than their maximum number of cases (**max_cases**).

On completion of this Gear any remaining coordination data is recorded in the associated Master Project and reader projects.

## Prerequisite

Successfully executing the `assign-readers` gear is a prerequisite for this gear to operate successfully.  The `assign-readers` gear creates, initializes, and modifies the reader projects that will receive the exported sessions.

## Website

[https://github.com/flywheel-apps/nyu_rotator_cuff_gear_suite](https://github.com/flywheel-apps/nyu_rotator_cuff_gear_suite)

## Usage Notes

The `assign-single-case` gear assigns or modifies the assignment of a single case. A new assignment is constrained by the availability of the specified reader (i.e. the readers number of assignments is less than their maximum number of cases). On execution, the gear distributes the specified case to a specified reader.

NOTE: This gear assumes that you are running it from within the "Master Project".  Attempting to execute this gear from within a reader project will fail.

### Gear Configuration

* **reader_email** (required): The email of the reader to assign the specific case.
* **assignment_reason** (required): A selected reason for the new assignment or reassignment. (Default *Assign to Resolve Tie*).  
  * **Assign to Resolve Tie**: Assign this case to the specified reader. Increases **case_coverage**, if require.
  * **Individual Assignment**: Assign this case to the specified reader. The gear will fail if constrained by **case_coverage**.
  * **Change Tear Classification**: Removes **Completed** status from case and allows reader to make changes to tear type and measurements.
  * **Change Measurement**: Removes **Completed** status from case and allows reader to make changes to measurements only.

### Expected Output

On successful execution of the `assign-single-case` gear, the following output will be produced.  The following csv (comma-separated-values) files are intended as record-keeping for the actions performed and the state of all assessments. They are not intended to be edited or to be easily human-readable reports.

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
