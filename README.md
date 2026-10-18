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

## Relationship to AUR

FAR tracks each project's own releases or vendor repository directly. It does
not poll AUR, synchronize AUR Git snapshots, or publish changes back to AUR.
AUR supplied the initial recipes for several packages; their original revision
links and contributor attribution remain in the package documentation. Existing
package names follow AUR conventions so local packages retain their expected
names, `provides`, and `conflicts`.

FAR owns packaging maintenance from here: dependency changes, patches, launchers,
install hooks, and signing-key changes require review in this repository. A new
upstream release can trigger a recipe PR without waiting for an AUR maintainer.

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
| [fritzing](packages/fritzing/) | x86_64 supported | Source-version bumps; pinned commits |
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

Requirements: Arch Linux, Python 3.11+, `base-devel` (including `vercmp`),
`shellcheck`, `git`, and `gnupg`.
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
direct GitHub AppImage source or the shared direct upstream interface. `--apply` updates the managed
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

The other packages use the shared interface in `scripts/upstreams.py`:

| Package | First-party discovery source |
| --- | --- |
| RTK | [GitHub stable releases](https://github.com/rtk-ai/rtk/releases) |
| Tailwind CSS | [GitHub stable releases](https://github.com/tailwindlabs/tailwindcss/releases) |
| FreeCAD weekly | [GitHub weekly releases](https://github.com/FreeCAD/FreeCAD/releases); base version from `version.json` at the selected tag |
| Spotify | [Vendor testing repository](https://repository.spotify.com/dists/testing/Release), authenticated with the committed signing key |
| TablePlus | [Vendor Linux APT repository](https://tableplus.com/download/linux), both amd64 and arm64 |
| Enpass | [Vendor stable APT repository](https://apt.enpass.io/), amd64 |
| Saleae Logic 2 | [Normal vendor download](https://www.saleae.com/downloads), resolved to an exact Linux x64 AppImage |
| Sublime Text dev | [Development build announcement](https://www.sublimetext.com/dev), x64 and arm64 tarballs |
| Fritzing | [Source-version commit history](https://github.com/fritzing/fritzing-app/commits/develop/src/version/version.cpp), checked against plist and AppStream metadata |

Each configuration declares allowed HTTPS hosts, assignments, and checksum
slots. Every declared architecture must be available at the same version. New
payloads are downloaded into the hashing stream and discarded, with declared
sizes and published checksums verified when available. Current sources with no
published checksum are downloaded again to detect changed content. Local
supporting files and recipe customizations remain in FAR; the updater changes
only the version/source literals, payload checksums, `pkgrel`, and `.SRCINFO`.

Spotify verifies the signed Release, its Packages index, and the Debian payload
using its pinned key in a disposable keyring. Its PKGBUILD retains **wget** for
local downloads. TablePlus and Enpass use HTTPS repository metadata and payload
checksums; their APT signatures are not currently authenticated by these adapters.
Sublime and Saleae downloads are hashed over HTTPS without an independent
signature step, matching the imported recipes' verification policy.

Fritzing watches source-version bump commits on the upstream `develop` branch.
It resolves an immutable head, reads the source version, and checks a matching
version-bump commit against both plist and AppStream metadata before proposing
that exact application pin. The current application's reviewed post-bump fixes
are preserved until the version advances. Its parts revision stays pinned for
compatibility review. Missing or ambiguous commits and inconsistent metadata
stop the update. A version bump can precede a public release: review upstream's
release status, source patches, and parts compatibility before merging. GitHub
Releases, tags, and website announcements are not used for Fritzing discovery.

For reproducible diagnosis of the Bambu Studio or Extrudo adapter,
`--releases-json <file>` accepts a saved GitHub REST release-list response.
`--verify-current` also checks shared-adapter payloads; it does not fetch
Fritzing VCS source trees. `--report <file>` writes a JSON summary, including
failures, for all adapters. These options do not bypass integrity checks.

The offline unit tests exercise beta selection, full build versions, historical
asset names, ambiguous/missing assets, source integrity, downgrade protection,
rollback, credential stripping, and repeat-run behavior. They build no packages
and contact no external services. Workflow tests also verify patch path limits,
payload bounds, report consistency, and publication without recipe execution.
Direct upstream tests cover multiple architectures, full Debian build versions,
signed metadata verification, source allowlists, checksum slots, weekly dates,
Fritzing version-bump selection, rollback, and publication on non-Arch runners.
They never build managed packages.

## GitHub Actions

`Validate recipes` checks every package on PRs, pushes to `main`, and manual
dispatch. It also runs the offline tests and `actionlint`. There are no path
filters that could leave a required check pending. The Arch container is pinned
by digest and updates its tools from official repositories at the start of each
run. Recipe evaluation runs as an unprivileged user with no write credentials.

`Update recipes` runs daily at **06:23 UTC** (03:23 in São Paulo) or on manual
dispatch, optionally for one package. It discovers packages and invokes a reusable
workflow independently for each. The preparation job checks the recipe and
produces a bounded text patch for the recipe and metadata. A separate publication
job validates the package-specific path allowlist and applies the patch, then creates or refreshes
`updates/<pkgbase>`. The publication job never evaluates the patched recipe. Data
passes through job outputs; there are no artifact uploads or binary caches.
Only text changes to the selected PKGBUILD and `.SRCINFO` are accepted. Supporting
files and signing-key changes require a separate reviewed maintenance commit.

PRs include the old/new versions, upstream link, and asset/checksum or source-pin
details. Repeat runs reuse the same PR and do nothing when already current. Merge manually after review. Source hashing and metadata checks are not
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

Add recipes manually from reviewed first-party packaging or an attributed
initial AUR recipe. There is no AUR import or synchronization command. Preserve
useful existing dependencies, install hooks, source patches, signatures, epochs,
and architecture definitions; maintain local changes directly in the recipe.

For the shared upstream interface:

1. Add `PKGBUILD`, generated `.SRCINFO`, supporting files, and a package README
   describing provenance, release channel, exact source selection, and local use.
2. Add `.nvchecker.toml` with `source = "upstream"`, an adapter `mode`, explicit
   HTTPS `hosts`, and an `assignments` allowlist containing `pkgver` plus the
   upstream literals. Binary sources use literal `_url...` variables referenced
   by `source` arrays. Map every remote payload/license to its exact checksum
   array/index, algorithm, and adapter-specific asset or repository metadata.
3. Reuse a discovery mode in `scripts/upstreams.py`, or add a focused mode with
   offline fixtures for selection, integrity, failure handling, and publication.
   Keep shared download, apply, rollback, and literal publication validation in
   `scripts/far_upstream.py`. Update adapters must cover all declared architectures.
4. Check metadata and run the offline tests before committing. Vendor signing-key
   rotations and changes to build patches/dependencies need explicit review.

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
