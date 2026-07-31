/**
 * H1 evaluation snapshot — generated from `results/eval-h1-bm25-2026-07-30/`, the full real-model run
 * (Jina v2-base-code (768-dim) + BGE reranker v2-m3 + gpt-4o-mini)
 * against the psf/requests corpus. Verdict written 2026-07-30 — a provenance
 * date, not one the harness recorded; see `results/eval-h1-bm25-2026-07-30/provenance.json`.
 *
 * Every number below is copied verbatim from a committed artifact in that
 * directory. Nothing here is rounded, adjusted, or hand-entered: `/methodology`
 * claims these match the recorded run, so they have to be checkable against it.
 *
 * Regenerate with `python3 scripts/sync_eval_artifacts.py` — do not edit by hand.
 */

export type BaselineName = 'B1' | 'B2' | 'B3' | 'B4';
/** Every question level in the suite. */
export type Level = 'L1' | 'L2' | 'L3';
/** The levels H1 is actually evaluated on — L1 is single-hop and out of scope. */
export type Taxonomy = 'L2' | 'L3';

/** Labels describe this recorded run, not every future implementation. */
export const baselineLabels: Record<BaselineName, string> = {
  B1: 'BM25 sparse',
  B2: 'Dense RAG',
  B3: 'Hybrid + rerank',
  B4: 'Dcode + graph + agent',
};

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
  path: 'results/eval-h1-bm25-2026-07-30/',
  /**
   * When the verdict file was written. Provenance metadata, not harness output —
   * the harness writes no timestamp, so every surface must preserve that distinction.
   * Observation basis and limits: `results/eval-h1-bm25-2026-07-30/provenance.json`.
   */
  verdictWritten: '2026-07-30',
  corpus: 'psf/requests',
  repoId: '2543893e-0965-4be7-ac45-5a8e38600bc0',
  k: 5,
  groundednessGuardrail: 0.95,
  sparseRetrieval: {
    implementation: 'okapi_bm25_v1',
    idf: 'ln(1 + (N - df + 0.5) / (df + 0.5))',
    k1: 1.2,
    b: 0.75,
    tokenizer: 'dcode_source_code_v1',
    document_fields: ['symbol_name', 'file_path', 'signature', 'content'],
    field_weighting: 'none',
    query_term_frequency: 'deduplicated',
  } as const,
  embedding: 'Jina v2-base-code (768-dim)',
  reranker: 'BGE reranker v2-m3',
  synthesis: 'gpt-4o-mini',
} as const;

/** Whole-suite metrics, all 16 questions. */
export const suiteSummary: Record<BaselineName, BaselineSummary> = {
  B1: {
    baseline: 'B1',
    questions: 16,
    recallAtK: 0.3958333333333333,
    mrr: 0.3614583333333333,
    ndcgAtK: 0.3106529350894414,
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
    recallAtK: 0.5260416666666666,
    mrr: 0.625,
    ndcgAtK: 0.5193678087913909,
    groundedness: 1.0,
  },
  B4: {
    baseline: 'B4',
    questions: 16,
    recallAtK: 0.5260416666666666,
    mrr: 0.625,
    ndcgAtK: 0.5193678087913909,
    groundedness: 1.0,
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
      recallAtK: 0.6,
      mrr: 0.36666666666666664,
      ndcgAtK: 0.4261859507142915,
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
      recallAtK: 0.3541666666666667,
      mrr: 0.24375,
      ndcgAtK: 0.25734463848442524,
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
      mrr: 0.65625,
      ndcgAtK: 0.43885345635245987,
      groundedness: 1.0,
    },
    B4: {
      baseline: 'B4',
      questions: 8,
      recallAtK: 0.3958333333333333,
      mrr: 0.65625,
      ndcgAtK: 0.43885345635245987,
      groundedness: 1.0,
    },
  },
  L3: {
    B1: {
      baseline: 'B1',
      questions: 3,
      recallAtK: 0.16666666666666666,
      mrr: 0.6666666666666666,
      ndcgAtK: 0.26025336666140114,
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
      recallAtK: 0.08333333333333333,
      mrr: 0.08333333333333333,
      ndcgAtK: 0.05604251209037248,
      groundedness: 1.0,
    },
    B4: {
      baseline: 'B4',
      questions: 3,
      recallAtK: 0.08333333333333333,
      mrr: 0.08333333333333333,
      ndcgAtK: 0.05604251209037248,
      groundedness: 1.0,
    },
  },
};

/** Verbatim from results/eval-h1-bm25-2026-07-30/h1_report.json. */
export const h1Report = {
  decision: 'unsupported',
  threshold: 0.05,
  note: 'H1 is supported only if B4 beats both B2 and B3 by at least 0.05 composite points on both L2 and L3.',
  comparisons: {
    L2: {
      questions: 8,
      b2Composite: 0.44836832986802616,
      b3Composite: 0.6227341974214483,
      b4Composite: 0.6227341974214483,
      marginVsB2: 0.17436586755342215,
      marginVsB3: 0.0,
      supported: false,
    },
    L3: {
      questions: 3,
      b2Composite: 0.3148769465274487,
      b3Composite: 0.3056772946892598,
      b4Composite: 0.3056772946892598,
      marginVsB2: -0.009199651838188883,
      marginVsB3: 0.0,
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
          'B1 sparse baseline top evidence:\n- `src/requests/adapters.py:128` `send`\n- `src/requests/adapters.py:122` `BaseAdapter`\n- `tests/test_requests.py:496` `test_headers_on_session_with_None_are_not_sent`',
        citations: [
          '`src/requests/adapters.py:128`',
          '`src/requests/adapters.py:122`',
          '`tests/test_requests.py:496`',
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
          "A `Session` prepares a request through the `prepare_request` method, which constructs a `PreparedRequest` for transmission. This method merges settings from the `Request` instance with those of the `Session`. Here’s how it works step-by-step:\n\n1. **Extract URL and Method**: The method begins by casting the request's URL and method to the appropriate types.\n\n2. **Handle Cookies**: It checks if the request has cookies. If not, it initializes an empty dictionary. If the cookies are not already in a `CookieJar`, it converts them using `cookiejar_from_dict`.\n\n3. **Merge Cookies**: The method merges the request's cookies with the session's cookies using `merge_cookies`, ensuring that both sets of cookies are included in the final request.\n\n4. **Authentication**: If the request does not explicitly set authentication and the session is configured to trust environment settings, it attempts to retrieve authentication details from the environment using `get_netrc_auth`.\n\n5. **Prepare the Request**: Finally, it creates a `PreparedRequest` instance and calls its `prepare` method, passing in the HTTP method and other necessary parameters (though the full details of this preparation are truncated in the evidence).\n\nThis process ensures that the request is fully configured with the appropriate headers, cookies, and authentication before it is sent out `src/requests/sessions.py:511`.",
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
          'B1 sparse baseline top evidence:\n- `src/requests/adapters.py:403` `build_connection_pool_key_attributes`\n- `src/requests/sessions.py:442` `__init__`\n- `tests/test_requests.py:411` `test_cookie_persists_via_api`',
        citations: [
          '`src/requests/adapters.py:403`',
          '`src/requests/sessions.py:442`',
          '`tests/test_requests.py:411`',
        ],
        groundedness: 1.0,
        recallAtK: 0.5,
        mrr: 0.25,
        ndcgAtK: 0.2640681225725909,
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
          'The flow from `requests.api.request` to `Session.request` involves several steps:\n\n1. **Entry Point**: The process begins at `requests.api.request`, which is the main function for making HTTP requests. This function is responsible for handling the request parameters and initiating the request process `src/requests/api.py:24`.\n\n2. **Session Creation**: When a request is made, it often utilizes a `Session` object. The `Session` class is designed to manage and persist settings across requests, such as cookies and authentication `src/requests/sessions.py:395`, `src/requests/sessions.py:1`.\n\n3. **Preparing the Request**: The `Session` object has a method called `prepare_request`, which constructs a `PreparedRequest` object. This method merges the settings from the `Request` instance with those of the `Session` `src/requests/sessions.py:511`. \n\n4. **Making the Request**: Finally, the `Session` class has a `request` method that is called to send the prepared request. This method handles the actual transmission of the request to the server `src.requests.sessions.Session.request`.\n\nIn summary, the flow can be outlined as:\n- `requests.api.request` → creates or uses a `Session` → calls `Session.prepare_request` → calls `Session.request` to send the request. \n\nThis sequence ensures that all session-specific settings are applied to the request before it is sent.',
        citations: [
          '`src/requests/api.py:24`',
          '`src/requests/sessions.py:395`',
          '`src/requests/sessions.py:1`',
          '`src/requests/sessions.py:511`',
          '`src/requests/sessions.py:557`',
        ],
        groundedness: 1.0,
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
          'B1 sparse baseline top evidence:\n- `src/requests/api.py:24` `request`\n- `src/requests/api.py:137` `put`\n- `src/requests/api.py:154` `patch`',
        citations: [
          '`src/requests/api.py:24`',
          '`src/requests/api.py:137`',
          '`src/requests/api.py:154`',
        ],
        groundedness: 1.0,
        recallAtK: 0.25,
        mrr: 1.0,
        ndcgAtK: 0.3903800499921017,
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
          'B3 hybrid baseline top evidence:\n- `tests/test_requests.py:2649` `test_requests_are_updated_each_time`\n- `tests/test_requests.py:624` `test_respect_proxy_env_on_send_session_prepared_request`\n- `tests/test_requests.py:496` `test_headers_on_session_with_None_are_not_sent`',
        citations: [
          '`tests/test_requests.py:2649`',
          '`tests/test_requests.py:624`',
          '`tests/test_requests.py:496`',
        ],
        groundedness: 1.0,
        recallAtK: 0.0,
        mrr: 0.0,
        ndcgAtK: 0.0,
      },
      B4: {
        answer:
          'The end-to-end send flow from `requests.api.request` to `Session.send` can be outlined as follows:\n\n1. **Request Creation**: The process begins with the creation of a request using `requests.Request`. For example, in the test `test_requests_are_updated_each_time`, a POST request is prepared with `requests.Request("POST", httpbin("post")).prepare()` `tests/test_requests.py:2649`.\n\n2. **Session Initialization**: A `Session` object is created, which is responsible for maintaining certain parameters across requests, such as headers and proxies. In the same test, a `RedirectSession` is instantiated `tests/test_requests.py:2649`.\n\n3. **Sending the Request**: The prepared request is sent using the `session.send(prep)` method. This method is responsible for executing the request and returning a response object. The test checks that the request method is correctly set to "POST" and verifies the last call made by the session `tests/test_requests.py:2649`.\n\n4. **Handling Redirects**: If the response indicates a redirect (like HTTP 303 or 307), the session resolves these redirects using `session.resolve_redirects(r0, prep)`. This method generates new requests for each redirect, which are then sent using `session.send` again, but this time as GET requests `tests/test_requests.py:2649`.\n\n5. **Default Parameters**: When sending requests, the session uses default parameters such as `stream`, `verify`, and `timeout`, which can be overridden if specified `tests/test_requests.py:2649`.\n\n6. **Final Response**: The final response from the server is returned to the caller, completing the request cycle.\n\nThis flow illustrates how `requests.api.request` ultimately leads to `Session.send`, encapsulating the request preparation, sending, and handling of responses, including redirects.',
        citations: [
          '`tests/test_requests.py:2649`',
          '`tests/test_requests.py:2649`',
          '`tests/test_requests.py:2649`',
          '`tests/test_requests.py:2649`',
          '`tests/test_requests.py:2649`',
        ],
        groundedness: 1.0,
        recallAtK: 0.0,
        mrr: 0.0,
        ndcgAtK: 0.0,
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
          'B1 sparse baseline top evidence:\n- `src/requests/sessions.py:134` `get_redirect_target`\n- `src/requests/sessions.py:1` `__module_doc__`\n- `tests/test_requests.py:431` `test_generic_cookiejar_works`',
        citations: [
          '`src/requests/sessions.py:134`',
          '`src/requests/sessions.py:1`',
          '`tests/test_requests.py:431`',
        ],
        groundedness: 1.0,
        recallAtK: 0.25,
        mrr: 1.0,
        ndcgAtK: 0.3903800499921017,
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
          "Redirect handling in the session stack is primarily managed through the `RedirectSession` class, which inherits from `SessionRedirectMixin`. Here's how it works:\n\n1. **Initialization**: The `RedirectSession` class is initialized with a list of redirects (`order_of_redirects`), a maximum number of redirects (`max_redirects`), and other session attributes like `cookies` and `trust_env` `tests/test_requests.py:2608`.\n\n2. **Sending Requests**: When a request is sent using the `send` method, it records the call and builds a response using `build_response`. This method simulates the response based on the current redirect status `tests/test_requests.py:2608`.\n\n3. **Building Responses**: The `build_response` method constructs a `Response` object. It sets the status code based on the next redirect in the list or defaults to 200 if there are no more redirects. It also sets the `Location` header to indicate where to redirect `tests/test_requests.py:2608`.\n\n4. **Redirect Logic**: The `SessionRedirectMixin` provides the `get_redirect_target` method, which is called to determine the next URL to redirect to. This method checks if the response is a redirect and retrieves the `Location` header. It also handles encoding issues with the header `src/requests/sessions.py:127` `src/requests/sessions.py:134`.\n\n5. **Handling Redirects**: The `resolve_redirects` method (not shown in the retrieved evidence but implied) would typically be responsible for following the redirect chain, ensuring that the session can handle multiple redirects as specified by the `max_redirects` limit `tests/test_requests.py:1988`.\n\n6. **Custom Redirect Handling**: The `test_custom_redirect_mixin` demonstrates how a custom session can override the default redirect behavior to handle specific cases, such as malformed responses `tests/test_requests.py:2286`.\n\nIn summary, the `RedirectSession` class manages redirects by simulating responses based on a predefined order, while the `SessionRedirectMixin` provides the necessary methods to interpret and follow those redirects. This structure allows for flexible handling of various redirect scenarios in HTTP requests.",
        citations: [
          '`tests/test_requests.py:2608`',
          '`tests/test_requests.py:2608`',
          '`tests/test_requests.py:2608`',
          '`src/requests/sessions.py:127`',
          '`src/requests/sessions.py:134`',
          '`tests/test_requests.py:1988`',
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
