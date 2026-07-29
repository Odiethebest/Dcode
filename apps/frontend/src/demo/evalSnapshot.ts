/**
 * H1 evaluation snapshot — generated from `results/eval-real/`, the full
 * real-model run (Jina v2-base-code 768-dim + BGE reranker v2-m3 + gpt-4o-mini)
 * recorded 2026-07-28 against the psf/requests corpus.
 *
 * Every number below is copied verbatim from a committed artifact in that
 * directory. Nothing here is rounded, adjusted, or hand-entered: `/methodology`
 * claims these match the recorded run, so they have to be checkable against it.
 * Regenerate rather than edit by hand.
 */

export type BaselineName = 'B1' | 'B2' | 'B3' | 'B4';
/** Every question level in the suite. */
export type Level = 'L1' | 'L2' | 'L3';
/** The levels H1 is actually evaluated on — L1 is single-hop and out of scope. */
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
  /** Questions at this level — L3 is n=3, small enough to be read with care. */
  questions: number;
  b2Composite: number;
  b3Composite: number;
  b4Composite: number;
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

/** Where these numbers come from, so the page can point at it. */
export const snapshotSource = {
  path: 'results/eval-real/',
  recorded: '2026-07-28',
  corpus: 'psf/requests',
  repoId: '2543893e-0965-4be7-ac45-5a8e38600bc0',
  k: 5,
  embedding: 'Jina v2-base-code (768-dim)',
  reranker: 'BGE reranker v2-m3',
  synthesis: 'gpt-4o-mini',
} as const;

/** Whole-suite metrics, all 16 questions. */
export const suiteSummary: Record<BaselineName, BaselineSummary> = {
  B1: {
    baseline: 'B1',
    questions: 16,
    recallAtK: 0.21354166666666666,
    mrr: 0.22083333333333333,
    ndcgAtK: 0.20391186865251767,
    groundedness: 1.0,
  },
  B2: {
    baseline: 'B2',
    questions: 16,
    recallAtK: 0.4739583333333333,
    mrr: 0.325,
    ndcgAtK: 0.3326636655451126,
    groundedness: 1.0,
  },
  B3: {
    baseline: 'B3',
    questions: 16,
    recallAtK: 0.5416666666666666,
    mrr: 0.5958333333333333,
    ndcgAtK: 0.508070342853884,
    groundedness: 1.0,
  },
  B4: {
    baseline: 'B4',
    questions: 16,
    recallAtK: 0.5416666666666666,
    mrr: 0.5958333333333333,
    ndcgAtK: 0.508070342853884,
    groundedness: 0.9158143939393939,
  },
};

/**
 * Per-level metrics. B3 and B4 are identical on every retrieval metric at every
 * level — B4's scored `retrieve()` calls the same hybrid search as B3, and its
 * call-graph tools fire later, inside the answer, which this harness does not
 * score. They diverge only on groundedness.
 */
export const levelSummary: Record<Level, Record<BaselineName, BaselineSummary>> = {
  L1: {
    B1: {
      baseline: 'B1',
      questions: 5,
      recallAtK: 0.2,
      mrr: 0.2,
      ndcgAtK: 0.2,
      groundedness: 1.0,
    },
    B2: {
      baseline: 'B2',
      questions: 5,
      recallAtK: 1.0,
      mrr: 0.54,
      ndcgAtK: 0.6559284135897828,
      groundedness: 1.0,
    },
    B3: {
      baseline: 'B3',
      questions: 5,
      recallAtK: 1.0,
      mrr: 0.9,
      ndcgAtK: 0.9261859507142916,
      groundedness: 1.0,
    },
    B4: {
      baseline: 'B4',
      questions: 5,
      recallAtK: 1.0,
      mrr: 0.9,
      ndcgAtK: 0.9261859507142916,
      groundedness: 1.0,
    },
  },
  L2: {
    B1: {
      baseline: 'B1',
      questions: 8,
      recallAtK: 0.20833333333333331,
      mrr: 0.25,
      ndcgAtK: 0.2206700796235777,
      groundedness: 1.0,
    },
    B2: {
      baseline: 'B2',
      questions: 8,
      recallAtK: 0.2916666666666667,
      mrr: 0.2708333333333333,
      ndcgAtK: 0.2309733194721046,
      groundedness: 1.0,
    },
    B3: {
      baseline: 'B3',
      questions: 8,
      recallAtK: 0.3958333333333333,
      mrr: 0.55625,
      ndcgAtK: 0.39185977135293965,
      groundedness: 1.0,
    },
    B4: {
      baseline: 'B4',
      questions: 8,
      recallAtK: 0.3958333333333333,
      mrr: 0.55625,
      ndcgAtK: 0.39185977135293965,
      groundedness: 0.9020833333333333,
    },
  },
  L3: {
    B1: {
      baseline: 'B1',
      questions: 3,
      recallAtK: 0.25,
      mrr: 0.17777777777777778,
      ndcgAtK: 0.16574308715055378,
      groundedness: 1.0,
    },
    B2: {
      baseline: 'B2',
      questions: 3,
      recallAtK: 0.08333333333333333,
      mrr: 0.1111111111111111,
      ndcgAtK: 0.06506334166535029,
      groundedness: 1.0,
    },
    B3: {
      baseline: 'B3',
      questions: 3,
      recallAtK: 0.16666666666666666,
      mrr: 0.19444444444444445,
      ndcgAtK: 0.12110585375572276,
      groundedness: 1.0,
    },
    B4: {
      baseline: 'B4',
      questions: 3,
      recallAtK: 0.16666666666666666,
      mrr: 0.19444444444444445,
      ndcgAtK: 0.12110585375572276,
      groundedness: 0.8121212121212121,
    },
  },
};

/** Verbatim from results/eval-real/h1_report.json. */
export const h1Report = {
  decision: 'unsupported',
  threshold: 0.05,
  note: 'H1 is supported only if B4 beats both B2 and B3 by at least 0.05 composite points on both L2 and L3.',
  comparisons: {
    L2: {
      questions: 8,
      b2Composite: 0.44836832986802616,
      b3Composite: 0.5859857761715682,
      b4Composite: 0.5615066095049016,
      marginVsB2: 0.11313827963687545,
      marginVsB3: -0.024479166666666607,
      supported: false,
    },
    L3: {
      questions: 3,
      b2Composite: 0.3148769465274487,
      b3Composite: 0.3705542412167085,
      b4Composite: 0.3235845442470115,
      marginVsB2: 0.00870759771956281,
      marginVsB3: -0.046969696969696995,
      supported: false,
    },
  } satisfies Record<Taxonomy, H1Comparison>,
};

/**
 * Per-question transcripts, straight out of each baseline's per_question.jsonl.
 * Architectural flows chosen so the page doesn't lean on one narrow subsystem.
 */
export const demoCases: DemoQuestionCase[] = [
  {
    questionId: 'q-008',
    taxonomy: 'L2',
    question: 'How does a `Session` prepare a request before it is sent?',
    gtFiles: ['src/requests/sessions.py', 'src/requests/models.py'],
    baselines: {
      B1: {
        answer:
          'B1 sparse baseline top evidence:\n- `tests/test_requests.py:1572` `test_prepared_request_with_file_is_pickleable`\n- `tests/test_requests.py:1588` `test_prepared_request_with_hook_is_pickleable`\n- `src/requests/models.py:378` `PreparedRequest`',
        citations: [
          '`tests/test_requests.py:1572`',
          '`tests/test_requests.py:1588`',
          '`src/requests/models.py:378`',
        ],
        groundedness: 1.0,
        recallAtK: 0.0,
        mrr: 0.0,
        ndcgAtK: 0.0,
      },
      B2: {
        answer:
          'B2 dense baseline top evidence:\n- `tests/test_requests.py:1239` `test_prepared_from_session`\n- `src/requests/models.py:378` `PreparedRequest`\n- `src/requests/sessions.py:511` `prepare_request`',
        citations: [
          '`tests/test_requests.py:1239`',
          '`src/requests/models.py:378`',
          '`src/requests/sessions.py:511`',
        ],
        groundedness: 1.0,
        recallAtK: 0.5,
        mrr: 0.3333333333333333,
        ndcgAtK: 0.3065735963827292,
      },
      B3: {
        answer:
          'B3 hybrid baseline top evidence:\n- `src/requests/sessions.py:511` `prepare_request`\n- `tests/test_requests.py:624` `test_respect_proxy_env_on_send_session_prepared_request`\n- `tests/test_requests.py:1256` `test_prepare_request_with_bytestring_url`',
        citations: [
          '`src/requests/sessions.py:511`',
          '`tests/test_requests.py:624`',
          '`tests/test_requests.py:1256`',
        ],
        groundedness: 1.0,
        recallAtK: 0.5,
        mrr: 1.0,
        ndcgAtK: 0.6131471927654584,
      },
      B4: {
        answer:
          "A `Session` prepares a request by using the `prepare_request` method, which constructs a `PreparedRequest` for transmission. This method merges settings from the `Request` instance with those of the `Session`. \n\nHere's how the preparation process works:\n\n1. **Extracting URL and Method**: The method retrieves the URL and HTTP method from the `Request` instance.\n2. **Handling Cookies**: It checks if cookies are provided and ensures they are in the correct format, merging them with any cookies stored in the session.\n3. **Authentication**: If no authentication is explicitly set in the request or session, it attempts to retrieve it from the environment using `get_netrc_auth`.\n4. **Creating PreparedRequest**: Finally, it creates a `PreparedRequest` and calls its `prepare` method to finalize the request setup (`src/requests/sessions.py:511`).\n\nThis process ensures that the request is properly configured with all necessary settings before it is sent.",
        citations: ['`src/requests/sessions.py:511`'],
        groundedness: 1.0,
        recallAtK: 0.5,
        mrr: 1.0,
        ndcgAtK: 0.6131471927654584,
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
          'B1 sparse baseline top evidence:\n- `src/requests/utils.py:341` `from_key_val_list`\n- `src/requests/utils.py:373` `to_key_val_list`\n- `src/requests/utils.py:371` `to_key_val_list`',
        citations: [
          '`src/requests/utils.py:341`',
          '`src/requests/utils.py:373`',
          '`src/requests/utils.py:371`',
        ],
        groundedness: 1.0,
        recallAtK: 0.0,
        mrr: 0.0,
        ndcgAtK: 0.0,
      },
      B2: {
        answer:
          'B2 dense baseline top evidence:\n- `src/requests/sessions.py:395` `Session`\n- `src/requests/sessions.py:1` `__module_doc__`\n- `src/requests/api.py:1` `__module_doc__`',
        citations: [
          '`src/requests/sessions.py:395`',
          '`src/requests/sessions.py:1`',
          '`src/requests/api.py:1`',
        ],
        groundedness: 1.0,
        recallAtK: 0.0,
        mrr: 0.0,
        ndcgAtK: 0.0,
      },
      B3: {
        answer:
          'B3 hybrid baseline top evidence:\n- `src/requests/sessions.py:395` `Session`\n- `src/requests/sessions.py:1` `__module_doc__`\n- `src/requests/sessions.py:442` `__init__`',
        citations: [
          '`src/requests/sessions.py:395`',
          '`src/requests/sessions.py:1`',
          '`src/requests/sessions.py:442`',
        ],
        groundedness: 1.0,
        recallAtK: 0.0,
        mrr: 0.0,
        ndcgAtK: 0.0,
      },
      B4: {
        answer:
          'The flow from [unverified reference removed] to [unverified reference removed] involves several steps:\n\n1. **Entry Point**: The process begins at [unverified reference removed], which is defined in `src/requests/api.py:24`. This function is responsible for handling the initial request.\n\n2. **Session Creation**: Within the `request` function, a `Session` object is typically created or retrieved. The `Session` class is defined in `src/requests/sessions.py:395`, and it manages settings like cookies, headers, and authentication across multiple requests.\n\n3. **Preparing the Request**: The `Session` object has a method called `request`, located at `src/requests/sessions.py:655`. This method is invoked to handle the actual HTTP request. Before sending the request, it prepares the request using the `prepare_request` method, which is defined at `src/requests/sessions.py:511`. This method constructs a `PreparedRequest` that merges the request settings with those of the session.\n\n4. **Sending the Request**: After preparation, the `Session` sends the request using its `send` method, found at `src/requests/sessions.py:752`. This method handles the actual transmission of the request to the server.\n\nIn summary, the flow is as follows: [unverified reference removed] → creates or uses a `Session` → calls [unverified reference removed] → prepares the request with [unverified reference removed] → sends the request with [unverified reference removed].\n\n> ⚠️ Groundedness 0.42 is below the 0.95 guardrail: 7 unverified references removed (not found in the index).',
        citations: [
          '`src/requests/api.py:24`',
          '`src/requests/sessions.py:395`',
          '`src/requests/sessions.py:655`',
          '`src/requests/sessions.py:511`',
          '`src/requests/sessions.py:752`',
        ],
        groundedness: 0.4166666666666667,
        recallAtK: 0.0,
        mrr: 0.0,
        ndcgAtK: 0.0,
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
          'B1 sparse baseline top evidence:\n- `src/requests/adapters.py:128` `send`\n- `src/requests/adapters.py:634` `send`\n- `src/requests/cookies.py:135` `extract_cookies_to_jar`',
        citations: [
          '`src/requests/adapters.py:128`',
          '`src/requests/adapters.py:634`',
          '`src/requests/cookies.py:135`',
        ],
        groundedness: 1.0,
        recallAtK: 0.25,
        mrr: 0.2,
        ndcgAtK: 0.15101961822780524,
      },
      B2: {
        answer:
          'B2 dense baseline top evidence:\n- `src/requests/sessions.py:132` `send`\n- `tests/test_requests.py:2649` `test_requests_are_updated_each_time`\n- `src/requests/sessions.py:752` `send`',
        citations: [
          '`src/requests/sessions.py:132`',
          '`tests/test_requests.py:2649`',
          '`src/requests/sessions.py:752`',
        ],
        groundedness: 1.0,
        recallAtK: 0.25,
        mrr: 0.3333333333333333,
        ndcgAtK: 0.19519002499605084,
      },
      B3: {
        answer:
          'B3 hybrid baseline top evidence:\n- `tests/test_requests.py:2649` `test_requests_are_updated_each_time`\n- `src/requests/sessions.py:132` `send`\n- `src/requests/sessions.py:752` `send`',
        citations: [
          '`tests/test_requests.py:2649`',
          '`src/requests/sessions.py:132`',
          '`src/requests/sessions.py:752`',
        ],
        groundedness: 1.0,
        recallAtK: 0.25,
        mrr: 0.3333333333333333,
        ndcgAtK: 0.19519002499605084,
      },
      B4: {
        answer:
          'The end-to-end send flow from [unverified reference removed] to [unverified reference removed] can be summarized as follows:\n\n1. **Request Preparation**: The process begins with a request being prepared using [unverified reference removed]. This is done in the test case where a POST request is prepared with `prep = [unverified reference removed]("POST", httpbin("post")).prepare()` (`tests/test_requests.py:2649`).\n\n2. **Sending the Request**: The prepared request is then sent using the `send` method of a `Session` object. In the test, this is executed with `r0 = session.send(prep)` (`tests/test_requests.py:2649`). The `send` method is defined in the `Session` class, which is responsible for sending the prepared request and returning a response (`src/requests/sessions.py:752`).\n\n3. **Handling Prepared Requests**: Inside the `send` method, there is a check to ensure that the request is a `PreparedRequest`. If it is not, a `ValueError` is raised (`src/requests/sessions.py:752`). This is confirmed by the tests that ensure unprepared requests cannot be sent (`tests/test_requests.py:1604`, `tests/test_requests.py:1170`).\n\n4. **Processing the Response**: After sending the request, the response is processed, which may involve handling redirects if the response indicates a redirect status. The test case also demonstrates this by resolving redirects with `redirect_generator = session.resolve_redirects(r0, prep)` (`tests/test_requests.py:2649`).\n\nIn summary, the flow involves preparing a request, sending it through the [unverified reference removed] method, ensuring it is a prepared request, and then processing the response, including any redirects.\n\n> ⚠️ Groundedness 0.64 is below the 0.95 guardrail: 4 unverified references removed (not found in the index).',
        citations: [
          '`tests/test_requests.py:2649`',
          '`tests/test_requests.py:2649`',
          '`src/requests/sessions.py:752`',
          '`src/requests/sessions.py:752`',
          '`tests/test_requests.py:1604`',
          '`tests/test_requests.py:1170`',
          '`tests/test_requests.py:2649`',
        ],
        groundedness: 0.6363636363636364,
        recallAtK: 0.25,
        mrr: 0.3333333333333333,
        ndcgAtK: 0.19519002499605084,
      },
    },
  },
  {
    questionId: 'q-016',
    taxonomy: 'L3',
    question: 'Explain how redirect handling works across the session stack.',
    gtFiles: ['src/requests/sessions.py'],
    baselines: {
      B1: {
        answer:
          'B1 sparse baseline top evidence:\n- `src/requests/sessions.py:127` `SessionRedirectMixin`\n- `src/requests/sessions.py:395` `Session`\n- `src/requests/sessions.py:134` `get_redirect_target`',
        citations: [
          '`src/requests/sessions.py:127`',
          '`src/requests/sessions.py:395`',
          '`src/requests/sessions.py:134`',
        ],
        groundedness: 1.0,
        recallAtK: 0.5,
        mrr: 0.3333333333333333,
        ndcgAtK: 0.34620964322385606,
      },
      B2: {
        answer:
          'B2 dense baseline top evidence:\n- `tests/test_requests.py:2608` `RedirectSession`\n- `src/requests/sessions.py:127` `SessionRedirectMixin`\n- `src/requests/auth.py:268` `handle_redirect`',
        citations: [
          '`tests/test_requests.py:2608`',
          '`src/requests/sessions.py:127`',
          '`src/requests/auth.py:268`',
        ],
        groundedness: 1.0,
        recallAtK: 0.0,
        mrr: 0.0,
        ndcgAtK: 0.0,
      },
      B3: {
        answer:
          'B3 hybrid baseline top evidence:\n- `tests/test_requests.py:2608` `RedirectSession`\n- `src/requests/sessions.py:127` `SessionRedirectMixin`\n- `tests/test_requests.py:2286` `test_custom_redirect_mixin`',
        citations: [
          '`tests/test_requests.py:2608`',
          '`src/requests/sessions.py:127`',
          '`tests/test_requests.py:2286`',
        ],
        groundedness: 1.0,
        recallAtK: 0.25,
        mrr: 0.25,
        ndcgAtK: 0.16812753627111746,
      },
      B4: {
        answer:
          'Redirect handling in the session stack is managed primarily through the `SessionRedirectMixin` and its subclasses, such as `RedirectSession`. \n\n1. **RedirectSession Class**: This class inherits from `SessionRedirectMixin` and is designed to handle a sequence of redirects specified by `order_of_redirects`. It maintains a list of calls made during the session and constructs responses based on the redirect order provided. The `send` method records each call and invokes `build_response` to generate the appropriate response based on the current redirect status (`tests/test_requests.py:2608`).\n\n2. **SessionRedirectMixin Class**: This mixin provides the foundational redirect handling logic. It includes the `get_redirect_target` method, which determines the next URL to redirect to based on the response received. This method is called multiple times during the redirect process, ensuring that each response is evaluated for potential redirects (`src/requests/sessions.py:127`, `src/requests/sessions.py:134`).\n\n3. **Redirect Logic**: When a response indicates a redirect (e.g., HTTP status codes like 302), the `get_redirect_target` method extracts the `Location` header from the response. It handles potential encoding issues with the header to ensure the URL is correctly interpreted. If the response is a redirect, the method returns the new location for the next request (`src/requests/sessions.py:134`).\n\n4. **Testing Redirect Handling**: The `test_custom_redirect_mixin` function tests the behavior of a custom session that overrides the redirect handling logic. It ensures that the session can correctly follow a redirect even when the response is malformed, demonstrating the flexibility of the redirect handling mechanism (`tests/test_requests.py:2286`).\n\nIn summary, the redirect handling mechanism is a combination of the `RedirectSession` class managing the sequence of redirects and the `SessionRedirectMixin` providing the logic to determine the next target URL based on the responses received.',
        citations: [
          '`tests/test_requests.py:2608`',
          '`src/requests/sessions.py:127`',
          '`src/requests/sessions.py:134`',
          '`src/requests/sessions.py:134`',
          '`tests/test_requests.py:2286`',
        ],
        groundedness: 1.0,
        recallAtK: 0.25,
        mrr: 0.25,
        ndcgAtK: 0.16812753627111746,
      },
    },
  },
];
