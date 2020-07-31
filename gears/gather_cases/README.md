# gather-cases

The `gather-cases` gear collects all assigned case status data from the reader projects. Data from assessed cases is collated into the origin case of a "Master Project",  into a "Master Project" itself, and reported on in tabular output described below.

Each case is considered "completed" by a reader if for each tendon

1. It is specified as "No tear", "Low grade partial thickness tear", or "High grade partial thickness tear" and has no measurements
2. It is specified as a "Full thickness tear" and has two appropriately labeled measurements.

NOTE: Should there be an error introduced in any case assessment, the output will mark this assessment as incomplete (`completed=False`) and append an error message in the `additionalNotes` column that reads:

```ERROR: An error occurred in the case assessment. Please examine and correct.```

## Prerequisite

Successfully executing the `assign-readers` gear is a prerequisite for this gear to operate successfully.  The `assign-readers` gear creates, initializes, and modifies the reader projects that will receive the exported sessions. Furthermore, the `assign-cases` gear is a prerequisite for attaining assessment on assigned cases. If the cases are not assigned, no assessment data will be available. Should assessement yet to done for the assigned cases, the output indicates that these cases are incomplete.

## Website

[https://github.com/flywheel-apps/nyu_rotator_cuff_gear_suite](https://github.com/flywheel-apps/nyu_rotator_cuff_gear_suite)

## Usage Notes

The `gather-cases` gear is executed without inputs and configuration parameters.

NOTE: This gear assumes that you are running it from within a "Master Project".  Attempting to execute this gear from within a reader project will fail.

### Expected Output

On successful execution of the `gather-cases` gear, the following csv (comma-separated-value) files are produces as output.

* **master_project_summary_data.csv**: A csv file that indicates the readers assigned to each case and the state of completion for that case. The fields of the csv are as follows:

  * `id`: the id of the session (case) assessed.
  * `label`: The label of the session in Flywheel.
  * `case_coverage`: The desired coverage for this cases.
  * `unassigned`: The number of unassigned cases for each case (up to **case_coverage**).
  * `assigned`: The number of assignments for each case (up to **case_coverage**).
  * `diagnosed`: The number of diagnosed assignments for each case (up to **case_coverage**).
  * `measured`: The number of measured assignments for each case (up to **case_coverage**).
  * `completed`: The number of completed assignments for each case (up to **case_coverage**).

* **case_assignment_status_export.csv**: A csv file containing the assessment status of each case assigned to readers.  The fields of the csv are as follows:
  * **id**: the id of the session (case) assessed.
  * **subject**: The label of the subject.
  * **session**: The label of the session.
  * **reader_id**: The email of the reader assigned this case.
  * **completed**: The completion status of each assigned case
  * For each tendon (infraspinatus, supraspinatus, subscapularis)
    * Tear classification
    * Difficulty
    * Retraction
    * For each measurement (total of two, if full-thickness tear):
      * Length: The length of the measurement in mm
      * Voxel_Start: start point of measurement in ijk-space
      * Voxel_End: end point of measurement in ijk-space
      * RAS_Start: start point of measurement in RAS-space
      * RAS_End: end point of measurement in RAS-space
      * ijk_to_RAS: Matrix converting ijk to RAS coordinates (4x4)
  * AdditionalNotes: Any notes left by the reader.
