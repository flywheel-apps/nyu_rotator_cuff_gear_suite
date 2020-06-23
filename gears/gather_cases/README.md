# gather-cases

The `gather-cases` gear collects all assigned case status data from the reader projects. Data from assessed cases is collated into the origin case of a "Master Project",  into a "Master Project" itself, and reported on in tabular output described below.

Each case is considered "completed" by a reader if for each tendon

1. It is specified as "No tear", "Low grade partial thickness tear", or "High grade partial thickness tear" and has no measurements
2. It is specified as a "Full thickness tear" and has two appropriately labeled measurements.

## Prerequisite

Successfully executing the `assign-readers` gear is a prerequisite for this gear to operate successfully.  The `assign-readers` gear creates, initializes, and modifies the reader projects that will receive the exported sessions.

## Website

[https://github.com/flywheel-apps/nyu_rotator_cuff_gear_suite](https://github.com/flywheel-apps/nyu_rotator_cuff_gear_suite)

## Usage Notes

The `gather-cases` gear is executed without inputs and configuration parameters.

NOTE: This gear assumes that you are running it from within a "Master Project".  Attempting to execute this gear from within a reader project will fail.

### Expected Output

On successful execution of the `gather-cases` gear, the following csv (comma-separated-value) file is produces as output.

* **master_project_summary_data.csv**: A csv file that indicates the readers assigned to each case and the state of completion for that case. The fields of the csv are as follows:

  * `id`: the id of the session (case) assessed.
  * `label`: The label of the session in Flywheel.
  * `case_coverage`: The desired coverage for this cases.
  * `unassigned`: The number of unassigned cases for each case (up to **case_coverage**).
  * `assigned`: The number of assignments for each case (up to **case_coverage**).
  * `diagnosed`: The number of diagnosed assignments for each case (up to **case_coverage**)
  * `measured`: The number of measured assignments for each case (up to **case_coverage**).
  * `completed`: The number of completed assignments for each case (up to **case_coverage**).
