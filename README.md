# NYU/Siemens Rotator Cuff Tear Assessment Gear Suite

A suite of custom gears preparing an annotated dataset for training an AI model.  This AI model will be trained from

1. The presence and degree (None, partialLow, partialHigh, Full) of a tear on a rotator cuff tendon (infraspinatus, supraspinatus, or subscapularis).

2. If a Full Thickness Tear, the extent of retraction (minimal, humeral, glenoid).

3. If a Full Thickness Tear, two measurements pertaining to the extent of the tear in the ohifViewer that is a part of Flywheel.

This is accomplished by gears that assign readers, assign cases and gather assessed case data (from the ohifViewer) to provide a summary report for the management for the NYU/Siemens Rotator Cuff Tear Project.

This project is designed to assign 520 cases across 13 readers for assessment with the following distribution:

1. Each case goes to three distinct and randomly selected readers. (3 x 520 = 1560)

2. Each reader is contracted to assess 120 cases. (13 x 120 = 1560)

3. A reader may assess more if they have agreed to break a tie.

A reader has read-write access to a specific "reader project" within the "Readers" group.

Administrative permission for Master Projects, the Readers group, and all reader projects is required for valid execution of all gears. Permissions to the Readers group may be granted to administrators of the project. To ensure that each project administrator can review a readers projects, they should be added as an admin to the Readers Group's Projects Template.

## Objectives

In order to achieve the desired workflow, four separate gears are developed:

1. [**Assign-Readers**](./gears/assign_readers/)

    This gear creates, initializes, and modifies projects with permission for one reader each.  This is done either in bulk with a csv file or with an individual specified in the gear configuration.  All reader projects are created within the “Readers” group.

2. [**Assign-Cases**](./gears/assign_cases/)

    This gear distributes each case of a "Master Project" to three randomly selected distinct reader projects for assessment. Readers are selected without replacement. For specifics about the relationship between the number of cases in a master project and the number of available readers, please see the `assign-cases` [README](./gears/assign_cases/).

3. [**Gather-Cases**](./gears/gather_cases/)

    This gear gathers case assessment status and assessment data into the session of origin.

4. [**Assign-Single-Case**](./gears/assign_single_case/)

    This gear is used for the assignment or reassignment of a specific single case to a single reader.

The gears above keep track of case assignments and assignment status in the metadata associated with each respective Flywheel container.  These metadata are backed up within csv files that are the outputs of both the assign-cases and the gather-cases gears.  Should the metadata in the projects accidentally get corrupted, these csv files can be used to restore the state of the system.

**NOTE:** All gears must be run from within a "Master Project". Attempting to execute any gear from within a reader project will fail.

**NOTE:** No gear in this suite can be run concurrently with any other gear in this suite. This is done to ensure the integrity of the data and metadata at each step.

**NOTE:** Gears run by a user without administrative priviledges on all involved projects will fail.
