/**
 * H1 evaluation snapshot — generated from `results/eval-h1-repeat3-2026-07-31/`, the full real-model run
 * (Jina v2-base-code (768-dim) + BGE reranker v2-m3 + gpt-4o-mini)
 * against the psf/requests corpus. Verdict written 2026-07-31 — a provenance
 * date, not one the harness recorded; see `results/eval-h1-repeat3-2026-07-31/provenance.json`.
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
  path: 'results/eval-h1-repeat3-2026-07-31/',
  /**
   * When the verdict file was written. Provenance metadata, not harness output —
   * the harness writes no timestamp, so every surface must preserve that distinction.
   * Observation basis and limits: `results/eval-h1-repeat3-2026-07-31/provenance.json`.
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
    recallAtK: 0.3898989898989899,
    mrr: 0.5631313131313131,
    ndcgAtK: 0.37630509253349576,
    groundedness: 1.0,
  },
  B2: {
    baseline: 'B2',
    questions: 33,
    recallAtK: 0.4893939393939394,
    mrr: 0.702020202020202,
    ndcgAtK: 0.524372621563125,
    groundedness: 1.0,
  },
  B3: {
    baseline: 'B3',
    questions: 33,
    recallAtK: 0.553030303030303,
    mrr: 0.7954545454545454,
    ndcgAtK: 0.5868901400662542,
    groundedness: 1.0,
  },
  B4: {
    baseline: 'B4',
    questions: 33,
    recallAtK: 0.6378787878787878,
    mrr: 0.8821548821548821,
    ndcgAtK: 0.6638800603331819,
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
      mrr: 1.0,
      ndcgAtK: 1.0,
      groundedness: 1.0,
    },
    B3: {
      baseline: 'B3',
      questions: 5,
      recallAtK: 1.0,
      mrr: 1.0,
      ndcgAtK: 1.0,
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
      recallAtK: 0.40729166666666666,
      mrr: 0.53125,
      ndcgAtK: 0.3838068929721032,
      groundedness: 1.0,
    },
    B2: {
      baseline: 'B2',
      questions: 16,
      recallAtK: 0.49374999999999997,
      mrr: 0.7083333333333334,
      ndcgAtK: 0.5348631089458712,
      groundedness: 1.0,
    },
    B3: {
      baseline: 'B3',
      questions: 16,
      recallAtK: 0.5458333333333333,
      mrr: 0.8697916666666666,
      ndcgAtK: 0.59856398573592,
      groundedness: 1.0,
    },
    B4: {
      baseline: 'B4',
      questions: 16,
      recallAtK: 0.61875,
      mrr: 0.8854166666666666,
      ndcgAtK: 0.6417363127605823,
      groundedness: 1.0,
    },
  },
  L3: {
    B1: {
      baseline: 'B1',
      questions: 12,
      recallAtK: 0.2791666666666667,
      mrr: 0.6875,
      ndcgAtK: 0.34551900104002087,
      groundedness: 1.0,
    },
    B2: {
      baseline: 'B2',
      questions: 12,
      recallAtK: 0.2708333333333333,
      mrr: 0.5694444444444444,
      ndcgAtK: 0.31220723070409884,
      groundedness: 1.0,
    },
    B3: {
      baseline: 'B3',
      questions: 12,
      recallAtK: 0.3763888888888889,
      mrr: 0.6111111111111112,
      ndcgAtK: 0.39919590420097223,
      groundedness: 1.0,
    },
    B4: {
      baseline: 'B4',
      questions: 12,
      recallAtK: 0.5125,
      mrr: 0.8287037037037037,
      ndcgAtK: 0.5533550822354739,
      groundedness: 1.0,
    },
  },
};

/** Verbatim from results/eval-h1-repeat3-2026-07-31/h1_report.json. */
export const h1Report = {
  decision: 'unsupported',
  threshold: 0.05,
  note: 'H1 is supported only if B4 beats both B2 and B3 by at least 0.05 composite points on both L2 and L3.',
  comparisons: {
    L2: {
      questions: 16,
      b2Composite: 0.5789821474264015,
      b3Composite: 0.67139632857864,
      b4Composite: 0.7153009931424164,
      marginVsB2: 0.13631884571601482,
      marginVsB3: 0.0439046645637764,
      supported: false,
    },
    L3: {
      questions: 12,
      b2Composite: 0.38416166949395886,
      b3Composite: 0.46223196806699074,
      b4Composite: 0.6315195953130592,
      marginVsB2: 0.24735792581910038,
      marginVsB3: 0.1692876272460685,
      supported: true,
    },
  } satisfies Record<Taxonomy, H1Comparison>,
  repeats: 3,
  perRepeat: [
    {
      repeat: 1,
      decision: 'unsupported',
      marginVsB3: {
        L2: 0.0376010164973648,
        L3: 0.13163111864299415,
      },
    },
    {
      repeat: 2,
      decision: 'unsupported',
      marginVsB3: {
        L2: 0.005666266874163828,
        L3: 0.17512679754643073,
      },
    },
    {
      repeat: 3,
      decision: 'supported',
      marginVsB3: {
        L2: 0.08844671031980045,
        L3: 0.20110496554878038,
      },
    },
  ],
};

/**
 * B0 — GitHub code search, an external keyword control.
 *
 * Separate from the ladder above on purpose. It retrieves FILES, not chunks:
 * the API returns a path and no line, so it has no chunk-level result and is
 * compared on the file-level metric every arm records. And it queries a live
 * external index, so unlike every other figure here it cannot be regenerated
 * from committed bytes — only re-queried, against an index that may have moved.
 *
 * `null` means unmeasured, which is a blank rather than a zero.
 */
export const externalKeywordBaseline = {
  runPath: 'results/eval-b0-2026-07-31/',
  questions: 33,
  fileRecallAtK: 0.30808080808080807,
  byLevel: {
    L1: 0.6,
    L2: 0.3645833333333333,
    L3: 0.1111111111111111,
  },
  reproducible: false,
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
          'B1 sparse baseline top evidence:\n- `src/requests/adapters.py:128` `send`\n- `src/requests/adapters.py:122` `BaseAdapter`\n- `src/requests/api.py:24` `request`',
        citations: [
          '`src/requests/adapters.py:128`',
          '`src/requests/adapters.py:122`',
          '`src/requests/api.py:24`',
        ],
        groundedness: 1.0,
        recallAtK: 0.0,
        mrr: 0.0,
        ndcgAtK: 0.0,
      },
      B2: {
        answer:
          "A `Session` prepares a request through the `prepare_request` method. This method constructs a `PreparedRequest` by merging settings from the `Request` instance with those of the `Session`. Here’s how it works:\n\n1. **Input Request**: The method takes a `Request` instance as input.\n2. **Cookie Handling**: It initializes cookies from the request and merges them with the session's cookies using the `merge_cookies` function.\n3. **Authentication**: If the request does not explicitly set authentication and the session trusts the environment, it retrieves authentication details from the network configuration.\n4. **PreparedRequest Creation**: A new `PreparedRequest` instance is created, and the method prepares it with the HTTP method and other necessary details before returning it.\n\nThe `PreparedRequest` object contains all the information needed for transmission, including the HTTP method, URL, headers, and cookies, ensuring that the request is ready to be sent by the session's `send` method `src/requests/sessions.py:511`, `src/requests/models.py:378`, `src/requests/sessions.py:752`. \n\nIn summary, the `Session` uses `prepare_request` to create a `PreparedRequest` that encapsulates all necessary configurations for the HTTP request.",
        citations: [
          '`src/requests/sessions.py:511`',
          '`src/requests/models.py:378`',
          '`src/requests/sessions.py:752`',
        ],
        groundedness: 1.0,
        recallAtK: 0.5,
        mrr: 1.0,
        ndcgAtK: 0.6131471927654584,
      },
      B3: {
        answer:
          "A `Session` prepares a request by using the `prepare_request` method, which constructs a `PreparedRequest` for transmission. This method merges settings from the `Request` instance with those of the `Session`. \n\nHere's how it works:\n\n1. **Extract Request Details**: The method retrieves the URL and HTTP method from the `Request` instance.\n2. **Handle Cookies**: It checks for cookies in the request and merges them with the session's cookies using the `merge_cookies` function.\n3. **Authentication**: If no authentication is explicitly set, it checks the environment for basic authentication credentials.\n4. **Prepare the Request**: Finally, it creates a `PreparedRequest` and calls its `prepare` method, passing in the method, URL, headers, and other relevant data from the `Request` instance.\n\nThe `Session` class itself initializes various attributes, such as headers, authentication, proxies, and hooks, which are used during the request preparation process `src/requests/sessions.py:511`, `src/requests/sessions.py:442`, `src/requests/sessions.py:395`. The `Request` class also has a `prepare` method that constructs a `PreparedRequest` by gathering all necessary information from the request parameters `src/requests/models.py:284`, `src/requests/models.py:360`. \n\nIn summary, the `Session` class centralizes the configuration and state management for requests, ensuring that each request is prepared with the appropriate settings before being sent.",
        citations: [
          '`src/requests/sessions.py:511`',
          '`src/requests/sessions.py:442`',
          '`src/requests/sessions.py:395`',
          '`src/requests/models.py:284`',
          '`src/requests/models.py:360`',
        ],
        groundedness: 1.0,
        recallAtK: 0.5,
        mrr: 1.0,
        ndcgAtK: 0.6131471927654584,
      },
      B4: {
        answer:
          'A `Session` prepares a request through the `request` method, which constructs a `Request` object, prepares it, and sends it. This process involves several steps:\n\n1. **Request Construction**: The `request` method takes parameters such as `method`, `url`, `params`, `data`, `headers`, and others to create a `Request` object `src.requests.sessions.Session.request`.\n\n2. **Preparation of the Request**: The `prepare_request` method is called, which constructs a `PreparedRequest` for transmission. This method merges settings from the `Request` instance with those of the `Session`. It handles cookies by merging them with session cookies and sets up authentication if not explicitly provided `src.requests.sessions.Session.prepare_request` `src/requests/sessions.py:511`.\n\n3. **Sending the Request**: The `send` method is then invoked with the `PreparedRequest`. This method ensures that the request is properly prepared and sets defaults for parameters like `stream`, `verify`, and `cert`. It also resolves proxies and checks if the request is indeed a `PreparedRequest` `src.requests.sessions.Session.send` `src/requests/sessions.py:752`.\n\n4. **Handling Redirects**: If the request is redirected, methods like `rebuild_auth` and `rebuild_method` are used to manage authentication headers and adjust the request method as necessary based on the response status code `src.requests.sessions.SessionRedirectMixin.rebuild_auth` `src/requests/sessions.py:370`.\n\nIn summary, the `Session` prepares a request by constructing it with necessary parameters, preparing it with session-specific settings, and then sending it while managing any redirects appropriately.',
        citations: [
          '`src/requests/sessions.py:557`',
          '`src/requests/sessions.py:511`',
          '`src/requests/sessions.py:511`',
          '`src/requests/sessions.py:752`',
          '`src/requests/sessions.py:752`',
          '`src/requests/sessions.py:309`',
          '`src/requests/sessions.py:370`',
        ],
        groundedness: 1.0,
        recallAtK: 0.5,
        mrr: 0.5,
        ndcgAtK: 0.38685280723454163,
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
          'B1 sparse baseline top evidence:\n- `src/requests/adapters.py:403` `build_connection_pool_key_attributes`\n- `src/requests/sessions.py:442` `__init__`\n- `src/requests/api.py:24` `request`',
        citations: [
          '`src/requests/adapters.py:403`',
          '`src/requests/sessions.py:442`',
          '`src/requests/api.py:24`',
        ],
        groundedness: 1.0,
        recallAtK: 0.5,
        mrr: 0.3333333333333333,
        ndcgAtK: 0.3065735963827292,
      },
      B2: {
        answer:
          'The flow from `requests.api.request` to `Session.request` involves several components of the Requests library.\n\n1. **Entry Point**: The `requests.api.request` function serves as the main entry point for making HTTP requests. This function is defined in the `requests.api` module `src/requests/api.py:1`.\n\n2. **Session Creation**: When a request is made, it often utilizes a `Session` object to manage settings like cookies and authentication. The `Session` class is defined in the `requests.sessions` module `src/requests/sessions.py:395`. \n\n3. **Request Preparation**: The `Session` object can prepare a request using the `Request` class, which is then converted into a `PreparedRequest` object. This is done through the `prepare()` method of the `Request` class `src/requests/models.py:378`.\n\n4. **Sending the Request**: Finally, the `Session` object sends the prepared request using its `send()` method, which handles the actual transmission of the HTTP request to the server `src/requests/sessions.py:395`.\n\nIn summary, the flow is as follows:\n- `requests.api.request` calls the `Session` class to create a session.\n- The session prepares a request using the `Request` class.\n- The prepared request is sent via the `Session.send()` method. \n\nThis structure allows for efficient management of HTTP requests and responses within the Requests library.',
        citations: [
          '`src/requests/api.py:1`',
          '`src/requests/sessions.py:395`',
          '`src/requests/models.py:378`',
          '`src/requests/sessions.py:395`',
        ],
        groundedness: 1.0,
        recallAtK: 0.0,
        mrr: 0.0,
        ndcgAtK: 0.0,
      },
      B3: {
        answer:
          "The flow from `requests.api.request` to `Session.request` involves several steps:\n\n1. **Starting Point**: The `requests.api.request` function is typically the entry point for making HTTP requests in the Requests library. This function is designed to handle various HTTP methods and parameters.\n\n2. **Session Creation**: When a `Session` object is created (e.g., `s = requests.Session()`), it initializes various settings such as headers, authentication, proxies, and cookies that will be used for all requests made through that session. This is done in the `__init__` method of the `Session` class `src/requests/sessions.py:442`.\n\n3. **Preparing the Request**: When a request is made using the session (e.g., `s.get('https://httpbin.org/get')`), the `Session.request` method is called internally. This method prepares the request by merging the session's settings with those of the individual request. The preparation is handled by the `prepare_request` method, which constructs a `PreparedRequest` object that includes all necessary configurations `src/requests/sessions.py:511`.\n\n4. **Executing the Request**: After preparation, the `PreparedRequest` is sent over the network, and the response is returned to the user.\n\nIn summary, the flow is as follows: `requests.api.request` → `Session` (creation and initialization) → `Session.request` → `prepare_request` (preparation of the request). Each step builds upon the previous one to ensure that the request is properly configured and executed.",
        citations: ['`src/requests/sessions.py:442`', '`src/requests/sessions.py:511`'],
        groundedness: 1.0,
        recallAtK: 0.0,
        mrr: 0.0,
        ndcgAtK: 0.0,
      },
      B4: {
        answer:
          "The flow from `requests.api.request` to `Session.request` involves the following steps:\n\n1. **Entry Point**: The function `requests.api.request` serves as the entry point for making HTTP requests. It is defined in `src/requests/api.py` `src.requests.api.request`.\n\n2. **Session Creation**: Within `requests.api.request`, a `Session` object is typically created or retrieved. This is done through the `session()` function, which returns an instance of `Session` `src.requests.sessions.session`.\n\n3. **Calling `Session.request`**: The `Session` object has a method called `request`, which is defined in the `Session` class. This method constructs and sends the HTTP request, returning a `Response` object `src.requests.sessions.Session.request`.\n\n4. **Request Preparation**: Inside the `Session.request` method, the request is prepared using the `prepare_request` method, which merges session settings with the request parameters `src.requests.sessions.Session.prepare_request`.\n\n5. **Sending the Request**: Finally, the prepared request is sent, and the response is returned to the caller of `Session.request`.\n\nThis flow illustrates how `requests.api.request` ultimately delegates the actual request handling to the `Session` class's `request` method, leveraging the session's configuration and capabilities.",
        citations: [
          '`src/requests/api.py:24`',
          '`src/requests/sessions.py:908`',
          '`src/requests/sessions.py:557`',
          '`src/requests/sessions.py:511`',
        ],
        groundedness: 1.0,
        recallAtK: 0.8333333333333334,
        mrr: 0.8333333333333334,
        ndcgAtK: 0.7420981285103055,
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
          "The end-to-end send flow from `requests.api.request` to `Session.send` involves several steps:\n\n1. **Starting Point - `requests.api.request`**: This function is typically the entry point for making a request. It prepares the request and ultimately calls the `Session.send` method to execute it.\n\n2. **Session Initialization**: When a `Session` object is created (e.g., `s = requests.Session()`), it initializes various attributes such as headers, cookies, and proxies, which are used throughout the request process `src/requests/sessions.py:395`.\n\n3. **Preparing the Request**: The `requests.api.request` function prepares a `PreparedRequest` object, which encapsulates all the details of the request (like method, URL, headers, etc.).\n\n4. **Calling `Session.send`**: Once the request is prepared, the `Session.send` method is invoked with the `PreparedRequest` object as an argument. This method is responsible for sending the request and returning the response `src/requests/sessions.py:132`.\n\n5. **Inside `Session.send`**: \n   - The method first sets default parameters for the request, such as `stream`, `verify`, and `cert`, which can be overridden by the caller `src/requests/sessions.py:752`.\n   - It checks if the request is indeed a `PreparedRequest` and raises an error if it is not.\n   - The method then retrieves the appropriate adapter for the request's URL, which handles the actual sending of the request over the network.\n\n6. **Handling the Response**: After sending the request, `Session.send` processes the response, including handling any potential exceptions that may arise, such as `ChunkedEncodingError` or `StreamConsumedError` if the response content is improperly formatted or already consumed `src/requests/exceptions.py:130` `src/requests/exceptions.py:138`.\n\nIn summary, the flow from `requests.api.request` to `Session.send` involves preparing the request, initializing a session, and executing the request through the session's send method, which manages the details of the HTTP transaction.",
        citations: [
          '`src/requests/sessions.py:395`',
          '`src/requests/sessions.py:132`',
          '`src/requests/sessions.py:752`',
          '`src/requests/exceptions.py:130`',
          '`src/requests/exceptions.py:138`',
        ],
        groundedness: 1.0,
        recallAtK: 0.25,
        mrr: 0.3888888888888889,
        ndcgAtK: 0.21222747957761057,
      },
      B3: {
        answer:
          "The end-to-end send flow from `requests.api.request` to `Session.send` involves several key components and steps:\n\n1. **Request Creation**: The process begins with creating a `Request` object, which is then prepared into a `PreparedRequest`. This is done using the `prepare()` method of the `Request` class. The `PreparedRequest` contains all the necessary information (like method, URL, headers, etc.) that will be sent to the server `src/requests/models.py:378`.\n\n2. **Session Initialization**: A `Session` object is created, which manages settings like headers, authentication, and proxies that will be used for all requests made through that session `src/requests/sessions.py:442` `src/requests/sessions.py:395`.\n\n3. **Sending the Request**: The `send()` method of the `Session` class is called with the `PreparedRequest` as an argument. This method sets up various parameters (like stream, verify, and proxies) and ensures that the request is indeed a `PreparedRequest` `src/requests/sessions.py:752`.\n\n4. **Adapter Selection**: Inside the `send()` method, the appropriate adapter for the request is determined using the `get_adapter()` method, which is responsible for handling the actual sending of the request `src/requests/sessions.py:752`.\n\n5. **Final Sending**: The `send()` method of the selected adapter is then called with the `PreparedRequest`. This method is responsible for executing the request and returning a `Response` object `src/requests/adapters.py:634`.\n\nIn summary, the flow is as follows: create a `Request` → prepare it into a `PreparedRequest` → initialize a `Session` → call `Session.send()` with the `PreparedRequest` → the adapter's `send()` method executes the request and returns a response.",
        citations: [
          '`src/requests/models.py:378`',
          '`src/requests/sessions.py:442`',
          '`src/requests/sessions.py:395`',
          '`src/requests/sessions.py:752`',
          '`src/requests/sessions.py:752`',
          '`src/requests/adapters.py:634`',
        ],
        groundedness: 1.0,
        recallAtK: 0.25,
        mrr: 0.25,
        ndcgAtK: 0.16812753627111746,
      },
      B4: {
        answer:
          "The end-to-end send flow from `requests.api.request` to `Session.send` involves several steps:\n\n1. **Request Creation**: The process begins with the `requests.api.request` function, which constructs a `Request` object based on the provided parameters such as method, URL, headers, etc. This function is defined in `src/requests/api.py` `src.requests.api.request`.\n\n2. **Preparing the Request**: The `Request` object is then prepared into a `PreparedRequest` object using the `prepare()` method. This `PreparedRequest` contains all the necessary information (like method, URL, headers, etc.) that will be sent to the server `src/requests/models.py:378`.\n\n3. **Session Initialization**: A `Session` object is created, which is responsible for managing the settings and state for the requests. The `Session` class is defined in `src/requests/sessions.py` `src.requests.sessions.Session`.\n\n4. **Sending the Request**: The `send()` method of the `Session` class is called with the `PreparedRequest` as an argument. This method is defined in `src/requests/sessions.py` `src.requests.sessions.Session.send`. It handles various configurations such as stream, verify, and proxies, and ensures that the request is indeed a `PreparedRequest` `src.requests.sessions.Session.send`.\n\n5. **Handling Redirects and Hooks**: Inside the `send()` method, it sets up necessary variables for handling redirects and hooks, and retrieves the appropriate adapter for the request `src.requests.sessions.Session.send`. The method also checks for any potential redirects that may occur during the request `src.requests.sessions.SessionRedirectMixin.send`.\n\n6. **Final Execution**: Finally, the request is dispatched through the selected adapter, which handles the actual sending of the request to the server and returns a `Response` object containing the server's response `src.requests.sessions.Session.send`.\n\nThis flow illustrates how a request is constructed, prepared, and sent using the `requests` library, leveraging the `Session` class for managing configurations and state.",
        citations: [
          '`src/requests/api.py:24`',
          '`src/requests/models.py:378`',
          '`src/requests/sessions.py:395`',
          '`src/requests/sessions.py:752`',
          '`src/requests/sessions.py:752`',
          '`src/requests/sessions.py:752`',
          '`src/requests/sessions.py:132`',
          '`src/requests/sessions.py:752`',
        ],
        groundedness: 1.0,
        recallAtK: 0.5833333333333334,
        mrr: 1.0,
        ndcgAtK: 0.6088474590058209,
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
          'B1 sparse baseline top evidence:\n- `src/requests/sessions.py:134` `get_redirect_target`\n- `src/requests/sessions.py:1` `__module_doc__`\n- `src/requests/sessions.py:442` `__init__`',
        citations: [
          '`src/requests/sessions.py:134`',
          '`src/requests/sessions.py:1`',
          '`src/requests/sessions.py:442`',
        ],
        groundedness: 1.0,
        recallAtK: 0.25,
        mrr: 1.0,
        ndcgAtK: 0.3903800499921017,
      },
      B2: {
        answer:
          'Redirect handling in the session stack is primarily managed by the `SessionRedirectMixin` class, which is responsible for processing HTTP redirects. Here\'s how it works:\n\n1. **Redirect Detection**: The `is_redirect` method in the `Response` class checks if a response is a valid HTTP redirect by verifying the presence of a "location" header and a status code that indicates a redirect (defined in `REDIRECT_STATI`) `src/requests/models.py:877`.\n\n2. **Getting Redirect Target**: The `get_redirect_target` method in `SessionRedirectMixin` retrieves the redirect URI from the response. It is called at least once for the original response and at least twice for each subsequent redirect. If the response is a redirect, it extracts the "location" header, encodes it in `latin1`, and then decodes it to a native string (likely UTF-8) to handle potential encoding issues `src/requests/sessions.py:127` `src/requests/sessions.py:134`.\n\n3. **Handling Redirects**: The `handle_redirect` method resets a counter (`num_401_calls`) whenever a redirect occurs. This is useful for managing authentication retries in the context of redirects `src/requests/auth.py:268`.\n\n4. **Permanent Redirects**: The `is_permanent_redirect` method checks if the response is a permanent redirect, which is a specific type of redirect that indicates the resource has moved permanently `src/requests/models.py:884`.\n\nOverall, the session stack utilizes these methods to effectively manage and process redirects, ensuring that the correct target is followed and that any necessary state (like authentication attempts) is reset appropriately.',
        citations: [
          '`src/requests/models.py:877`',
          '`src/requests/sessions.py:127`',
          '`src/requests/sessions.py:134`',
          '`src/requests/auth.py:268`',
          '`src/requests/models.py:884`',
        ],
        groundedness: 1.0,
        recallAtK: 0.25,
        mrr: 0.3333333333333333,
        ndcgAtK: 0.19519002499605084,
      },
      B3: {
        answer:
          'Redirect handling in the session stack is primarily managed through the `SessionRedirectMixin` class and its associated methods. Here\'s how it works:\n\n1. **Redirect Detection**: The `is_redirect` method in the `Response` class checks if a response is a valid HTTP redirect by verifying the presence of a "location" header and a status code that indicates a redirect (defined in `REDIRECT_STATI`) `src/requests/models.py:877`.\n\n2. **Getting Redirect Targets**: The `get_redirect_target` method in `SessionRedirectMixin` processes the response to extract the redirect URI. It is called at least once for the original response and at least twice for each subsequent redirect. If the response is a redirect, it retrieves the "location" header, encodes it in `latin1`, and then decodes it to a native string in UTF-8 `src/requests/sessions.py:127` `src/requests/sessions.py:134`.\n\n3. **Handling Redirects**: The `handle_redirect` method resets a counter (`num_401_calls`) when a redirect occurs. This is useful for managing authentication retries in the context of redirects `src/requests/auth.py:268`.\n\n4. **Permanent Redirects**: The `is_permanent_redirect` method identifies if a response is a permanent redirect by checking specific status codes (like 301 or 308) `src/requests/models.py:884`.\n\nIn summary, the session stack handles redirects by detecting them through response headers, extracting the target URI, and managing state related to authentication retries, ensuring a smooth flow through multiple redirects.',
        citations: [
          '`src/requests/models.py:877`',
          '`src/requests/sessions.py:127`',
          '`src/requests/sessions.py:134`',
          '`src/requests/auth.py:268`',
          '`src/requests/models.py:884`',
        ],
        groundedness: 1.0,
        recallAtK: 0.25,
        mrr: 0.3333333333333333,
        ndcgAtK: 0.19519002499605084,
      },
      B4: {
        answer:
          'Redirect handling in the session stack is managed primarily through the `SessionRedirectMixin` class, which provides methods to process HTTP redirects effectively.\n\n1. **Redirect Target Retrieval**: The method `get_redirect_target` is responsible for extracting the redirect URI from the response. It checks if the response is a redirect and retrieves the "location" header. This method is called at least once for the original response and at least twice for each subsequent redirect response, allowing it to handle multiple redirects in a session `src.requests.sessions.SessionRedirectMixin` `src.requests.sessions.SessionRedirectMixin.get_redirect_target`.\n\n2. **Resolving Redirects**: The `resolve_redirects` method orchestrates the redirect process. It maintains a history of responses to track the redirects that have occurred. It uses `get_redirect_target` to get the next URL to redirect to and prepares a new request based on the previous one. If the maximum number of redirects (`max_redirects`) is exceeded, it raises a `TooManyRedirects` exception `src.requests.sessions.SessionRedirectMixin.resolve_redirects` `src/requests/sessions.py:186`.\n\n3. **Method Rebuilding**: The `rebuild_method` function adjusts the HTTP method of the request based on the response status code. For instance, if a 302 or 301 status code is received, it changes the method to GET, which is a common behavior in web browsers `src/requests/sessions.py:370`.\n\n4. **Authorization Handling**: The method `should_strip_auth` determines whether to remove the Authorization header when redirecting. It checks if the hostname has changed or if the scheme has switched from HTTP to HTTPS, which affects whether the credentials should be sent to the new location `src/requests/sessions.py:154`.\n\n5. **Session Integration**: The `Session` class inherits from `SessionRedirectMixin`, allowing it to utilize these redirect handling capabilities seamlessly. This integration ensures that all requests made through a session can handle redirects according to the defined logic `src.requests.sessions.Session` `src/requests/sessions.py:395`.\n\nOverall, the redirect handling mechanism in this codebase is designed to manage multiple redirects efficiently while adhering to HTTP standards and common browser behaviors.',
        citations: [
          '`src/requests/sessions.py:127`',
          '`src/requests/sessions.py:134`',
          '`src/requests/sessions.py:186`',
          '`src/requests/sessions.py:186`',
          '`src/requests/sessions.py:370`',
          '`src/requests/sessions.py:154`',
          '`src/requests/sessions.py:395`',
          '`src/requests/sessions.py:395`',
        ],
        groundedness: 1.0,
        recallAtK: 0.75,
        mrr: 0.6666666666666666,
        ndcgAtK: 0.663278012977707,
      },
    },
  },
];
