import flywheel

OHIF_VIEWER = {
    "read": {
        "mike_shs_pct@gmail_com": {
            "date": "2020-09-18T18:46:36.693Z",
            "notes": {
                "infraspinatusDifficulty": "none",
                "infraspinatusTear": "none",
                "subscapularisDifficulty": "none",
                "subscapularisTear": "none",
                "supraspinatusDifficulty": "none",
                "supraspinatusTear": "none",
            },
        }
    }
}


def prime_all_sessions_in_project(fw_client, project_id):
    project = fw_client.get(project_id).reload()
    for session in project.sessions():
        session = session.reload()
        info = session.info
        session.delete_info("ohifViewer")
        info["ohifViewer"] = OHIF_VIEWER
        session.update_info(info)


if __name__ == "__main__":
    fw_client = flywheel.Client("nyu.dev.flywheel.io:AykoM96O2UpbBaSb3p")
    for project_id in ["5f08e7e5fdf2ac0066a5ba79", "5f08c415fdf2ac005ea5b91b"]:
        prime_all_sessions_in_project(fw_client, project_id)
