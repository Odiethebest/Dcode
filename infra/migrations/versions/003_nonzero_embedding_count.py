"""index_runs.chunks_with_nonzero_embedding — count what is retrievable.

`chunks_written` was `len(ctx.chunks)`, the worker's in-memory counter: what the
pipeline believed it wrote, not a measurement of what is in the table. This column
adds the number that actually carry a usable vector, and `chunks_written` starts
coming from the same query.

Why non-zero rather than non-NULL. `StubEmbeddingClient` writes all-zero vectors,
which are perfectly non-NULL, so a NULL-based count reports 100% healthy for a stub
index that retrieves nothing — a confident wrong record, which is worse than none.
Measure the quantity that matters instead of measuring a proxy and attaching a
caveat.

Why it belongs in a run record at all: the same argument as `skipped_files`. It
describes what did *not* happen. A chunk the dense path cannot reach cannot be
retrieved, so a recall miss may be an indexing gap rather than a retrieval failure
— and retrieval is the entire subject of the H1 dispute. It matters more than it
looks, because zero-vector rows sort *last* under pgvector (NaN distance, ordered
above every real value), so a partly-stubbed corpus never appears in a top-5 and is
completely invisible in the metrics. Counting is the only way to find it.

What it does not establish: that the embeddings are any *good*. A degenerate but
non-zero model would pass. It catches the one known degenerate producer, and it is
a measurement rather than a warning.

Purely additive: one nullable column on a table whose rows are never rewritten.
Existing rows keep NULL, which is the honest marker for "recorded before this was
measured" — and NULL is deliberately distinguishable from 0, which would mean
"measured, and nothing is retrievable".

Revision ID: 003_nonzero_embedding_count
Revises: 002_index_runs
Create Date: 2026-07-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "003_nonzero_embedding_count"
down_revision: str | None = "002_index_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "index_runs",
        sa.Column("chunks_with_nonzero_embedding", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("index_runs", "chunks_with_nonzero_embedding")
