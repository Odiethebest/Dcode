import { useEffect, useMemo, useState } from 'react';

import {
  demoCases,
  h1Report,
  suiteSummary,
  type BaselineName,
  type Taxonomy,
} from '@/demo/evalSnapshot';

const BASELINE_ORDER: BaselineName[] = ['B2', 'B3', 'B4'];
const TAXONOMY_ORDER: Taxonomy[] = ['L2', 'L3'];

export default function ComparePage() {
  const [taxonomy, setTaxonomy] = useState<Taxonomy>('L2');
  const visibleCases = useMemo(
    () => demoCases.filter((item) => item.taxonomy === taxonomy),
    [taxonomy]
  );
  const [selectedQuestionId, setSelectedQuestionId] = useState(visibleCases[0]?.questionId ?? '');

  useEffect(() => {
    if (!visibleCases.some((item) => item.questionId === selectedQuestionId)) {
      setSelectedQuestionId(visibleCases[0]?.questionId ?? '');
    }
  }, [selectedQuestionId, visibleCases]);

  const selectedCase =
    visibleCases.find((item) => item.questionId === selectedQuestionId) ?? visibleCases[0];

  return (
    <section className="mx-auto max-w-7xl space-y-8">
      <header className="space-y-3">
        <h1 className="text-3xl font-semibold tracking-tight">Demo compare</h1>
        <p className="max-w-4xl text-sm leading-6 text-stone-600">
          Compare B2, B3, and B4 on the same `requests` evaluation prompts. This page uses a
          fixed snapshot from the latest local H1 suite so the demo stays stable during review.
        </p>
      </header>

      <section className="grid gap-4 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
        <div className="rounded-lg border border-stone-200 bg-white p-5 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-lg font-semibold text-stone-900">H1 status</h2>
            <span
              className={`inline-flex rounded-md px-2 py-1 text-xs font-medium ${
                h1Report.decision === 'supported'
                  ? 'bg-emerald-100 text-emerald-800'
                  : 'bg-rose-100 text-rose-800'
              }`}
            >
              {h1Report.decision}
            </span>
          </div>
          <p className="mt-4 text-sm leading-6 text-stone-700">{h1Report.note}</p>
          <div className="mt-5 grid gap-3 sm:grid-cols-2">
            {TAXONOMY_ORDER.map((level) => {
              const comparison = h1Report.comparisons[level];
              return (
                <div key={level} className="rounded-md border border-stone-200 bg-stone-50 px-4 py-4">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-stone-900">{level}</span>
                    <span className="text-xs text-stone-500">
                      threshold {h1Report.threshold.toFixed(2)}
                    </span>
                  </div>
                  <dl className="mt-3 space-y-2 text-sm text-stone-700">
                    <div className="flex items-center justify-between gap-4">
                      <dt>B4 composite</dt>
                      <dd>{comparison.baselineComposite.toFixed(3)}</dd>
                    </div>
                    <div className="flex items-center justify-between gap-4">
                      <dt>vs B2</dt>
                      <dd>{comparison.marginVsB2.toFixed(3)}</dd>
                    </div>
                    <div className="flex items-center justify-between gap-4">
                      <dt>vs B3</dt>
                      <dd>{comparison.marginVsB3.toFixed(3)}</dd>
                    </div>
                  </dl>
                </div>
              );
            })}
          </div>
        </div>

        <div className="rounded-lg border border-stone-200 bg-white p-5 shadow-sm">
          <h2 className="text-lg font-semibold text-stone-900">Suite summary</h2>
          <div className="mt-4 space-y-3">
            {BASELINE_ORDER.map((baseline) => {
              const summary = suiteSummary[baseline];
              return (
                <div key={baseline} className="rounded-md border border-stone-200 bg-stone-50 px-4 py-4">
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-sm font-medium text-stone-900">{baseline}</span>
                    <span className="text-xs text-stone-500">{summary.questions} questions</span>
                  </div>
                  <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-sm text-stone-700">
                    <div className="flex items-center justify-between gap-3">
                      <dt>Recall@k</dt>
                      <dd>{summary.recallAtK.toFixed(3)}</dd>
                    </div>
                    <div className="flex items-center justify-between gap-3">
                      <dt>MRR</dt>
                      <dd>{summary.mrr.toFixed(3)}</dd>
                    </div>
                    <div className="flex items-center justify-between gap-3">
                      <dt>NDCG@k</dt>
                      <dd>{summary.ndcgAtK.toFixed(3)}</dd>
                    </div>
                    <div className="flex items-center justify-between gap-3">
                      <dt>Grounded</dt>
                      <dd>{summary.groundedness.toFixed(2)}</dd>
                    </div>
                  </dl>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[20rem_minmax(0,1fr)]">
        <aside className="rounded-lg border border-stone-200 bg-white p-5 shadow-sm">
          <div className="flex gap-2">
            {TAXONOMY_ORDER.map((level) => (
              <button
                key={level}
                type="button"
                onClick={() => setTaxonomy(level)}
                className={`rounded-md px-3 py-2 text-sm font-medium ${
                  taxonomy === level
                    ? 'bg-stone-900 text-white'
                    : 'border border-stone-300 bg-white text-stone-700'
                }`}
              >
                {level}
              </button>
            ))}
          </div>

          <div className="mt-4 space-y-2">
            {visibleCases.map((questionCase) => (
              <button
                key={questionCase.questionId}
                type="button"
                onClick={() => setSelectedQuestionId(questionCase.questionId)}
                className={`block w-full rounded-md px-3 py-3 text-left text-sm transition ${
                  questionCase.questionId === selectedCase?.questionId
                    ? 'bg-stone-900 text-white'
                    : 'border border-stone-200 bg-stone-50 text-stone-800 hover:border-stone-300'
                }`}
              >
                <div className="font-medium">{questionCase.questionId}</div>
                <div className="mt-1 line-clamp-4 text-xs leading-5 opacity-90">
                  {questionCase.question}
                </div>
              </button>
            ))}
          </div>
        </aside>

        <div className="space-y-6">
          {selectedCase ? (
            <>
              <section className="rounded-lg border border-stone-200 bg-white p-5 shadow-sm">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <h2 className="text-lg font-semibold text-stone-900">{selectedCase.question}</h2>
                  <span className="rounded-md bg-stone-100 px-2 py-1 text-xs font-medium text-stone-700">
                    {selectedCase.taxonomy}
                  </span>
                </div>
                <p className="mt-4 text-sm text-stone-600">
                  Ground-truth files: {selectedCase.gtFiles.join(', ')}
                </p>
              </section>

              <section className="grid gap-4 xl:grid-cols-3">
                {BASELINE_ORDER.map((baseline) => {
                  const answer = selectedCase.baselines[baseline];
                  return (
                    <div key={baseline} className="rounded-lg border border-stone-200 bg-white p-5 shadow-sm">
                      <div className="flex items-center justify-between gap-3">
                        <h3 className="text-base font-semibold text-stone-900">{baseline}</h3>
                        <span
                          className={`rounded-md px-2 py-1 text-xs font-medium ${
                            answer.groundedness >= 0.95
                              ? 'bg-emerald-100 text-emerald-800'
                              : 'bg-amber-100 text-amber-800'
                          }`}
                        >
                          grounded {answer.groundedness.toFixed(2)}
                        </span>
                      </div>

                      <dl className="mt-4 grid grid-cols-3 gap-2 text-xs text-stone-600">
                        <div className="rounded-md bg-stone-50 px-2 py-2">
                          <dt>Recall</dt>
                          <dd className="mt-1 font-medium text-stone-900">
                            {answer.recallAtK.toFixed(3)}
                          </dd>
                        </div>
                        <div className="rounded-md bg-stone-50 px-2 py-2">
                          <dt>MRR</dt>
                          <dd className="mt-1 font-medium text-stone-900">
                            {answer.mrr.toFixed(3)}
                          </dd>
                        </div>
                        <div className="rounded-md bg-stone-50 px-2 py-2">
                          <dt>NDCG</dt>
                          <dd className="mt-1 font-medium text-stone-900">
                            {answer.ndcgAtK.toFixed(3)}
                          </dd>
                        </div>
                      </dl>

                      <div className="mt-4 whitespace-pre-wrap rounded-md bg-stone-50 px-4 py-4 text-sm leading-6 text-stone-800">
                        {answer.answer}
                      </div>

                      <div className="mt-4 space-y-2">
                        {answer.citations.map((citation, index) => (
                          <div
                            key={`${baseline}-${index}-${citation}`}
                            className="flex items-center justify-between gap-3 rounded-md border border-stone-200 px-3 py-2 text-sm"
                          >
                            <span className="font-mono text-stone-800">{citation}</span>
                            <span
                              className={`rounded-md px-2 py-1 text-xs font-medium ${
                                citation === '`:0`'
                                  ? 'bg-amber-100 text-amber-800'
                                  : 'bg-emerald-100 text-emerald-800'
                              }`}
                            >
                              {citation === '`:0`' ? 'suspect' : 'grounded'}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </section>
            </>
          ) : null}
        </div>
      </section>
    </section>
  );
}
