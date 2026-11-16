// Curated author labels, distinct from engine-bound experimental context.
export const PROJECTION_EXAMPLES = [
  {
    "id": "scoring-change",
    "title": "A scoring change reuses an observation",
    "description": "Authored software continuation. The scoring input changed; observation evidence was reused while analysis and confirmation ran. No robot trial.",
    "group": "Dependency decisions",
    "sourceCommit": "12afda5f7e388744a0f6d64ac585663ea7f48112",
    "summary": {
      "file": "scoring-change.summary.json",
      "sha256": "683f6ae72be7c7d1bee64f7c5f8b9b1a423d771ac9c43a98a6467f44bdfa6531"
    },
    "measurement": null,
    "explanation": {
      "file": "scoring-change.explanation.json",
      "sha256": "0bef90700cdc973a20280e87d0b1060e32c7a965d1c0a4d00ffec7988d8b8d18"
    }
  },
  {
    "id": "unattempted-reuse",
    "title": "Reuse planned, never attempted",
    "description": "Authored software control. An unknown population input blocked execution. Planned reusable checks remain unattempted.",
    "group": "Dependency decisions",
    "sourceCommit": "12afda5f7e388744a0f6d64ac585663ea7f48112",
    "summary": {
      "file": "unattempted-reuse.summary.json",
      "sha256": "763d49e1a0d15906f0b7aa1ec85b451e38ac1d1d7cb9ef274098cefaf13e9278"
    },
    "measurement": null,
    "explanation": {
      "file": "unattempted-reuse.explanation.json",
      "sha256": "9084d40db7192c99ef5c559f734f6242b8b76a07fa89ce5fb9a9ff29fe883ed0"
    }
  },
  {
    "id": "missing-history",
    "title": "A previous receipt needs a new check",
    "description": "Authored software control with a removed historical observation artifact. The public explanation deliberately withholds diagnostic text; receipt presence alone does not establish reusable evidence.",
    "group": "Dependency decisions",
    "sourceCommit": "12afda5f7e388744a0f6d64ac585663ea7f48112",
    "summary": {
      "file": "missing-history.summary.json",
      "sha256": "6a61fab49965437c94f1c8a8be106219a66358068a9357b172fd4a68b635eb82"
    },
    "measurement": null,
    "explanation": {
      "file": "missing-history.explanation.json",
      "sha256": "743814d0a2593a937bc348949776a17a0c064e2ac655a3d0a92c0fe413e9a873"
    }
  },
  {
    "id": "nonzero-refused",
    "title": "A tiny nonzero value is refused",
    "description": "Authored numeric-transport control using 1e-400. Its observation read failed before assessment; this example context is not a diagnosis of arbitrary failed imports.",
    "group": "Numeric transport controls",
    "sourceCommit": "298a0a1b271afbaa8edd960800d5193583ae11be",
    "summary": {
      "file": "nonzero-refused.summary.json",
      "sha256": "078ee43e97feda7f75ad430de4ba5c19d87b1be9db2aaa326e2800fa142238e1"
    },
    "measurement": {
      "file": "nonzero-refused.measurement.json",
      "sha256": "68f7c6af1bd775ae0562c8c7c920a6d8a54223229a176933d269bd263678a628"
    },
    "explanation": {
      "file": "nonzero-refused.explanation.json",
      "sha256": "710b84aedc1d1ae96cc27309be8503331849e49c7e8889d8ae8203a82d2d9c08"
    }
  },
  {
    "id": "literal-zero",
    "title": "Literal zero retains its meaning",
    "description": "Authored numeric-transport control using 0e-400. The declared equality is supported and agrees with the saved assessment. This is a software control, not a task or hardware result.",
    "group": "Numeric transport controls",
    "sourceCommit": "298a0a1b271afbaa8edd960800d5193583ae11be",
    "summary": {
      "file": "literal-zero.summary.json",
      "sha256": "28a236aa144e8649bf9d014fd1d7d8722fdc27fadc48f21d1663f3bb90f78d83"
    },
    "measurement": {
      "file": "literal-zero.measurement.json",
      "sha256": "8a34fd88d00ec80af0982687bcd0b3207797647b083b82e206ba1dd91b4bb171"
    },
    "explanation": {
      "file": "literal-zero.explanation.json",
      "sha256": "04ffb4f428bc9c5c0dd561f841e01089359be8c4845d876270e332f031e02415"
    }
  },
  {
    "id": "recorded-relation",
    "title": "A recorded relation holds",
    "description": "Analysis of retained Newton records. Lower tracked allocation and equal sampled payloads; the solver remains unconverged. No new simulator run.",
    "group": "Measurement records",
    "sourceCommit": "6e7db24bfdfcbb4bf1b6ffc7f88c5e1a49df1816",
    "summary": {
      "file": "recorded-relation.summary.json",
      "sha256": "6f7fa41e214d2ab98f44d08296bc4b8a8ae8f50560359d4d53422a84a56ec95b"
    },
    "measurement": {
      "file": "recorded-relation.measurement.json",
      "sha256": "8b9cfa1445bb44816a0944ceb52e109b624858aab6a939dd15033e069a0acf38"
    },
    "explanation": null
  },
  {
    "id": "rejected-relation",
    "title": "A recorded relation fails",
    "description": "An exposed scoring control over historical Newton data. A matching rejection is a legitimate result.",
    "group": "Measurement records",
    "sourceCommit": "6e7db24bfdfcbb4bf1b6ffc7f88c5e1a49df1816",
    "summary": {
      "file": "rejected-relation.summary.json",
      "sha256": "7f2673cbc9114304ea5592e1b50a2a3b59bec9e5e30bb8934a3c754b85eb5ccc"
    },
    "measurement": {
      "file": "rejected-relation.measurement.json",
      "sha256": "f387c0059053ace09e2d592a109642b957feab78a441dc617c6c86b712dd79ac"
    },
    "explanation": null
  },
  {
    "id": "claim-disagreement",
    "title": "A saved claim disagrees",
    "description": "Authored adversarial software control. The handler deliberately saved a supported verdict over a rejected relation.",
    "group": "Measurement records",
    "sourceCommit": "6e7db24bfdfcbb4bf1b6ffc7f88c5e1a49df1816",
    "summary": {
      "file": "claim-disagreement.summary.json",
      "sha256": "91ae7f23f07f8f999243f334a3fa1b4e313ce749c829d545a6793ea4b7b3a642"
    },
    "measurement": {
      "file": "claim-disagreement.measurement.json",
      "sha256": "e4ae21cd282d42277694089d5d6921f1095326cab691d269355b4239e4f211aa"
    },
    "explanation": null
  },
  {
    "id": "unresolved-semantics",
    "title": "Measurement meaning is unresolved",
    "description": "An exposed metric-substitution control. The recorded measurement does not meet the declared contract's semantics.",
    "group": "Measurement records",
    "sourceCommit": "6e7db24bfdfcbb4bf1b6ffc7f88c5e1a49df1816",
    "summary": {
      "file": "unresolved-semantics.summary.json",
      "sha256": "1492306b27bc8bbd1819000ffcabb3581fe304846ac2423bca440d87c87955e1"
    },
    "measurement": {
      "file": "unresolved-semantics.measurement.json",
      "sha256": "1e163abfe89a85cb2cb5cb5fadaea1e64bc625eda40e69145b6ca050b75f2ce6"
    },
    "explanation": null
  },
  {
    "id": "incomplete-execution",
    "title": "An execution is incomplete",
    "description": "An exposed incomplete-data control over retained Newton records. No complete measurement assessment is released.",
    "group": "Measurement records",
    "sourceCommit": "6e7db24bfdfcbb4bf1b6ffc7f88c5e1a49df1816",
    "summary": {
      "file": "incomplete-execution.summary.json",
      "sha256": "1a5df2057a7c4b3825f4685623ba79e5f4039118ab6e121af8dbdd75ded54de8"
    },
    "measurement": {
      "file": "incomplete-execution.measurement.json",
      "sha256": "23522a9c54acb17b04cfef9ae6a071e40035afc5c0fa78c76fd21c159488324e"
    },
    "explanation": null
  },
  {
    "id": "acquisition-failed",
    "title": "Input acquisition failed",
    "description": "Authored software execution control. Input acquisition failed before any check was attempted.",
    "group": "Measurement records",
    "sourceCommit": "6e7db24bfdfcbb4bf1b6ffc7f88c5e1a49df1816",
    "summary": {
      "file": "acquisition-failed.summary.json",
      "sha256": "0527253adb42caf142095031bb30993f61a9da10ea0b74931c54868c3daf2025"
    },
    "measurement": null,
    "explanation": null
  }
] as const;
