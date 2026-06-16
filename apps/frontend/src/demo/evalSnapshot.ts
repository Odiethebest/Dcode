export type BaselineName = 'B2' | 'B3' | 'B4';
export type Taxonomy = 'L2' | 'L3';

export interface BaselineSummary {
  baseline: BaselineName;
  questions: number;
  recallAtK: number;
  mrr: number;
  ndcgAtK: number;
  groundedness: number;
}

export interface H1Comparison {
  baselineComposite: number;
  marginVsB2: number;
  marginVsB3: number;
  supported: boolean;
}

export interface DemoBaselineAnswer {
  answer: string;
  citations: string[];
  groundedness: number;
  recallAtK: number;
  mrr: number;
  ndcgAtK: number;
}

export interface DemoQuestionCase {
  questionId: string;
  taxonomy: Taxonomy;
  question: string;
  gtFiles: string[];
  baselines: Record<BaselineName, DemoBaselineAnswer>;
}

export const suiteSummary: Record<BaselineName, BaselineSummary> = {
  B2: {
    baseline: 'B2',
    questions: 16,
    recallAtK: 0.19791666666666666,
    mrr: 0.2125,
    ndcgAtK: 0.1917124920902645,
    groundedness: 1,
  },
  B3: {
    baseline: 'B3',
    questions: 16,
    recallAtK: 0.19791666666666666,
    mrr: 0.2125,
    ndcgAtK: 0.1917124920902645,
    groundedness: 1,
  },
  B4: {
    baseline: 'B4',
    questions: 16,
    recallAtK: 0.19791666666666666,
    mrr: 0.2125,
    ndcgAtK: 0.1917124920902645,
    groundedness: 0.95,
  },
};

export const h1Report = {
  decision: 'unsupported',
  threshold: 0.05,
  note: 'H1 requires B4 to beat both B2 and B3 by at least 0.05 composite points on both L2 and L3.',
  comparisons: {
    L2: {
      baselineComposite: 0.4072508532392277,
      marginVsB2: -0.012500000000000067,
      marginVsB3: -0.012500000000000067,
      supported: false,
    },
    L3: {
      baselineComposite: 0.31683660303796757,
      marginVsB2: -0.033333333333333326,
      marginVsB3: -0.033333333333333326,
      supported: false,
    },
  } satisfies Record<Taxonomy, H1Comparison>,
};

export const demoCases: DemoQuestionCase[] = [
  {
    questionId: 'q-006',
    taxonomy: 'L2',
    question: 'How does requests attach basic auth to a prepared request?',
    gtFiles: ['src/requests/models.py', 'src/requests/auth.py'],
    baselines: {
      B2: {
        answer:
          'B2 dense baseline top evidence:\n- `src/requests/auth.py:85` `HTTPBasicAuth`\n- `src/requests/auth.py:34` `_basic_auth_str`\n- `src/requests/auth.py:124` `HTTPDigestAuth`',
        citations: [
          '`src/requests/auth.py:85`',
          '`src/requests/auth.py:34`',
          '`src/requests/auth.py:124`',
        ],
        groundedness: 1,
        recallAtK: 0.6666666666666666,
        mrr: 1,
        ndcgAtK: 0.7653606369886217,
      },
      B3: {
        answer:
          'B3 hybrid baseline top evidence:\n- `src/requests/auth.py:85` `HTTPBasicAuth`\n- `src/requests/auth.py:34` `_basic_auth_str`\n- `src/requests/auth.py:124` `HTTPDigestAuth`',
        citations: [
          '`src/requests/auth.py:85`',
          '`src/requests/auth.py:34`',
          '`src/requests/auth.py:124`',
        ],
        groundedness: 1,
        recallAtK: 0.6666666666666666,
        mrr: 1,
        ndcgAtK: 0.7653606369886217,
      },
      B4: {
        answer:
          'Top code hits for `How does requests attach basic auth to a prepared request?`:\n- `HTTPBasicAuth` in `src/requests/auth.py:85`\n- `_basic_auth_str` in `src/requests/auth.py:34`\n- `HTTPDigestAuth` in `src/requests/auth.py:124`',
        citations: [
          '`src/requests/auth.py:85`',
          '`src/requests/auth.py:34`',
          '`src/requests/auth.py:124`',
        ],
        groundedness: 1,
        recallAtK: 0.6666666666666666,
        mrr: 1,
        ndcgAtK: 0.7653606369886217,
      },
    },
  },
  {
    questionId: 'q-010',
    taxonomy: 'L2',
    question: 'What is the flow from `requests.api.request` to `Session.request`?',
    gtFiles: ['src/requests/api.py', 'src/requests/sessions.py'],
    baselines: {
      B2: {
        answer:
          'B2 dense baseline top evidence:\n- `src/requests/utils.py:341` `from_key_val_list`\n- `src/requests/utils.py:371` `to_key_val_list`\n- `src/requests/utils.py:373` `to_key_val_list`',
        citations: [
          '`src/requests/utils.py:341`',
          '`src/requests/utils.py:371`',
          '`src/requests/utils.py:373`',
        ],
        groundedness: 1,
        recallAtK: 0,
        mrr: 0,
        ndcgAtK: 0,
      },
      B3: {
        answer:
          'B3 hybrid baseline top evidence:\n- `src/requests/utils.py:341` `from_key_val_list`\n- `src/requests/utils.py:371` `to_key_val_list`\n- `src/requests/utils.py:373` `to_key_val_list`',
        citations: [
          '`src/requests/utils.py:341`',
          '`src/requests/utils.py:371`',
          '`src/requests/utils.py:373`',
        ],
        groundedness: 1,
        recallAtK: 0,
        mrr: 0,
        ndcgAtK: 0,
      },
      B4: {
        answer:
          'Top code hits for `What is the flow from `requests.api.request` to `Session.request`?`:\n- `from_key_val_list` in `src/requests/utils.py:341`\n- `to_key_val_list` in `src/requests/utils.py:371`\n- `to_key_val_list` in `src/requests/utils.py:373`',
        citations: [
          '`src/requests/utils.py:341`',
          '`src/requests/utils.py:371`',
          '`src/requests/utils.py:373`',
          '`:0`',
          '`:0`',
        ],
        groundedness: 0.6,
        recallAtK: 0,
        mrr: 0,
        ndcgAtK: 0,
      },
    },
  },
  {
    questionId: 'q-015',
    taxonomy: 'L3',
    question: 'Explain the end-to-end send flow from `requests.api.request` to `Session.send`.',
    gtFiles: ['src/requests/api.py', 'src/requests/sessions.py'],
    baselines: {
      B2: {
        answer:
          'B2 dense baseline top evidence:\n- `src/requests/adapters.py:128` `send`\n- `src/requests/adapters.py:634` `send`\n- `src/requests/cookies.py:135` `extract_cookies_to_jar`',
        citations: [
          '`src/requests/adapters.py:128`',
          '`src/requests/adapters.py:634`',
          '`src/requests/cookies.py:135`',
        ],
        groundedness: 1,
        recallAtK: 0.25,
        mrr: 0.2,
        ndcgAtK: 0.15101961822780524,
      },
      B3: {
        answer:
          'B3 hybrid baseline top evidence:\n- `src/requests/adapters.py:128` `send`\n- `src/requests/adapters.py:634` `send`\n- `src/requests/cookies.py:135` `extract_cookies_to_jar`',
        citations: [
          '`src/requests/adapters.py:128`',
          '`src/requests/adapters.py:634`',
          '`src/requests/cookies.py:135`',
        ],
        groundedness: 1,
        recallAtK: 0.25,
        mrr: 0.2,
        ndcgAtK: 0.15101961822780524,
      },
      B4: {
        answer:
          'Top code hits for `Explain the end-to-end send flow from `requests.api.request` to `Session.send`.`:\n- `send` in `src/requests/adapters.py:128`\n- `send` in `src/requests/adapters.py:634`\n- `extract_cookies_to_jar` in `src/requests/cookies.py:135`',
        citations: [
          '`src/requests/adapters.py:128`',
          '`src/requests/adapters.py:634`',
          '`src/requests/cookies.py:135`',
          '`:0`',
          '`:0`',
        ],
        groundedness: 0.6,
        recallAtK: 0.25,
        mrr: 0.2,
        ndcgAtK: 0.15101961822780524,
      },
    },
  },
];
