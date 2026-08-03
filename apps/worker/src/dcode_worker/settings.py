"""Worker settings — extends SharedSettings with pipeline-specific knobs."""

from dcode_shared.settings import SharedSettings


class WorkerSettings(SharedSettings):
    """Index worker configuration."""

    workdir_base: str = "/tmp/dcode-workdirs"
    queue_name: str = "dcode.index_jobs"
    # Guardrails against memory / embedding-token blowup on pathological repos.
    max_file_bytes: int = 1_000_000  # skip .py files larger than this (0 = no cap)
    max_chunk_chars: int = 20_000  # truncate chunk content beyond this (0 = no cap)

    # Cloned workdirs were never removed, for any repository, ever — disk grew
    # monotonically with the number of distinct repos anyone ever submitted. On
    # a fixed cloud volume that is a slow outage.
    #
    # This is a cap, not a TTL, and it is OFF by default because eviction is not
    # free: the agent's read_file / grep / list_directory tools read that tree at
    # query time, so pruning a `ready` repository's workdir degrades its answers
    # until it is re-indexed. Search and the call graph are unaffected — they
    # read Postgres. A count is the honest knob: an operator can pick a number
    # that fits the volume and know exactly what it costs.
    #
    # 0 keeps the previous behaviour, so no existing deployment changes.
    workdir_max_repos: int = 0


worker_settings = WorkerSettings()
