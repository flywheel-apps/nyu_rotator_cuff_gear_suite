from pathlib import Path

import bson
import flywheel

from gears.assign_cases.utils.container_operations import define_created

DATA_ROOT = Path(__file__).parents[1] / "data"


def test_define_created():
    sess_id = bson.ObjectId()
    session = flywheel.Session(id=sess_id)

    created_container = define_created(session)

    assert created_container == {"container": "session", "id": sess_id, "new": True}
