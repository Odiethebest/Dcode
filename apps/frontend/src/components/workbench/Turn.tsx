import type { CitationPayload, QueryStreamEvent } from '@/api/types';
import { CitationChip } from '@/components/ui';
import { AnswerMarkdown } from '@/components/workbench/AnswerMarkdown';
import { Trace } from '@/components/workbench/Trace';
import { turnStatus, type Turn as TurnData } from '@/hooks/useThread';
import { citationKey, mergeCitations, unmatchedCitations } from '@/lib/citations';

type EventOf<K extends QueryStreamEvent['event']> = Extract<QueryStreamEvent, { event: K }>;

export interface TurnProps {
  turn: TurnData;
  activeCitationKey: string | null;
  onOpenCitation: (citation: CitationPayload) => void;
}

export function Turn({ turn, activeCitationKey, onOpenCitation }: TurnProps) {
  const status = turnStatus(turn);

  const finalAnswer = turn.events.find(
    (event): event is EventOf<'final_answer'> => event.event === 'final_answer'
  )?.data;
  const partial = turn.events
    .filter((event): event is EventOf<'partial_answer'> => event.event === 'partial_answer')
    .map((event) => event.data.delta)
    .join('');
  const errorData = turn.events.find(
    (event): event is EventOf<'error'> => event.event === 'error'
  )?.data;

  const answerText = finalAnswer?.answer ?? partial;
  const citations = mergeCitations(turn.events, finalAnswer);
  const toolCount = turn.events.filter((event) => event.event === 'tool_call').length;
  // Chips + verified state bind ONLY at settle — while streaming, refs render inert.
  const boundCitations = status === 'done' ? citations : [];
  const sources = status === 'done' ? unmatchedCitations(answerText, citations) : [];

  return (
    <section className="border-b border-line py-8 last:border-0">
      <div className="mb-5 flex gap-3">
        <span className="mt-1.5 flex-none font-mono text-[10px] uppercase tracking-[0.1em] text-ink-3">
          Asked
        </span>
        <h2 className="font-display text-2xl font-medium leading-snug tracking-tight text-ink">
          {turn.question}
        </h2>
      </div>

      <div className="pl-[3.25rem] max-[760px]:pl-0">
        <Trace
          events={turn.events}
          status={status}
          groundedness={finalAnswer?.groundedness ?? null}
          toolCount={toolCount}
        />

        {status === 'error' ? (
          <div className="rounded-md bg-bad-wash px-4 py-3 text-sm text-bad">
            <span className="font-mono text-xs">{errorData?.code ?? 'ERROR'}</span> —{' '}
            {errorData?.message ?? 'Something went wrong while answering.'}
          </div>
        ) : answerText ? (
          <AnswerMarkdown
            text={answerText}
            citations={boundCitations}
            activeKey={activeCitationKey}
            onOpenCitation={onOpenCitation}
          />
        ) : (
          <p className="text-sm text-ink-3">Thinking…</p>
        )}

        {sources.length > 0 && (
          <div className="mt-4">
            <div className="mb-2 font-mono text-[10px] uppercase tracking-[0.12em] text-ink-3">
              Sources
            </div>
            <div className="flex flex-wrap gap-2">
              {sources.map((citation) => (
                <CitationChip
                  key={citationKey(citation)}
                  verified={citation.verified}
                  active={activeCitationKey === citationKey(citation)}
                  onClick={() => onOpenCitation(citation)}
                >
                  {citation.file_path}:{citation.line}
                </CitationChip>
              ))}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
