@LinCanNerd Thank you for running both revisions and recording the environment. Using the same fixture against the base makes the comparison clear: the eight SAME_STEP failures and the 48-pass candidate match the macOS result.

I've added your Thor result, tested revisions and environment to the PR description, with the CPU-only scope explicit. The `forkserver` detail is useful too; the `spawn` fallback remains covered separately by the Windows report and local fallback checks.
