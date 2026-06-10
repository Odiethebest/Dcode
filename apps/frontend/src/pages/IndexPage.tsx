/**
 * IndexPage — repo submission + index status display.
 * Skeleton placeholder. M2 wires:
 *   - POST /api/v1/repos via apiClient.submitRepo()
 *   - polling/SSE on GET /api/v1/repos/{id}/status (DESIGN.md §4.1)
 */
export default function IndexPage() {
  return (
    <section>
      <h1 className="text-2xl font-semibold mb-2">Index a repository</h1>
      <p className="text-stone-600 max-w-prose">
        Skeleton placeholder. M2 wires repository submission and live indexing-status
        streaming per DESIGN.md §2.1 and §4.1.
      </p>
    </section>
  );
}
