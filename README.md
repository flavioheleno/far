# FAR — Flavio's Arch Repository

Personal Arch Linux package recipes for an x86_64 machine, maintained at
[flavioheleno/far](https://github.com/flavioheleno/far). GitHub Actions keeps
the recipes current through pull requests. Build and install packages locally
with [rua](https://github.com/vn971/rua) or `makepkg` and `pacman`.

## Repository contract

- Each package lives in `packages/<pkgbase>/` with its `PKGBUILD`, generated
  `.SRCINFO`, update configuration, and packaging notes.
- Git tracks recipes, metadata, patches, documentation, and automation.
- GitHub Actions performs recipe checks and upstream update discovery. It never
  builds or installs managed packages, executes upstream AppImages, uploads package
  artifacts, or caches downloaded binaries.
- An updater may download upstream files into temporary storage to verify their
  checksums. Those files are discarded when the job ends.
- Updates arrive as one reviewable pull request per package. Merge decisions and
  local installation remain manual.

## Layout

```text
packages/              One directory per package base
scripts/               Recipe validation and update orchestration
tests/                 Tests for update selection and failure handling
.github/workflows/     Validation and scheduled recipe updates
AGENTS.md              Instructions for future repository work
```

## Packages

| Package | Architecture | Release channel |
| --- | --- | --- |
| [bambustudio-appimage](packages/bambustudio-appimage/) | x86_64 | Stable and beta |
| [rtk-bin](packages/rtk-bin/) | x86_64 supported | Stable RTK releases |
| [spotify](packages/spotify/) | x86_64 supported | Vendor testing channel |
| [tableplus](packages/tableplus/) | x86_64 supported | Vendor Linux releases |
| [saleae-logic2](packages/saleae-logic2/) | x86_64 supported | Vendor Logic 2 releases |
| [tailwindcss-bin](packages/tailwindcss-bin/) | x86_64 supported | Stable standalone CLI |
| [enpass-bin](packages/enpass-bin/) | x86_64 supported | Vendor Enpass releases |
| [freecad-weekly-appimage](packages/freecad-weekly-appimage/) | x86_64 supported | Weekly FreeCAD builds |
| [fritzing](packages/fritzing/) | x86_64 supported | AUR-selected source revisions |
| [sublime-text-dev](packages/sublime-text-dev/) | x86_64 supported | Sublime Text development builds |
| [extrudo-appimage](packages/extrudo-appimage/) | x86_64 | Stable releases |

## Local build and installation

Clone `https://github.com/flavioheleno/far.git` and review the package recipe and
its history. After pulling
updates with `git pull --ff-only`, use rua's local-directory command:

```sh
rua builddir ./packages/bambustudio-appimage
```

Or enter the package directory and use `makepkg --syncdeps`, then install the
resulting local archive with `sudo pacman -U <package-file>`. `makepkg -si`
combines those steps. See the package README for dependencies, installation
details, and manual runtime checks.

`rua install` and `rua upgrade` normally fetch AUR recipes. They do not discover
FAR's GitHub updates. Use the local checkout when consuming FAR recipes, and keep
your AUR helper from independently replacing FAR-managed packages.

## Metadata maintenance

On Arch Linux with `base-devel` installed, regenerate package metadata without
downloading sources or building a package:

```sh
cd packages/bambustudio-appimage
makepkg --printsrcinfo > .SRCINFO
```

## Recipe checks and updates

Requirements: Arch Linux, Python 3.11+, `base-devel`, `shellcheck`, and `git`.
The Python tooling uses only the standard library. Commands work from any
working directory; the paths below assume the repository root.

```sh
./scripts/check-packages
python3 -m unittest discover -s tests -v
./scripts/update-packages --list
./scripts/update-packages bambustudio-appimage
./scripts/update-packages --apply bambustudio-appimage
```

The checker runs Bash syntax checks, ShellCheck (excluding package metadata and
makepkg-provided variable false positives), and compares regenerated `.SRCINFO`
with the committed file. These checks never call `build()`, `prepare()`, or
`package()` and do not download package sources. Metadata generation does source
the recipe as shell code: only evaluate recipes you trust.

The updater defaults to a read-only preview. `.nvchecker.toml` selects either a
direct GitHub source or an AUR snapshot source. `--apply` updates the managed
recipe files and regenerates `.SRCINFO`, rolling back if validation fails.
Both commands accept one or more package bases;
omitting them selects all packages. Failures are reported independently and
produce a nonzero exit code.

The `source = "upstream"` adapter interface supports direct vendor discovery,
multiple architectures, and SHA-256/SHA-512 source arrays. Configuration declares
allowed HTTPS hosts, literal assignments, and exact checksum slots. Shared
transport hashes downloads in memory with size limits; publication inspects
literal recipe values without executing the recipe. These adapters use Arch's
`vercmp`, including dated package versions. `--verify-current` also forces
payload verification for this interface.

For direct GitHub sources, `update.py` selects the release and exact asset. New
assets are downloaded and hashed. Already-current recipes use GitHub's asset digest to detect upstream changes
without downloading the asset again. Use `--verify-current` to force a fresh
download and hash; assets without a published digest are always downloaded.
Changed content at the same version, ambiguous assets, and downgrades require
manual review. Temporary downloads are hashed as a stream and never saved.
An optional `GH_TOKEN` raises the GitHub API rate limit; it is not passed to
`makepkg`. Release discovery follows up to 1,000 release entries, failing visibly
instead of silently truncating a larger history.

RTK, Tailwind CSS, FreeCAD weekly, Enpass, TablePlus, Saleae Logic 2, and
Sublime Text development builds, and Spotify use the direct upstream interface.
Spotify verifies signed vendor metadata with its pinned key in a temporary
keyring. Fritzing currently uses the AUR source below.

For AUR sources, the updater imports a pinned Git snapshot with its recipe,
patches, launchers, install hooks, and signing keys. It preserves the maintainer's
source checksums and signature checks. `.aur.json` records the current revision
and SHA-256 of every managed file. FAR's optional `far.patch` is reapplied before
metadata generation; conflicts stop the update. AUR recipe/support-file changes
at an unchanged software version also produce a reviewable PR. Vendor payloads
are verified by makepkg locally, rather than downloaded by CI for these packages.
This mode depends on the AUR maintainer publishing an updated recipe.

For reproducible diagnosis of a direct GitHub package, `--releases-json <file>`
accepts a saved GitHub REST release-list response. `--verify-current` likewise
applies only to direct GitHub sources. `--report <file>` writes a JSON summary,
including failures, for either mode. These options do not bypass integrity checks.

The offline unit tests exercise beta selection, full build versions, historical
asset names, ambiguous/missing assets, source integrity, downgrade protection,
rollback, credential stripping, and repeat-run behavior. They build no packages
and contact no external services. Workflow tests also verify patch path limits,
payload bounds, report consistency, and publication without recipe execution.
AUR tests exercise epochs, dated versions, supporting-file additions/removals,
overlay conflicts, rollback, and local source-file integrity. They evaluate only
metadata, and never run packaging functions.

## GitHub Actions

`Validate recipes` checks every package on PRs, pushes to `main`, and manual
dispatch. It also runs the offline tests and `actionlint`. There are no path
filters that could leave a required check pending. The Arch container is pinned
by digest and updates its tools from official repositories at the start of each
run. Recipe evaluation runs as an unprivileged user with no write credentials.

`Update recipes` runs daily at **06:23 UTC** (03:23 in São Paulo) or on manual
dispatch, optionally for one package. It discovers packages and invokes a reusable
workflow independently for each. The preparation job checks the recipe and
produces a bounded text patch for the recipe and metadata. For AUR snapshots, it
also includes the source manifest and changed supporting files. A separate publication
job validates the package-specific path allowlist and applies the patch, then creates or refreshes
`updates/<pkgbase>`. The publication job never evaluates the patched recipe. Data
passes through job outputs; there are no artifact uploads or binary caches.
Small imported public signing keys can travel as bounded Git binary patches;
executable binary payloads are excluded from that handoff.

Direct GitHub PRs include the old/new versions, upstream release link, asset name,
and verified SHA-256. AUR PRs link the precise snapshot revision and preserve the
local overlay; all changed recipe/support files are included. Repeat runs reuse
the same PR and do nothing when already
current. Merge manually after review. Source hashing and metadata checks are not
a substitute for a successful local build and runtime test.

### Repository setup

1. Push the committed repository to `flavioheleno/far` with `main` as the default
   branch. Enable Actions for the repository.
2. Under **Settings → Actions → General → Workflow permissions**, enable
   **Allow GitHub Actions to create and approve pull requests**. Keep the default
   token read-only; the workflows request write access only where needed.
3. Run **Validate recipes**, then manually run **Update recipes** to verify the
   initial configuration. Review the Actions logs for failures.
4. After the first validation run, configure the `Recipe checks` status as a
   required check on `main` if you want branch protection. Merge manually.

By default, PR creation uses the built-in `GITHUB_TOKEN`, requiring no personal
token or repository secrets. GitHub currently places CI runs for PRs created by
that token into an approval-required state; approve the run on the PR. The update
preparation job has already performed recipe checks before opening it.

To make PR CI start automatically, optionally install a GitHub App on **this
repository only**, with Contents and Pull requests read/write permissions. Set
the repository variable `FAR_APP_ID` and secret `FAR_APP_PRIVATE_KEY`. The App key
is used only in the publication job. Leave both unset to use `GITHUB_TOKEN`.

External Actions are pinned to full commit SHAs and updated weekly by Dependabot.
Refresh the official `archlinux:base-devel` container digest in both workflow
files when needed; Dependabot does not maintain those container fields.

GitHub schedules run on the default branch, can be delayed, and public-repository
schedules are disabled after 60 days without repository activity. Watch failure
notifications, check the last successful run periodically, and re-enable an idle
workflow in the Actions UI. Manual dispatch is always available when enabled.

References: [GitHub token behavior](https://docs.github.com/en/actions/concepts/security/github_token),
[scheduled workflows](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule),
and [rua local-directory usage](https://github.com/vn971/rua#use).

## Adding a package

Use the **exact AUR pkgbase**, retaining established `-bin`, `-dev`, `-weekly`, and
`-appimage` names. Preserve a multi-architecture recipe when it supports x86_64;
FAR's local target does not require stripping other architectures from metadata.

For AUR-backed packages, start with a reviewed import:

```sh
./scripts/import-aur <pkgbase>
```

`--checkout <path>` reads an existing AUR Git clone. `--overlay <patch>` records
local changes as `far.patch` and checks that they apply. The import creates
provenance/usage notes, `.nvchecker.toml`, generated `.SRCINFO`, and `.aur.json`,
and refuses to overwrite an existing package. Review and customize the package
README and update the table above before committing.

Keep local recipe changes in `far.patch`, relative to the pinned AUR snapshot.
Use a normal unified diff with context. After reviewing manual changes to an
existing recipe, regenerate its metadata and manifest with:

```sh
./scripts/import-aur --refresh <pkgbase>
```

This intentionally trusts your reviewed changes; update the overlay in the same
commit so the next automated import preserves them. Adding/removing local source
files also requires an explicit update to the manifest's file list.

For direct GitHub updates such as Bambu Studio:

1. Add `packages/<pkgbase>/PKGBUILD`, supporting files, and a README recording
   provenance, channel, asset selection, dependencies, and local usage.
2. Add `.nvchecker.toml` with a matching pkgbase table, `source = "github"`,
   `use_max_release = true`, an explicit `include_prereleases` boolean, and
   numeric dotted version normalization.
3. Add `update.py` implementing `select_candidate(releases, config)` and
   `render_recipe(text, candidate)`. The current shared apply logic expects a
   single SHA-256 source and literal `pkgver`, `_upstream_tag`, and `_asset`
   assignments. Extend that interface with tests before adding other recipe
   shapes; do not force unrelated packages into the AppImage assumptions.
4. Generate `.SRCINFO` and add offline selection/integrity tests.

Run all checks and update the package table before committing. Workflows discover
package directories automatically. Add and review nonofficial dependencies
explicitly; automation does not recursively import or build AUR dependencies.

See [AGENTS.md](AGENTS.md) for the maintenance conventions.
