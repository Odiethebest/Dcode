"""Worker settings — extends SharedSettings with pipeline-specific knobs."""

from dcode_shared.settings import SharedSettings


class WorkerSettings(SharedSettings):
    """Index worker configuration."""

    workdir_base: str = "/tmp/dcode-workdirs"
    queue_name: str = "dcode.index_jobs"
    # Guardrails against memory / embedding-token blowup on pathological repos.
    max_file_bytes: int = 1_000_000  # skip .py files larger than this (0 = no cap)
    max_chunk_chars: int = 20_000  # truncate chunk content beyond this (0 = no cap)


worker_settings = WorkerSettings()
