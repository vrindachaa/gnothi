# Catalog admission review — not an admission claim

Reviewed all 18 rules at:
https://hermes-agent.nousresearch.com/docs/developer-guide/plugins/catalog-submission

`hermes plugins validate C:/Users/vrind/Documents/v-brain/gnothi-submission --install-deps`
passed on the trimmed tree. Manifest, configuration, version-floor parsing,
loadability, isolated registration, declared tools/hooks/middleware, built-in
name collisions, security scan, and no-core-override checks passed. There are
no Python dependencies. Security scan: **safe**.

Warning: `provides_hooks` declares `post_tool_call` and `transform_llm_output`
but default `register()` did not register them. These are intentionally
conditional on `automatic_check: true`; README discloses this. Validation also
reports plugin-host isolation. This warning is not silently waived.

| Rule | Evidence / remaining gate |
|---|---|
| 1 Human-merged gate | Pending: no catalog PR or maintainer admission; local package only. |
| 2 Exact SHA pin | Pending: publish approved destination and use the full final 40-character commit in its catalog entry, never a branch or short hash. |
| 3 No self-updating code | Runtime source has no updater, source download/replacement, or remote executable loading. Only remote call is optional advisory JSON in `jev.py`. |
| 4 SHA bumps via new PR | Future operational requirement; subsequent releases require separately reviewed catalog pin changes. |
| 5 Owner/contributor submission | Source repository is `vrindachaa/gnothi-dev`; user authorized this preparation. Actual catalog PR must be submitted by owner/major contributor or maintainer. |
| 6 Declared capabilities | Manifest lists three tools and two optional hooks; isolated validator passes with conditional-hook warning above. No catalog `capabilities` block exists yet. Optional `OPENROUTER_API_KEY` is declared as a non-required `config_schema` secret, resolved through Hermes; it does not gate loading the offline tools. |
| 7 Install scanner | Actual `--install-deps` validation reports security scan safe. Revalidate the exact published pin in catalog CI. |
| 8 Desktop SDK only | Not applicable: no desktop plugin, renderer script, or UI payload in this package. |
| 9 No core override | Validator passes; `__init__.py` registers tools, hooks, and a skill through context APIs. No runtime core rebinding. |
| 10 Dependency policy | Stdlib-only runtime; validator confirms no Python dependencies declared or installed. |
| 11 Hermes credentials only | `jev.py:22-23` resolves `OPENROUTER_API_KEY` at call time using `agent.secret_scope.get_secret`; fail-closed tests cover missing API and cross-profile environment avoidance. No credential-file reads. Optional credential declaration is present in `config_schema`. |
| 12 Approval/unattended behavior | No shell children, interactive prompts, approvals bypass, or guard changes. Advisory network request has bounded timeout and failure returns `None`; tested without live service calls. |
| 13 Disclosure | README and PITCH disclose separate opt-in OpenRouter/provider transfer of claim/question/aggregate evidence, charges, held-stream latency, non-authoritative scores, and no durable state. Copy these disclosures into catalog PR. |
| 14 Compatibility | `plugin.yaml` version 0.1.0 and SemVer floor >=0.21.5 validate under installed Hermes. Catalog entry must match. Validation on this installation does not establish compatibility across every version at the floor. |
| 15 No skins/bundled forks | This package contains an independent quantitative-verification plugin, not a skin or bundled-plugin modification. Catalog lineage still subject to maintainer review. |
| 16 One listing per lineage | No listing created. This tree derives from the user's Gnothi development branch, not a new competing brand. Catalog duplication/lineage sweep remains before opening entry PR. |
| 17 Reviewable source | Trim removed committed bytecode, historical archive, and alternate implementations. Final committed tree/archive contains readable source/docs/config only. Generated local compile caches are ignored, not shipped. |
| 18 Password-manager vendor | Not applicable: no `register_login_backend`, vault backend, or password-manager integration. |

## Other pre-submission gates

The submission is published at https://github.com/vrindachaa/gnothi under MIT.
The catalog entry must pin the final published commit. Full model-driven Hermes smoke,
public demo, submission form, and catalog CI are not established by unit tests.
Do not describe this package as fully catalog-aligned or admitted until the
pending catalog review and CI gates have been resolved.
