# assign-cases

The `assign-cases` gear distributes cases from a populated "Master Project" to reader projects given the following constraints. Each case is assessed by a preset number of readers (**case_coverage**). Likewise, each reader elects to have a maximum number of cases (**max_cases**), to assess for rotator cuff tears. On assignment, each case--along with its acquisitions, files, and metadata--is copied to a reader's project for assessment by that reader.

The assignment of each case to a **case_coverage** number of distinct readers is done by random sampling of available readers without replacement. Each reader is considered available if they are assigned less than their maximum number of cases (**max_cases**). Furthermore, readers with the least number of assignments are preferred for selection. This results in cases being distributed to readers as evenly as possible within the above constraints. This strategy comes with the consequence of the following constraints for the complete assignment of all cases:

1. Single Master Project with Single Distribution.

    All cases assigned to all readers from a single master project in a single distribution.

    **total_number_of_cases** * **case_coverage** <= **number_of_readers** * **max_cases**.

2. Single Master Project with Multiple Distributions.

    The **max_cases** for each reader is incrementally updated to allow for multiple distributions from a single master project.  The change in **max_cases** (**∆ max_cases**) times number of readers must be divisible by **case_coverage**

    **number_of_readers** * **∆ max_cases** % **case_coverage** = 0

3. Multiple Masters Projects with Multiple Distributions.

    Multiple Master Projects with specific number of cases (**batch_size**) each can be completely distributed over all readers if each **batch_size** is divisible by the number of readers.

    **batch_size** % **number_of_readers** = 0

All of these assume that **max_cases** is defined and incremented consistently across all readers for usage of the `assign-cases` gear. If **max_cases** differs across readers, `assign-cases` may not completely distribute the cases of a particular Master Project. For (2) and (3), above, the end-state of the system must be constrained by the condition in (1) for complete distribution of all cases from all Master Projects.

Depending on the number of cases to assign to readers, the execution of this gear may take hours.  However, once a case is assigned, present and indexed in any reader project it is available to be assessed. On completion of this gear any remaining coordination data is recorded in the associated Master Project and reader projects.

## Prerequisite

Successfully executing the `assign-readers` gear is a prerequisite for this gear to operate successfully.  The `assign-readers` gear creates, initializes, and modifies the reader projects that will receive the exported sessions.

## Website

[https://github.com/flywheel-apps/nyu_rotator_cuff_gear_suite](https://github.com/flywheel-apps/nyu_rotator_cuff_gear_suite)

## Usage Notes

The `assign-cases` gear distributes cases present in a "Master Project" to the available readers. Available readers are those readers with less than **max_cases** number of cases assigned.

The `assign-cases` gear is executed with the following configuration parameters. Successfull execution ensures outputs described below.

NOTE: This gear assumes that you are running it from within a "Master Project".  Attempting to execute this gear from within a reader project will fail.

NOTE: Additional execution without first updating the number of cases and/or the number of readers will result in no actions performed.

NOTE: This gear distributes the `ohif_config.json` file to the master project, should it not yet exist. The `ohif_config.json` file is necessary to render and validate the assessment of each case.

### Gear Configuration

* **case_coverage** (required): The number of readers each case will be assigned to.  (Default *3*).

### Expected Output

On successful execution of the `assign-readers` gear, the following output will be produced.  The following csv (comma-separated-values) files are intended as record-keeping for the actions performed and the state of all assessments. They are not intended to be edited or to be easily human-readable reports.

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
