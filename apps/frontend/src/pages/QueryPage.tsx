/**
 * QueryPage — chat interface streaming agent SSE.
 * Skeleton placeholder. M2 wires:
 *   - POST /api/v1/query SSE consumer via apiClient.streamQuery()
 *   - 7-event renderer (thought / tool_call / tool_result / citation / partial_answer / final_answer / error)
 *     per DESIGN.md §4.3
 */
export default function QueryPage() {
  return (
    <section>
      <h1 className="text-2xl font-semibold mb-2">Ask the agent</h1>
      <p className="text-stone-600 max-w-prose">
        Skeleton placeholder. M2 wires the SSE query stream and the citation-rendering
        panel per DESIGN.md §4.3.
      </p>
    </section>
  );
}
