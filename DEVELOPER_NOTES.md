# assign cases

Here are some particular notes related to development and maintenance of the `assign-readers`, `assign-cases`, and `gather-case-data` gears.

Collectively these gears:

* find/create users, assign them to the "Readers" group, create projects with a reader being the sole user of that project, copy the NYU ohif configuration (`ohif_config.json`) from the Master Project to the readers project (`assign-readers`)
* assign a session to a reader (user) by copying/exporting the contents of that session (subject/session/acquisitions/files) to the reader's project (`assign-cases`).
* Set up the meta-data structures on the source project, source session, and the reader projects to effectively manage the flow of data created by the assessment process (`assign-readers`, `assign-cases`, `gather-case-data`).
* Maintain the metadata structures as more cases are gathered into the Master Project, new readers are available to assess those cases, and after the assessments are performed (`assign-readers`, `assign-cases`, `gather-case-data`).
* Metadata is backed up in the form of CSV files reflecting those metadata.
  * `assign-cases` creates:
    * "master_project_case_data.csv" which backs up master project session metadata
    * "reader_project_case_data.csv" which backs up reader project metadata
  * `gather-case-data` creates
    * "master_project_summary_data.csv" which backs up master project metadata

The metadata structures are as follows:

For the Master Project:

```json
{
    'project_features': {
        'case_coverage': 3,
        'case_states': [
            {
                'id': '5e5975430cc73f4694c82204',
                'label': '600063595040',
                'case_coverage': 3,
                'unassigned': 0,
                'assigned': 3,
                'diagnosed': 0,
                'measured': 0,
                'completed': 0
            },
            ...
        ]
    }
}
```

This lists the status of each session with respects to unassigned, assigned, ..., completed.

For sessions in the Master Project:

```json
'session_features': {
    'case_coverage': 3,
    'assignments': [
        {
            'project_id': '5ed00f27dd4e560524c2cc51',
            'reader_id': 'gsfr@flywheel.io',
            'session_id': '5ed00f46dd4e560528c2cc5f',
            'status': 'Assigned'
        },
        ...
        {
            'project_id': '5ed03ca5dd4e56054bc2cc52',
            'read': {
                'joshuajacobs@flywheel_io': {
                    'date': '2020-05-29T17: 08: 46.267Z',
                        'notes': {
                            'supraspinatusTear': 'highPartial',
                            'supraspinatusDifficulty': 'plus',
                            'infraspinatusTear': 'none',
                            'subscapularisTear': 'none',
                            'subscapularisDifficulty': 'none',
                            'infraspinatusDifficulty': 'none'
                        }
                    }
            }
            'reader_id': 'gsfr@flywheel.io',
            'session_id': '5ed03f1cdd4e560542c2cd84',
            'status': 'Completed'
        },
            ...
        {
            'project_id': '5ed03ca6dd4e56054bc2cc56',
            'read': {
                'joshuajacobs@flywheel_io': {
                    'date': '2020-05-29T17: 38: 47.042Z',
                    'notes': {
                        'supraspinatusTear': 'full',
                        'supraspinatusDifficulty': 'none',
                        'infraspinatusTear': 'none',
                        'subscapularisTear': 'none',
                        'subscapularisDifficulty': 'none',
                        'infraspinatusDifficulty': 'none'
                    }
                }
            },
            'reader_id': 'thadbrown@flywheel.io',
            'session_id': '5ed03f19dd4e56054bc2ce2e',
            'status': 'Completed',
            'measurements': {
                'Length': [
                    {
                        'visible': True,
                    },
                    ...
                ]
            }
        }

    ],
  'assigned_count': 3
}
```

This indicates the status of each session and where it is assigned to. Note that "Completed" sessions have additional fields "read" and "measured".

For the reader's project:

```json
{
    'project_features': {
        'assignments': [
            {
                'source_session': '5e5975430cc73f4694c82204',
                'dest_session': '5ed00f46dd4e560528c2cc5f'
            },
            ...
        ],
        'max_cases': 5
    }
}
```

This records the assignments for each reader and the maximum number of assigments (**max_cases**) that they will assess.
