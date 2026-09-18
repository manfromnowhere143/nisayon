# Licensing

Nisayon's original code, documentation and eligible research records are
licensed under the unmodified [Apache License 2.0](../LICENSE).
Copyright 2026 Daniel Wahnich. [NOTICE](../NOTICE) carries the project attribution.
The license applies to the included historical Nisayon source archives as well;
their bytes and scientific identities remain unchanged. Include LICENSE and
NOTICE when redistributing that source.

## Why Apache-2.0

Apache-2.0 fits this open-source research release and follows the published
licenses of Sentinel, Telos, Inbar and Odeya. The [pinned review](licensing-review.json)
records exact revisions, license bytes and comparison with the official text.

For this release, Apache-2.0 supports research and commercial reuse, including
proprietary derivatives. It requires preservation of applicable notices and
identification of modifications, and includes an explicit patent grant limited
to covered contributor claims, with its stated patent-litigation termination
condition. It does not grant general trademark permission. These are the
standard license's terms, not additional Nisayon restrictions. See the
[official text](https://www.apache.org/licenses/LICENSE-2.0) and
[application guidance](https://www.apache.org/foundation/license-faq.html#Apply-My-Software).

This choice does not certify the software, establish physical safety, or turn
the two negative comparisons into a positive result. Commercial reuse does not
require publishing the user's separate proprietary code under this license.

## Third-party boundary

The Git release contains Nisayon source and eligible compact evidence. It does
not bundle the simulator installation, Python dependency wheels, training data,
policy weights, videos or full raw simulator stores. The lockfile identifies
dependencies; installing them obtains separate works under their upstream terms.
Nisayon's license does not replace those terms or grant rights over upstream assets.

The qualified simulator uses robomimic and robosuite code under MIT and MuJoCo
under Apache-2.0. Their package notices, bundled components and transitive
dependencies retain their own terms. See the pinned upstream license links and
qualified versions in [ASSETS.md](experiments/ASSETS.md). A future distribution
that bundles those packages must preserve the notices required for its actual
contents; this source release does not claim to clear every possible bundle.

The robomimic Lift checkpoint has a public download and a pinned SHA-256, but
the model-zoo page does not state a separate checkpoint license. It is obtained
from upstream and excluded from this distribution. A code license is not a
grant to redistribute separately hosted model weights or training data.

No license grants or research claims are inferred from the private development
history. The public source snapshot excludes private client settings, session
memory and that history. The [release manifest](RELEASE.md) binds its contents.

## Contributions and packages

Submit only material you have the right to contribute. Contributions intentionally
submitted for inclusion use Apache-2.0 under section 5 unless explicitly stated
otherwise or governed by a separate agreement. Preserve third-party notices.
There is no additional contributor agreement introduced by this release.

Package metadata declares `Apache-2.0` and includes LICENSE and NOTICE. Factual
model identifiers and experiment provenance remain in the records; public
authorship follows the [standing project rule](VOICE.md).
