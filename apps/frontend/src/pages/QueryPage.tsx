import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react';

import { streamQuery } from '@/api/client';
import type {
  CitationPayload,
  FinalAnswerPayload,
  QueryStreamEvent,
} from '@/api/types';
import { RepoStatusBadge } from '@/components/RepoStatusBadge';
import { loadRecentRepos } from '@/lib/recentRepos';

const DEFAULT_QUERY = 'Where is `HTTPBasicAuth` defined?';

export default function QueryPage() {
  const recentRepos = useMemo(() => loadRecentRepos(), []);
  const [repoId, setRepoId] = useState(recentRepos[0]?.repoId ?? '');
  const [query, setQuery] = useState(DEFAULT_QUERY);
  const [events, setEvents] = useState<QueryStreamEvent[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  const finalAnswer = [...events]
    .reverse()
    .find((event): event is Extract<QueryStreamEvent, { event: 'final_answer' }> => event.event === 'final_answer')
    ?.data;
  const partialAnswer = [...events]
    .reverse()
    .find((event): event is Extract<QueryStreamEvent, { event: 'partial_answer' }> => event.event === 'partial_answer')
    ?.data.delta;
  const citations = mergeCitations(events, finalAnswer);

  return (
    <section className="mx-auto grid max-w-6xl gap-6 xl:grid-cols-[22rem_minmax(0,1fr)]">
      <aside className="space-y-6 rounded-lg border border-stone-200 bg-white p-5 shadow-sm">
        <div className="space-y-2">
          <h1 className="text-3xl font-semibold tracking-tight">Ask the agent</h1>
          <p className="text-sm leading-6 text-stone-600">
            Stream the agent run, inspect tool activity, and review grounded citations on
            the same screen.
          </p>
        </div>

        <form className="space-y-4" onSubmit={(event) => void handleSubmit(event, repoId, query, setEvents, setIsStreaming, setSubmitError, abortRef)}>
          <div className="space-y-2">
            <label htmlFor="repo-id" className="block text-sm font-medium text-stone-700">
              Repo ID
            </label>
            <input
              id="repo-id"
              value={repoId}
              onChange={(event) => setRepoId(event.target.value)}
              className="w-full rounded-md border border-stone-300 px-3 py-2 text-sm font-mono outline-none transition focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
              placeholder="repo UUID"
              required
            />
          </div>

          <div className="space-y-2">
            <label htmlFor="query" className="block text-sm font-medium text-stone-700">
              Query
            </label>
            <textarea
              id="query"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              rows={5}
              className="w-full rounded-md border border-stone-300 px-3 py-2 text-sm outline-none transition focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
              placeholder="Ask a code question"
              required
            />
          </div>

          <div className="flex flex-wrap gap-3">
            <button
              type="submit"
              disabled={isStreaming}
              className="inline-flex min-w-32 items-center justify-center rounded-md bg-stone-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-stone-700 disabled:cursor-not-allowed disabled:bg-stone-400"
            >
              {isStreaming ? 'Streaming…' : 'Run query'}
            </button>
            <button
              type="button"
              onClick={() => {
                abortRef.current?.abort();
                setIsStreaming(false);
              }}
              className="inline-flex min-w-32 items-center justify-center rounded-md border border-stone-300 px-4 py-2 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-50"
            >
              Stop
            </button>
          </div>
        </form>

        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-stone-900">Recent repos</h2>
            <span className="text-xs text-stone-500">{recentRepos.length}</span>
          </div>
          <div className="space-y-2">
            {recentRepos.length === 0 ? (
              <p className="text-sm text-stone-600">No indexed repo cached yet.</p>
            ) : (
              recentRepos.map((repo) => (
                <button
                  key={repo.repoId}
                  type="button"
                  onClick={() => setRepoId(repo.repoId)}
                  className="block w-full rounded-md border border-stone-200 px-3 py-3 text-left transition hover:border-sky-300 hover:bg-sky-50"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-stone-900">{repo.url}</p>
                      <p className="mt-1 truncate font-mono text-xs text-stone-500">{repo.repoId}</p>
                    </div>
                    <RepoStatusBadge value={toKnownRepoStatus(repo.status)} />
                  </div>
                </button>
              ))
            )}
          </div>
        </section>
      </aside>

      <div className="grid gap-6">
        <section className="rounded-lg border border-stone-200 bg-white p-5 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-lg font-semibold text-stone-900">Final answer</h2>
            {finalAnswer ? (
              <span className="rounded-md bg-stone-100 px-2 py-1 text-xs font-medium text-stone-700">
                groundedness {finalAnswer.groundedness.toFixed(2)}
              </span>
            ) : null}
          </div>

          <div className="mt-4 whitespace-pre-wrap rounded-md border border-stone-200 bg-stone-50 px-4 py-4 text-sm leading-6 text-stone-800">
            {finalAnswer?.answer ?? partialAnswer ?? 'No answer yet.'}
          </div>

          {submitError ? (
            <p className="mt-4 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
              {submitError}
            </p>
          ) : null}
        </section>

        <section className="rounded-lg border border-stone-200 bg-white p-5 shadow-sm">
          <h2 className="text-lg font-semibold text-stone-900">Citations</h2>
          <div className="mt-4 space-y-3">
            {citations.length === 0 ? (
              <p className="text-sm text-stone-600">No citations emitted yet.</p>
            ) : (
              citations.map((citation) => (
                <div key={citationKey(citation)} className="rounded-md border border-stone-200 bg-stone-50 px-4 py-3">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate font-mono text-sm text-stone-900">{citation.symbol}</p>
                      <p className="mt-1 text-xs text-stone-600">
                        {citation.file_path}:{citation.line}
                      </p>
                    </div>
                    <span
                      className={`inline-flex rounded-md px-2 py-1 text-xs font-medium ${
                        citation.verified
                          ? 'bg-emerald-100 text-emerald-800'
                          : 'bg-amber-100 text-amber-800'
                      }`}
                    >
                      {citation.verified ? 'verified' : 'unverified'}
                    </span>
                  </div>
                </div>
              ))
            )}
          </div>
        </section>

        <section className="rounded-lg border border-stone-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-lg font-semibold text-stone-900">Event stream</h2>
            <span className="text-xs text-stone-500">{events.length} events</span>
          </div>
          <div className="mt-4 space-y-3">
            {events.length === 0 ? (
              <p className="text-sm text-stone-600">No stream activity yet.</p>
            ) : (
              events.map((event, index) => (
                <div key={`${event.event}-${index}`} className="rounded-md border border-stone-200 px-4 py-3">
                  <EventRow event={event} />
                </div>
              ))
            )}
          </div>
        </section>
      </div>
    </section>
  );
}

function EventRow({ event }: { event: QueryStreamEvent }) {
  switch (event.event) {
    case 'thought':
      return (
        <div className="space-y-1">
          <p className="text-xs font-medium uppercase tracking-wide text-stone-500">thought</p>
          <p className="text-sm text-stone-800">
            step {event.data.step}: {event.data.content}
          </p>
        </div>
      );
    case 'tool_call':
      return (
        <div className="space-y-1">
          <p className="text-xs font-medium uppercase tracking-wide text-stone-500">tool_call</p>
          <p className="text-sm text-stone-800">
            step {event.data.step}: {event.data.tool}
          </p>
          <pre className="overflow-x-auto rounded bg-stone-50 p-2 text-xs text-stone-700">
            {JSON.stringify(event.data.args, null, 2)}
          </pre>
        </div>
      );
    case 'tool_result':
      return (
        <div className="space-y-1">
          <p className="text-xs font-medium uppercase tracking-wide text-stone-500">tool_result</p>
          <p className="text-sm text-stone-800">
            step {event.data.step}: {event.data.tool}
          </p>
          <p className="text-sm text-stone-600">{event.data.result_summary}</p>
        </div>
      );
    case 'citation':
      return (
        <div className="space-y-1">
          <p className="text-xs font-medium uppercase tracking-wide text-stone-500">citation</p>
          <p className="font-mono text-sm text-stone-800">{event.data.symbol}</p>
          <p className="text-sm text-stone-600">
            {event.data.file_path}:{event.data.line}
          </p>
        </div>
      );
    case 'partial_answer':
      return (
        <div className="space-y-1">
          <p className="text-xs font-medium uppercase tracking-wide text-stone-500">partial_answer</p>
          <p className="whitespace-pre-wrap text-sm text-stone-800">{event.data.delta}</p>
        </div>
      );
    case 'final_answer':
      return (
        <div className="space-y-1">
          <p className="text-xs font-medium uppercase tracking-wide text-stone-500">final_answer</p>
          <p className="whitespace-pre-wrap text-sm text-stone-800">{event.data.answer}</p>
        </div>
      );
    case 'error':
      return (
        <div className="space-y-1">
          <p className="text-xs font-medium uppercase tracking-wide text-stone-500">error</p>
          <p className="text-sm font-medium text-rose-700">{event.data.code}</p>
          <p className="text-sm text-rose-600">{event.data.message}</p>
        </div>
      );
  }
}

async function handleSubmit(
  event: FormEvent<HTMLFormElement>,
  repoId: string,
  query: string,
  setEvents: React.Dispatch<React.SetStateAction<QueryStreamEvent[]>>,
  setIsStreaming: React.Dispatch<React.SetStateAction<boolean>>,
  setSubmitError: React.Dispatch<React.SetStateAction<string | null>>,
  abortRef: React.MutableRefObject<AbortController | null>
) {
  event.preventDefault();
  abortRef.current?.abort();
  const controller = new AbortController();
  abortRef.current = controller;
  setEvents([]);
  setSubmitError(null);
  setIsStreaming(true);

  try {
    await streamQuery(
      {
        repo_id: repoId.trim(),
        query: query.trim(),
      },
      (streamEvent) => {
        setEvents((current) => [...current, streamEvent]);
        if (streamEvent.event === 'error') {
          setSubmitError(`${streamEvent.data.code}: ${streamEvent.data.message}`);
        }
      },
      controller.signal
    );
  } catch (error) {
    if (controller.signal.aborted) {
      return;
    }
    setSubmitError(error instanceof Error ? error.message : 'Unknown query error');
  } finally {
    if (abortRef.current === controller) {
      abortRef.current = null;
    }
    setIsStreaming(false);
  }
}

function mergeCitations(
  events: QueryStreamEvent[],
  finalAnswer: FinalAnswerPayload | undefined
): CitationPayload[] {
  const merged = new Map<string, CitationPayload>();

  for (const event of events) {
    if (event.event !== 'citation') {
      continue;
    }
    merged.set(citationKey(event.data), event.data);
  }

  for (const citation of finalAnswer?.citations ?? []) {
    merged.set(citationKey(citation), citation);
  }

  return [...merged.values()];
}

function citationKey(citation: CitationPayload): string {
  return `${citation.symbol}|${citation.file_path}|${citation.line}`;
}

function toKnownRepoStatus(status: string): 'queued' | 'cloning' | 'parsing' | 'embedding' | 'graphing' | 'ready' | 'failed' {
  switch (status) {
    case 'queued':
    case 'cloning':
    case 'parsing':
    case 'embedding':
    case 'graphing':
    case 'ready':
    case 'failed':
      return status;
    default:
      return 'queued';
  }
}
