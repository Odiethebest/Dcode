"""Pipeline stage: shallow-clone the target Git repository.

Implements DESIGN.md §2.1 'Clone' stage. Real implementation uses
`git clone --depth=1 <url> <workdir>` into the configured WORKDIR_BASE.
"""

from dcode_worker.context import PipelineContext


async def run(ctx: PipelineContext) -> PipelineContext:
    # TODO(M1): subprocess git clone --depth=1 ctx.repo_url; set ctx.workdir
    raise NotImplementedError("clone stage — implement per DESIGN.md §2.1 at M1")
