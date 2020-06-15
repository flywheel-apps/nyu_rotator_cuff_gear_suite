
class DuplicateJobError(Exception):
    """
    Exception raised for attempting to run a duplicate of an atomic gear.

    Args:
        message (str): explanation of the error
    """

    def __init__(self, message):
        Exception.__init__(self)
        self.message = message


def check_for_duplicate_execution(fw_client, gear_name):
    """
    Checks for the existence of a duplicate running gear.

    Args:
        fw_client (flywheel.Client): A flywheel client
        gear_name (str): The name of the running gear

    Raises:
        DuplicateJobError: If a duplicate job is found, raise this error with message
    """
    jobs = [
        job for job in fw_client.jobs.find(f'gear_info.name={gear_name}')
        if job.state in ['running', 'pending']
    ]
    if len(jobs) >= 2:
        raise DuplicateJobError(
            "You are attempting to run a duplicate of an atomic gear."
        )
