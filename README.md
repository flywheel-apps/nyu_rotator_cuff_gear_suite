# <s>NYU/Siemens Rotator Cuff Tear Assessment</s> "Blind Reader Study" Gear Suite

A suite of custom gears preparing an annotated dataset for the training of an AI model.  This AI model will be trained from

1. The key/value pairs of a completed reader form.

2. The list-of-points fields from the required measurements

This is accomplished by gears that assign readers, assign cases and gather assessed case data (from the ohifViewer) to provide a summary report for the management for the Blind Reader Study.

This project is designed to assign any number of cases across any number of readers for assessment with the following distribution:

1. Each case goes to a distinct number of randomly selected readers (`case_coverage` default 3).

2. Each reader is contracted to assess a specific number of cases (`max_cases`, set with `assign-readers`)

3. A reader may assess more if they have agreed to break a tie (necessitating a change to both `max_cases` and `case_coverage`).

A reader is the only user with read-write access to a specific "reader project" within the "Readers" group.

Administrative permission for Master Projects, the Readers group, and all reader projects is required for valid execution of all gears. Permissions to the Readers group may be granted to administrators of the project. To ensure that each project administrator can review a readers projects, they should be added as an admin to the Readers Group's Projects Template.

## Objectives

In order to achieve the desired workflow, five separate gears are developed:

1. [**Assign-Readers**](./gears/assign_readers/)

    This gear creates, initializes, and modifies projects with permission for one reader each.  This is done either in bulk with a csv file or with an individual specified in the gear configuration.  All reader projects are created within the “Readers” group.

2. [**Assign-Cases**](./gears/assign_cases/)

    This gear distributes each case of a "Master Project" to three randomly selected distinct reader projects for assessment. Readers are selected without replacement. For specifics about the relationship between the number of cases in a master project and the number of available readers, please see the `assign-cases` [README](./gears/assign_cases/).

3. [**Assign-Batch-Cases**](./gears/assign_batch_cases)

    This gear distributes cases in a provided csv to the assigned readers.  The max number of cases per reader (**max_cases**) and the coverage that each case is restricted to (**case_coverage**) is enforced.
  
4. [**Gather-Cases**](./gears/gather_cases/)

    This gear gathers case assessment status and assessment data into the session of origin.

5. [**Assign-Single-Case**](./gears/assign_single_case/)

    This gear is used for the assignment or reassignment of a specific single case to a single reader.

The gears above keep track of case assignments and assignment status in the metadata associated with each respective Flywheel container.  These metadata are backed up within csv files that are the outputs of both the assign-cases and the gather-cases gears.  Should the metadata in the projects accidentally get corrupted, these csv files can be used to restore the state of the system.

**NOTE:** All gears must be run from within a "Master Project". Attempting to execute any gear from within a reader project will fail. Furthermore, attempting to reference different "Master Project's" cases from within a particular "Master Project's" gear run will result in failure.

**NOTE:** No gear in this suite can be run concurrently with any other gear in this suite. This is done to ensure the integrity of the data and metadata at each step.

**NOTE:** Gears run by a user without administrative priviledges on all involved projects will fail.

## **TODOs:**

* Eliminate embedded `ohif_config.json` files from ever making into a reader project. ALWAYS insist that an `ohif_config.json` file exists in the Master Project or FAIL gears!!!
* Combine the functionality of `assign-batch-cases`, `assign-cases`, and `assign-single-case`.