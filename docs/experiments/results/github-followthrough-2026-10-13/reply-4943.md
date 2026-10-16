@JonnyFaeth Thank you for catching this and testing the correction on Windows. My fixture assumed `forkserver` was available. I've applied your fallback in `0f5d98875af5c7bd98c2b6804cba96119b2ef12b`, with credit in the commit.

On macOS arm64, the updated fixture passes all **48 selected checks**. I also forced its available-method list to `["spawn"]` and reran all **17 async cases**: all pass, with real spawned Gym workers and no skips. Full pre-commit checks pass. Production code and test assertions are unchanged.

I've added your Windows result to the PR description with the tested revision and environment. The local fallback check covers `spawn` behavior on macOS; your report supplies the Windows check.
