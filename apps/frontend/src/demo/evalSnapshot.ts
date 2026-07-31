/**
 * H1 evaluation snapshot — generated from `results/eval-h1-l3x12-2026-07-31/`, the full real-model run
 * (Jina v2-base-code (768-dim) + BGE reranker v2-m3 + gpt-4o-mini)
 * against the psf/requests corpus. Verdict written 2026-07-31 — a provenance
 * date, not one the harness recorded; see `results/eval-h1-l3x12-2026-07-31/provenance.json`.
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
  path: 'results/eval-h1-l3x12-2026-07-31/',
  /**
   * When the verdict file was written. Provenance metadata, not harness output —
   * the harness writes no timestamp, so every surface must preserve that distinction.
   * Observation basis and limits: `results/eval-h1-l3x12-2026-07-31/provenance.json`.
   */
  verdictWritten: '2026-07-31',
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
    questions: 33,
    recallAtK: 0.3686868686868687,
    mrr: 0.4732323232323232,
    ndcgAtK: 0.33414665829754703,
    groundedness: 1.0,
  },
  B2: {
    baseline: 'B2',
    questions: 33,
    recallAtK: 0.3404040404040404,
    mrr: 0.39494949494949494,
    ndcgAtK: 0.28644732294592795,
    groundedness: 1.0,
  },
  B3: {
    baseline: 'B3',
    questions: 33,
    recallAtK: 0.40050505050505053,
    mrr: 0.6338383838383839,
    ndcgAtK: 0.41808802012445023,
    groundedness: 1.0,
  },
  B4: {
    baseline: 'B4',
    questions: 33,
    recallAtK: 0.4484848484848485,
    mrr: 0.7626262626262627,
    ndcgAtK: 0.4942552509793038,
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
      mrr: 1.0,
      ndcgAtK: 1.0,
      groundedness: 1.0,
    },
  },
  L2: {
    B1: {
      baseline: 'B1',
      questions: 16,
      recallAtK: 0.37604166666666666,
      mrr: 0.465625,
      ndcgAtK: 0.34429955418408925,
      groundedness: 1.0,
    },
    B2: {
      baseline: 'B2',
      questions: 16,
      recallAtK: 0.29270833333333335,
      mrr: 0.375,
      ndcgAtK: 0.2690606418736563,
      groundedness: 1.0,
    },
    B3: {
      baseline: 'B3',
      questions: 16,
      recallAtK: 0.36666666666666664,
      mrr: 0.6927083333333334,
      ndcgAtK: 0.412923096213062,
      groundedness: 1.0,
    },
    B4: {
      baseline: 'B4',
      questions: 16,
      recallAtK: 0.45,
      mrr: 0.84375,
      ndcgAtK: 0.512084745507928,
      groundedness: 1.0,
    },
  },
  L3: {
    B1: {
      baseline: 'B1',
      questions: 12,
      recallAtK: 0.2625,
      mrr: 0.5277777777777778,
      ndcgAtK: 0.28225975860851393,
      groundedness: 1.0,
    },
    B2: {
      baseline: 'B2',
      questions: 12,
      recallAtK: 0.12916666666666668,
      mrr: 0.3611111111111111,
      ndcgAtK: 0.15567910994068396,
      groundedness: 1.0,
    },
    B3: {
      baseline: 'B3',
      questions: 12,
      recallAtK: 0.19583333333333333,
      mrr: 0.4444444444444444,
      ndcgAtK: 0.21326711426053396,
      groundedness: 1.0,
    },
    B4: {
      baseline: 'B4',
      questions: 12,
      recallAtK: 0.21666666666666667,
      mrr: 0.5555555555555556,
      ndcgAtK: 0.25975561284918136,
      groundedness: 1.0,
    },
  },
};

/** Verbatim from results/eval-h1-l3x12-2026-07-31/h1_report.json. */
export const h1Report = {
  decision: 'unsupported',
  threshold: 0.05,
  note: 'H1 is supported only if B4 beats both B2 and B3 by at least 0.05 composite points on both L2 and L3.',
  comparisons: {
    L2: {
      questions: 16,
      b2Composite: 0.4841922438017474,
      b3Composite: 0.6180745240532655,
      b4Composite: 0.701458686376982,
      marginVsB2: 0.21726644257523464,
      marginVsB3: 0.08338416232371659,
      supported: true,
    },
    L3: {
      questions: 12,
      b2Composite: 0.41148922192961546,
      b3Composite: 0.46338622300957794,
      b4Composite: 0.5079944587678509,
      marginVsB2: 0.09650523683823542,
      marginVsB3: 0.04460823575827294,
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
          "A `Session` prepares a request by using the `prepare_request` method, which constructs a `PreparedRequest` instance for transmission. This method merges settings from the `Request` instance with those of the `Session`. \n\nHere’s how the preparation process works:\n\n1. **Extracting Request Details**: The method retrieves the URL and HTTP method from the `Request` instance.\n2. **Handling Cookies**: It checks if cookies are provided; if not, it initializes an empty dictionary. It then merges these cookies with the session's cookies using the `merge_cookies` function.\n3. **Authentication**: If the request does not explicitly set authentication and the session is configured to trust environment settings, it attempts to retrieve authentication details from the netrc file.\n4. **Creating PreparedRequest**: A new `PreparedRequest` object is created, and the method prepares it with the HTTP method and other necessary details before returning it.\n\nThis process ensures that the request is properly configured with all relevant session settings, including headers, cookies, and authentication details, before it is sent out `src/requests/sessions.py:511`. \n\nThe `Session` class itself is designed to manage these configurations, providing features like cookie persistence and connection pooling `src/requests/sessions.py:395` `src/requests/sessions.py:442`.",
        citations: [
          '`src/requests/sessions.py:511`',
          '`src/requests/sessions.py:395`',
          '`src/requests/sessions.py:442`',
        ],
        groundedness: 1.0,
        recallAtK: 0.5,
        mrr: 1.0,
        ndcgAtK: 0.6131471927654584,
      },
      B4: {
        answer:
          "A `Session` prepares a request through the `prepare_request` method, which constructs a `PreparedRequest` for transmission. This method merges settings from the `Request` instance with those of the `Session`. Here’s how it works step-by-step:\n\n1. **Extract URL and Method**: The method begins by extracting the URL and HTTP method from the `Request` instance.\n\n2. **Handle Cookies**: It checks if the request has cookies. If not, it initializes an empty dictionary. If the cookies are not in the correct format, it converts them into a `CookieJar`.\n\n3. **Merge Cookies**: The method merges the request cookies with the session's cookies using the `merge_cookies` function, ensuring that all relevant cookies are included in the prepared request.\n\n4. **Authentication**: If the request does not specify authentication and the session is configured to trust the environment, it attempts to retrieve authentication details from the environment using `get_netrc_auth`.\n\n5. **Prepare the Request**: Finally, it creates a `PreparedRequest` instance and calls its `prepare` method, passing the HTTP method and other necessary parameters to finalize the request setup.\n\nThis process ensures that the request is fully configured with the appropriate settings before it is sent out `src/requests/sessions.py:511`.",
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
          "The flow from `requests.api.request` to `Session.request` involves several steps:\n\n1. **Starting Point**: The `requests.api.request` function is a high-level function that initiates a request. It is designed to handle various HTTP methods and parameters.\n\n2. **Session Creation**: When a `Session` object is created (e.g., `s = requests.Session()`), it initializes various settings such as headers, authentication, proxies, and cookies, as defined in the `__init__` method of the `Session` class `src/requests/sessions.py:442`.\n\n3. **Preparing the Request**: When a request is made using the session (e.g., `s.get('https://httpbin.org/get')`), the `Session` class's `prepare_request` method is called. This method constructs a `PreparedRequest` object that merges the request's settings with those of the session `src/requests/sessions.py:511`.\n\n4. **Executing the Request**: Finally, the `Session.request` method is invoked to send the prepared request. This method handles the actual transmission of the request, utilizing the session's configurations for cookies, authentication, and other settings.\n\nIn summary, the flow is initiated by `requests.api.request`, which leads to the creation of a `Session`, followed by the preparation of a request using `Session.prepare_request`, and ultimately the execution of the request through `Session.request`.",
        citations: ['`src/requests/sessions.py:442`', '`src/requests/sessions.py:511`'],
        groundedness: 1.0,
        recallAtK: 0.0,
        mrr: 0.0,
        ndcgAtK: 0.0,
      },
      B4: {
        answer:
          'The flow from `requests.api.request` to `Session.request` involves several steps:\n\n1. **Entry Point**: The process begins at `requests.api.request`, which is the main function for making HTTP requests. This function is responsible for handling the request parameters and initiating the request process `src/requests/api.py:24`.\n\n2. **Session Creation**: If a `Session` object is used, it is typically created via `requests.Session()`. This object manages settings such as cookies, authentication, and proxies across multiple requests `src/requests/sessions.py:395`, `src/requests/sessions.py:1`.\n\n3. **Preparing the Request**: When a request is made using a `Session`, the `Session.request` method is called. This method internally calls `Session.prepare_request`, which constructs a `PreparedRequest` object that merges the request settings with those of the session `src/requests/sessions.py:511`, `src.requests.sessions.Session.request`.\n\n4. **Sending the Request**: After preparing the request, the `Session.send` method is invoked to actually send the HTTP request. This method handles the connection and response `src.requests.sessions.Session.send`.\n\n5. **Final Execution**: The response from the server is then returned to the caller, completing the flow from `requests.api.request` to `Session.request`.\n\nIn summary, the flow is as follows:\n- `requests.api.request` → `Session.request` → `Session.prepare_request` → `Session.send` → Response. \n\nThis sequence allows for the management of session-specific settings while making HTTP requests.',
        citations: [
          '`src/requests/api.py:24`',
          '`src/requests/sessions.py:395`',
          '`src/requests/sessions.py:1`',
          '`src/requests/sessions.py:511`',
          '`src/requests/sessions.py:557`',
          '`src/requests/sessions.py:752`',
        ],
        groundedness: 1.0,
        recallAtK: 1.0,
        mrr: 1.0,
        ndcgAtK: 0.8503449055347546,
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
          'The end-to-end send flow from `requests.api.request` to `Session.send` can be outlined as follows:\n\n1. **Request Creation**: The process begins with creating a `Request` object using `requests.Request`. This object encapsulates the HTTP method and URL, among other parameters. For example, in the test `test_requests_are_updated_each_time`, a POST request is prepared with `requests.Request("POST", httpbin("post")).prepare()` `tests/test_requests.py:2649`.\n\n2. **Session Preparation**: A `Session` object is instantiated, which allows for persistent settings across multiple requests. The session can have default headers, authentication, proxies, and other configurations set `src/requests/sessions.py:442`.\n\n3. **Preparing the Request**: The request is prepared using the session\'s `prepare_request` method, which ensures that the request is ready to be sent with any session-specific settings applied. This is demonstrated in the test `test_session_pickling`, where a request is prepared before being sent `tests/test_requests.py:1619`.\n\n4. **Sending the Request**: The prepared request is sent using the `session.send(prep)` method. This method handles the actual transmission of the request to the server. In the `test_requests_are_updated_each_time`, the response from the send call is captured in `r0` `tests/test_requests.py:2649`.\n\n5. **Handling Redirects**: If the response indicates a redirect, the session can resolve these redirects using `session.resolve_redirects(r0, prep)`, which generates new requests for each redirect. Each of these requests is also sent using `session.send` `tests/test_requests.py:2649`.\n\n6. **Final Response**: The final response from the server is returned to the caller, completing the flow from request creation to response handling.\n\nThis flow illustrates how the `requests` library manages HTTP requests through a session, ensuring that configurations are consistently applied and that redirects are handled seamlessly.',
        citations: [
          '`tests/test_requests.py:2649`',
          '`src/requests/sessions.py:442`',
          '`tests/test_requests.py:1619`',
          '`tests/test_requests.py:2649`',
          '`tests/test_requests.py:2649`',
        ],
        groundedness: 1.0,
        recallAtK: 0.0,
        mrr: 0.0,
        ndcgAtK: 0.0,
      },
      B4: {
        answer:
          'The end-to-end send flow from `requests.api.request` to `Session.send` can be summarized as follows:\n\n1. **Request Preparation**: The process begins with the `requests.api.request` function, which is responsible for creating a request. This function typically calls `Session.prepare_request`, which prepares the request by setting up necessary attributes like headers and parameters. This is evident in the test case where a request is prepared using `session.prepare_request(request)` `tests/test_requests.py:624`.\n\n2. **Sending the Request**: Once the request is prepared, it is sent using the `Session.send` method. This method is called with the prepared request object. For example, in the test `test_requests_are_updated_each_time`, the prepared request is sent using `session.send(prep)` `tests/test_requests.py:2649`.\n\n3. **Handling Redirects**: If the response indicates a redirect (like HTTP 303 or 307), the `Session.send` method will handle the redirect by calling `session.resolve_redirects`, which processes the response and prepares a new request for the redirected URL. This is shown in the same test where the `redirect_generator` is used to handle multiple redirects `tests/test_requests.py:2649`.\n\n4. **Final Response**: The final response from the server is returned to the caller of `Session.send`. This response contains the status code and any data returned by the server, which can be accessed through the response object `tests/test_requests.py:2649`.\n\nIn summary, the flow involves preparing a request, sending it through the session, handling any redirects, and finally returning the response. Each of these steps is crucial for the proper functioning of HTTP requests in the `requests` library.',
        citations: [
          '`tests/test_requests.py:624`',
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
          'Redirect handling in the session stack is managed primarily through the `RedirectSession` class, which inherits from `SessionRedirectMixin`. Here\'s how it works:\n\n1. **Initialization**: The `RedirectSession` class initializes with a list of redirects, a call history, a maximum redirect limit, and cookie storage. This setup allows it to track the redirects that need to be processed `tests/test_requests.py:2608`.\n\n2. **Sending Requests**: When a request is sent using the `send` method, it records the call and prepares a response using `build_response`. This method simulates the response based on the redirect status codes provided during initialization. If there are no more redirects, it defaults to a 200 status code `tests/test_requests.py:2608`.\n\n3. **Redirect Logic**: The `SessionRedirectMixin` class provides the `get_redirect_target` method, which is crucial for determining the next URL to follow when a response indicates a redirect (e.g., status codes like 302). This method checks if the response is a redirect and retrieves the "Location" header to find the target URL `src/requests/sessions.py:127` `src/requests/sessions.py:134`. It also handles potential encoding issues with the redirect URL `src/requests/sessions.py:134`.\n\n4. **Custom Handling**: Developers can subclass `RedirectSession` to customize redirect handling. For example, the `test_custom_redirect_mixin` demonstrates how a custom session can manage malformed redirects by overriding the `get_redirect_target` method `tests/test_requests.py:2286`.\n\n5. **Manual Redirects**: The `resolve_redirects` method in the session can be used to manually handle redirects, allowing for partial body reads before following the redirect. This is shown in the `test_manual_redirect_with_partial_body_read`, where the response body is read partially before proceeding with the redirect `tests/test_requests.py:1988`.\n\nOverall, the redirect handling mechanism is designed to be flexible, allowing for both automatic and custom handling of redirects while maintaining a clear structure for tracking and processing them across the session stack.',
        citations: [
          '`tests/test_requests.py:2608`',
          '`tests/test_requests.py:2608`',
          '`src/requests/sessions.py:127`',
          '`src/requests/sessions.py:134`',
          '`src/requests/sessions.py:134`',
          '`tests/test_requests.py:2286`',
          '`tests/test_requests.py:1988`',
        ],
        groundedness: 1.0,
        recallAtK: 0.25,
        mrr: 0.25,
        ndcgAtK: 0.16812753627111746,
      },
      B4: {
        answer:
          "Redirect handling in the session stack is primarily managed through the `RedirectSession` class, which inherits from `SessionRedirectMixin`. Here's how it works:\n\n1. **Initialization**: The `RedirectSession` class is initialized with an order of redirects, which it stores in `self.redirects`. It also maintains a list of calls made (`self.calls`), a maximum number of redirects (`self.max_redirects`), and a cookie jar (`self.cookies`) `tests/test_requests.py:2608`.\n\n2. **Sending Requests**: When a request is sent using the `send` method, it records the call and builds a response using the `build_response` method. This method simulates the response based on the current redirect status, popping the next status code from `self.redirects` `tests/test_requests.py:2608`.\n\n3. **Building Responses**: The `build_response` method constructs a `requests.Response` object. If there are no more redirects, it defaults to a status code of 200. It also sets the `Location` header to indicate where the redirect points `tests/test_requests.py:2608`.\n\n4. **Redirect Logic**: The `SessionRedirectMixin` provides the `get_redirect_target` method, which is called to determine the next URL to redirect to. This method checks if the response is a redirect and retrieves the `Location` header. It also handles encoding issues with the header `src/requests/sessions.py:127` `src/requests/sessions.py:134`.\n\n5. **Handling Redirects**: The redirect handling logic is designed to be extensible. For example, a custom session can override `get_redirect_target` to handle specific cases, such as malformed redirects `tests/test_requests.py:2286`. The tests ensure that the session can follow redirects correctly, even when responses are not standard `tests/test_requests.py:2286` `tests/test_requests.py:1988`.\n\n6. **Iterating Through Redirects**: The session can resolve redirects iteratively, allowing for partial body reads before following a redirect. This is demonstrated in tests where the response body is read partially before proceeding to the next redirect `tests/test_requests.py:1988`.\n\nIn summary, the `RedirectSession` class, through its methods and the mixin, manages the redirect process by tracking calls, building responses, and determining redirect targets, while allowing for customization and handling of edge cases.",
        citations: [
          '`tests/test_requests.py:2608`',
          '`tests/test_requests.py:2608`',
          '`tests/test_requests.py:2608`',
          '`src/requests/sessions.py:127`',
          '`src/requests/sessions.py:134`',
          '`tests/test_requests.py:2286`',
          '`tests/test_requests.py:2286`',
          '`tests/test_requests.py:1988`',
          '`tests/test_requests.py:1988`',
        ],
        groundedness: 1.0,
        recallAtK: 0.25,
        mrr: 0.3333333333333333,
        ndcgAtK: 0.19519002499605084,
      },
    },
  },
];
