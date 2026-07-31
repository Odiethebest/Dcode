"""index_runs — append-only executor records for each indexing pass.

Adds `index_runs` plus a mutable pointer `repos.current_index_run_id`.

The split is the point. `index_runs` rows are facts about something that already
happened and must never change; the pointer says which of them produced what is
in the tables right now, and must change when the contents do. `repos.commit_sha`
has only the second half, which is why nothing can currently establish that the
index a query ran against is the one a given `repos` row describes.

Immutability is enforced by a trigger, not by discipline in the ORM layer. An
append-only table whose append-only-ness lives in a code review is a convention,
and conventions are what this repository keeps being overtaken by.

Purely additive: one new table, one new nullable column. No existing row is
read or rewritten, and existing repos keep `current_index_run_id = NULL` —
deliberately, as the honest marker for "indexed before this existed". Backfilling
would produce rows shaped exactly like executor records but sourced from mutable
local state.

Revision ID: 002_index_runs
Revises: 001_initial_schema
Create Date: 2026-07-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "002_index_runs"
down_revision: str | None = "001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# RAISE, not a silent no-op: a caller that thinks it updated provenance and did
# not is worse off than one that crashed. TG_OP is included so the error says
# which operation was attempted.
_IMMUTABLE_FN = """
CREATE OR REPLACE FUNCTION index_runs_reject_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION
        'index_runs is append-only: % on row % is not permitted', TG_OP, OLD.id
        USING HINT =
            'An index run records something that already happened. Insert a new row.';
END;
$$ LANGUAGE plpgsql;
"""

_IMMUTABLE_TRIGGER = """
CREATE TRIGGER index_runs_immutable
    BEFORE UPDATE OR DELETE ON index_runs
    FOR EACH ROW EXECUTE FUNCTION index_runs_reject_mutation();
"""


def upgrade() -> None:
    op.create_table(
        "index_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        # RESTRICT rather than CASCADE. Nothing deletes a repo today; if that
        # changes, this fails loudly instead of quietly destroying provenance.
        sa.Column(
            "repo_id",
            UUID(as_uuid=True),
            sa.ForeignKey("repos.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("corpus_commit_sha", sa.Text()),
        sa.Column("embedding_model_loaded_at_start", sa.Text()),
        sa.Column("embedding_model_loaded_at_end", sa.Text()),
        sa.Column("embedding_model_configured", sa.Text()),
        sa.Column("embedding_dim", sa.Integer()),
        sa.Column("worker_git_head", sa.Text()),
        sa.Column("chunks_written", sa.Integer()),
        sa.Column("symbols_written", sa.Integer()),
        sa.Column("edges_written", sa.Integer()),
        sa.Column("skipped_files", JSONB(), nullable=False, server_default="[]"),
        sa.Column("failure_reason", sa.Text()),
    )
    op.create_index("ix_index_runs_repo_id", "index_runs", ["repo_id"])

    op.execute(_IMMUTABLE_FN)
    op.execute(_IMMUTABLE_TRIGGER)

    op.add_column("repos", sa.Column("current_index_run_id", UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_repos_current_index_run",
        "repos",
        "index_runs",
        ["current_index_run_id"],
        ["id"],
    )


def downgrade() -> None:
    # Order matters: the pointer's FK has to go before the table it points at,
    # and the trigger has to go before the table it guards — DROP TABLE would
    # otherwise be blocked by nothing, but the function would be orphaned.
    op.drop_constraint("fk_repos_current_index_run", "repos", type_="foreignkey")
    op.drop_column("repos", "current_index_run_id")
    op.execute("DROP TRIGGER IF EXISTS index_runs_immutable ON index_runs")
    op.execute("DROP FUNCTION IF EXISTS index_runs_reject_mutation()")
    op.drop_index("ix_index_runs_repo_id", table_name="index_runs")
    op.drop_table("index_runs")
