export type BaselineName = 'B1' | 'B2' | 'B3' | 'B4';
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
  B1: {
    baseline: 'B1',
    questions: 16,
    recallAtK: 0.027363445021008542,
    mrr: 0.3854166666666667,
    ndcgAtK: 0.2301844476761583,
    groundedness: 1.0,
  },
  B2: {
    baseline: 'B2',
    questions: 16,
    recallAtK: 0.0999737997588098,
    mrr: 0.7395833333333334,
    ndcgAtK: 0.5200690920451543,
    groundedness: 1.0,
  },
  B3: {
    baseline: 'B3',
    questions: 16,
    recallAtK: 0.06728134935397131,
    mrr: 0.7083333333333334,
    ndcgAtK: 0.4260447454804978,
    groundedness: 1.0,
  },
  B4: {
    baseline: 'B4',
    questions: 16,
    recallAtK: 0.06728134935397131,
    mrr: 0.7083333333333334,
    ndcgAtK: 0.4260447454804978,
    groundedness: 0.984375,
  },
};

export const h1Report = {
  decision: 'unsupported',
  threshold: 0.05,
  note: 'H1 requires B4 to beat both B2 and B3 by at least 0.05 composite points on both L2 and L3.',
  comparisons: {
    L2: {
      baselineComposite: 0.5622414869384356,
      marginVsB2: -0.025329635486131652,
      marginVsB3: -0.00390625,
      supported: false,
    },
    L3: {
      baselineComposite: 0.5863208133192348,
      marginVsB2: 0.016638419453822717,
      marginVsB3: -0.01041666666666674,
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
      B1: {
        answer:
          'B1 sparse baseline top evidence:\n- `src/requests/auth.py:85` `HTTPBasicAuth`\n- `src/requests/auth.py:34` `_basic_auth_str`\n- `src/requests/auth.py:124` `HTTPDigestAuth`',
        citations: [
          '`src/requests/auth.py:85`',
          '`src/requests/auth.py:34`',
          '`src/requests/auth.py:124`',
        ],
        groundedness: 1,
        recallAtK: 0.0494,
        mrr: 1.0,
        ndcgAtK: 0.8688,
      },
      B2: {
        answer:
          'B2 dense baseline top evidence:\n- `src/requests/auth.py:116` `HTTPProxyAuth`\n- `src/requests/auth.py:111` `__call__`\n- `src/requests/auth.py:85` `HTTPBasicAuth`',
        citations: ['`src/requests/auth.py:116`', '`src/requests/auth.py:111`', '`src/requests/auth.py:85`'],
        groundedness: 1,
        recallAtK: 0.0494,
        mrr: 1.0,
        ndcgAtK: 0.8539,
      },
      B3: {
        answer:
          'B3 hybrid baseline top evidence:\n- `src/requests/auth.py:85` `HTTPBasicAuth`\n- `src/requests/auth.py:116` `HTTPProxyAuth`\n- `tests/test_requests.py:563` `test_set_basicauth`',
        citations: ['`src/requests/auth.py:85`', '`src/requests/auth.py:116`', '`tests/test_requests.py:563`'],
        groundedness: 1,
        recallAtK: 0.037,
        mrr: 1.0,
        ndcgAtK: 0.6844,
      },
      B4: {
        answer:
          'Agent trace for `How does requests attach basic auth to a prepared request?`:\n- `search_code` found these likely entry points:\n  - `HTTPBasicAuth` in `src/requests/auth.py:85`\n  - `HTTPProxyAuth` in `src/requests/auth.py:116`\n  - `test_set_basicauth` in `tests/test_requests.py:563`\n- `read_file` inspected `src/requests/auth.py:85`-`113` for local implementation context.\n- `get_file_outline` added nearby file symbols.',
        citations: ['`src/requests/auth.py:85`', '`src/requests/auth.py:116`', '`tests/test_requests.py:563`', '`src/requests/auth.py:1`', '`src/requests/auth.py:78`'],
        groundedness: 1.0,
        recallAtK: 0.037,
        mrr: 1.0,
        ndcgAtK: 0.6844,
      },
    },
  },
  {
    questionId: 'q-010',
    taxonomy: 'L2',
    question: 'What is the flow from `requests.api.request` to `Session.request`?',
    gtFiles: ['src/requests/api.py', 'src/requests/sessions.py'],
    baselines: {
      B1: {
        answer:
          'B1 sparse baseline top evidence:\n- `src/requests/utils.py:341` `from_key_val_list`\n- `src/requests/utils.py:376` `to_key_val_list`\n- `src/requests/utils.py:373` `to_key_val_list`',
        citations: [
          '`src/requests/utils.py:341`',
          '`src/requests/utils.py:376`',
          '`src/requests/utils.py:373`',
        ],
        groundedness: 1,
        recallAtK: 0.0,
        mrr: 0.0,
        ndcgAtK: 0.0,
      },
      B2: {
        answer:
          'B2 dense baseline top evidence:\n- `src/requests/sessions.py:395` `Session`\n- `src/requests/sessions.py:1` `__module_doc__`\n- `src/requests/api.py:1` `__module_doc__`',
        citations: ['`src/requests/sessions.py:395`', '`src/requests/sessions.py:1`', '`src/requests/api.py:1`'],
        groundedness: 1,
        recallAtK: 0.0976,
        mrr: 1.0,
        ndcgAtK: 0.8688,
      },
      B3: {
        answer:
          'B3 hybrid baseline top evidence:\n- `src/requests/sessions.py:127` `SessionRedirectMixin`\n- `src/requests/models.py:732` `Response`\n- `src/requests/utils.py:341` `from_key_val_list`',
        citations: ['`src/requests/sessions.py:127`', '`src/requests/models.py:732`', '`src/requests/utils.py:341`'],
        groundedness: 1,
        recallAtK: 0.0488,
        mrr: 1.0,
        ndcgAtK: 0.4852,
      },
      B4: {
        answer:
          'Agent trace for `What is the flow from requests.api.request to Session.request?`:\n- `search_code` found these likely entry points:\n  - `SessionRedirectMixin` in `src/requests/sessions.py:127`\n  - `Response` in `src/requests/models.py:732`\n  - `from_key_val_list` in `src/requests/utils.py:341`\n- `read_file` inspected `src/requests/sessions.py:395`-`450` for Session.request implementation.\n- `get_file_outline` added nearby file symbols.',
        citations: ['`src/requests/sessions.py:127`', '`src/requests/models.py:732`', '`src/requests/utils.py:341`', '`src/requests/sessions.py:395`', '`src/requests/api.py:1`'],
        groundedness: 0.875,
        recallAtK: 0.0488,
        mrr: 1.0,
        ndcgAtK: 0.4852,
      },
    },
  },
  {
    questionId: 'q-015',
    taxonomy: 'L3',
    question: 'Explain the end-to-end send flow from `requests.api.request` to `Session.send`.',
    gtFiles: ['src/requests/api.py', 'src/requests/sessions.py'],
    baselines: {
      B1: {
        answer:
          'B1 sparse baseline top evidence:\n- `src/requests/utils.py:522` `get_encodings_from_content`\n- `src/requests/cookies.py:579` `cookiejar_from_dict`\n- `src/requests/sessions.py:752` `send`',
        citations: ['`src/requests/utils.py:522`', '`src/requests/cookies.py:579`', '`src/requests/sessions.py:752`'],
        groundedness: 1,
        recallAtK: 0.0244,
        mrr: 0.3333,
        ndcgAtK: 0.1696,
      },
      B2: {
        answer:
          'B2 dense baseline top evidence:\n- `src/requests/sessions.py:132` `send`\n- `tests/test_requests.py:2649` `test_requests_are_updated_each_time`\n- `src/requests/sessions.py:752` `send`',
        citations: ['`src/requests/sessions.py:132`', '`tests/test_requests.py:2649`', '`src/requests/sessions.py:752`'],
        groundedness: 1,
        recallAtK: 0.0488,
        mrr: 1.0,
        ndcgAtK: 0.5087,
      },
      B3: {
        answer:
          'B3 hybrid baseline top evidence:\n- `src/requests/sessions.py:752` `send`\n- `src/requests/sessions.py:132` `send`\n- `src/requests/adapters.py:634` `send`',
        citations: ['`src/requests/sessions.py:752`', '`src/requests/sessions.py:132`', '`src/requests/adapters.py:634`'],
        groundedness: 1,
        recallAtK: 0.0732,
        mrr: 1.0,
        ndcgAtK: 0.6992,
      },
      B4: {
        answer:
          'Agent trace for `Explain the end-to-end send flow from requests.api.request to Session.send.`:\n- `search_code` found these likely entry points:\n  - `send` in `src/requests/sessions.py:752`\n  - `send` in `src/requests/sessions.py:132`\n  - `send` in `src/requests/adapters.py:634`\n- `read_file` inspected `src/requests/sessions.py:752`-`820` for the full send path.\n- `get_file_outline` added nearby file symbols.',
        citations: ['`src/requests/sessions.py:752`', '`src/requests/sessions.py:132`', '`src/requests/adapters.py:634`', '`src/requests/sessions.py:395`', '`src/requests/api.py:1`'],
        groundedness: 0.875,
        recallAtK: 0.0732,
        mrr: 1.0,
        ndcgAtK: 0.6992,
      },
    },
  },
];
