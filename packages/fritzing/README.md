# fritzing

Arch recipe imported from [AUR](https://aur.archlinux.org/packages/fritzing),
initially at revision
[`045535f8160b983a754e0d5d82b345a7fd2093ae`](https://aur.archlinux.org/cgit/aur.git/commit/?h=fritzing&id=045535f8160b983a754e0d5d82b345a7fd2093ae).
Original maintainer and contributor headers are preserved.

## Package policy

Builds Fritzing **from source on your machine**. The application and parts
repositories are pinned to separate commits, with the AUR patches, ngspice/Qt
dependencies, and install hook retained. FAR adds explicit failure handling for
directory changes. VCS checksum exceptions correspond to those pinned Git
revisions; the other sources retain their checksums.

The recipe declares `x86_64`, `aarch64`, and `i686`; FAR's local target is Arch
Linux x86_64. Read [PKGBUILD](PKGBUILD) and [.SRCINFO](.SRCINFO) for
current versions and runtime, build, and optional dependencies.

## Local use

From the repository root:

```sh
rua builddir ./packages/fritzing
```

Or enter this directory and run `makepkg -si`; makepkg builds locally and pacman
installs the result. For separate steps, use `makepkg --syncdeps`, inspect
`makepkg --packagelist`, then `sudo pacman -U <package-file>`. Review the recipe
and update diff, and keep Arch updated first.

## Maintenance

FAR watches upstream's source-version history on the `develop` branch, following
commits such as
[`da68b653842c4e35fb2e3e3453384d2fbdb9e4ae` (Bump version to 1.0.8)](https://github.com/fritzing/fritzing-app/commit/da68b653842c4e35fb2e3e3453384d2fbdb9e4ae).
It does not use GitHub Releases, source tags, AUR, or website announcements for
discovery.

The updater resolves an immutable branch head and reads
`CFBundleShortVersionString` from `FritzingInfo.plist` there. If this version is
newer, it scans the history of `src/version/version.cpp` at that same head for a
unique matching version-bump commit. It checks the plist and AppStream release
version at the bump commit, then proposes that exact application commit in
`_gitrev`. A commit message alone is insufficient. Missing/ambiguous bumps,
inconsistent metadata, and incomplete history scans fail visibly for manual
review.

For the current version, the existing reviewed application commit is preserved,
including its post-bump fixes. The parts revision remains a manually maintained
compatibility pin. Review parts compatibility, Arch patches, dependencies, and
upstream's release status before merging. A source version
bump can precede a publicly announced release, so a PR is a discovery signal
requiring review.

FAR owns the recipe and supporting patches; AUR attribution records only the
initial import. Compilation and runtime verification happen locally.
`--verify-current` does not download or build pinned VCS sources. If automatic
selection stops, inspect the upstream history, choose full application and parts
commit hashes explicitly, update the version and packaging revision, regenerate
`.SRCINFO`, and run the repository checks.

See the [repository guide](../../README.md#local-build-and-installation) for the
shared local workflow and
[maintenance commands](../../README.md#recipe-checks-and-updates) for update
previews, applying recipe changes, and troubleshooting.
