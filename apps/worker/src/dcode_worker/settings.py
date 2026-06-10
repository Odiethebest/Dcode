"""Worker settings — extends SharedSettings with pipeline-specific knobs."""

from dcode_shared.settings import SharedSettings


class WorkerSettings(SharedSettings):
    """Index worker configuration."""

    workdir_base: str = "/tmp/dcode-workdirs"
    queue_name: str = "dcode.index_jobs"


worker_settings = WorkerSettings()
