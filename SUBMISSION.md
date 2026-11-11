# Submission package

## Contents

The repository root is the installable `gnothi` plugin: manifest, runtime
modules, bundled skill, tests, user documentation, pitch, and CI workflow.
No alternative implementations, orchestration prompts, internal handoffs,
review archives, historical UI, or development transcripts are included in
the submitted tree. Production Python code is unchanged from the source PR.

Source: `vrindachaa/gnothi-dev` PR #2, `lux` commit
`68d99ba91be5d9898bb25789ac7f5cbf92785514`.

## Verified on this trimmed tree

- `python -B -m unittest discover -s tests -v`: 115 tests passed.
- `python -m compileall -q .`: passed.
- `git diff --check`: passed before committing.
- Unit coverage includes package-loader registration and the public-handler
  40-task demo: exact McNemar p=0.625, inconclusive, overclaim flagged.
- CI paths have been updated for the root-level plugin. The configured remote
  matrix targets Python 3.12 and 3.14; a configured workflow is not a CI pass.

## Limits and publication checklist

- This is a local submission branch, not a public release or catalog admission.
- No full model-driven Hermes session or live remote Jev request was rerun for
  this packaging change. Mocked integration tests are not live-service evidence.
- Automatic hooks and remote Jev advice remain explicitly default-off. See the
  README for data disclosure, charges, and statistical interpretation limits.
- The selected source plugin has no license. The owner must choose/authorize an
  appropriate license if submission rules require one; none has been invented.
- Confirm the destination (new repository versus branch) and intended visibility
  before publishing. Complete any external form, recording, and catalog entry
  separately.
- A branch retains its source history. Use the clean tree archive or a fresh
  repository import if development history must not be published.
