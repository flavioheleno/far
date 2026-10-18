# tableplus

Arch recipe imported from [AUR](https://aur.archlinux.org/packages/tableplus),
initially at revision
[`426c310a583a869b3de623d8b854865ac1d27830`](https://aur.archlinux.org/cgit/aur.git/commit/?h=tableplus&id=426c310a583a869b3de623d8b854865ac1d27830).
Original maintainer and contributor headers are preserved.

## Package policy

The vendor’s Linux Debian package is repackaged locally. FAR quotes build paths,
removes the duplicate binary installation, and installs the launcher in
`/usr/bin/tableplus` as a symlink to `/opt/tableplus/tableplus`, rather than
placing package-managed files under `/usr/local`. The initial FAR packaging
adjustment used `pkgrel=1.1`; new upstream versions reset it to `1`. Consult
`PKGBUILD` for the current revision.

The recipe declares `x86_64` and `aarch64`; FAR's local target is Arch Linux
x86_64. Read [PKGBUILD](PKGBUILD) and [.SRCINFO](.SRCINFO) for current
versions and runtime, build, and optional dependencies.

## Local use

From the repository root:

```sh
rua builddir ./packages/tableplus
```

Or enter this directory and run `makepkg -si`; makepkg builds locally and pacman
installs the result. For separate steps, use `makepkg --syncdeps`, inspect
`makepkg --packagelist`, then `sudo pacman -U <package-file>`. Review the recipe
and update diff, and keep Arch updated first.

## Maintenance

Tracks the vendor-supported Linux APT repository documented at
[TablePlus downloads](https://tableplus.com/download/linux), using its
`tableplus/main` indices for amd64 and arm64. Both architectures must publish
the same complete version. Debian build suffixes are retained as numeric
package-version components (for example, `2.0.0-318` becomes `2.0.0.318`). The
initial `0.1.316` sources came from the vendor’s Ubuntu 24 directories. Update
proposals resolve files from the vendor’s `tableplus/main` repository; review
extraction layout and dependencies when accepting that transition.

FAR owns the recipe and supporting files. AUR is credited for the original
import and is not polled. Scheduled update PRs change only the recipe and
generated `.SRCINFO`.

Discovery fetches the vendor's published signing key into a disposable keyring
and accepts it only if it matches the fingerprint pinned in the PKGBUILD's
`validpgpkeys`; FAR stores no key files. It then verifies the detached
`Release.gpg`, checks each `Packages` index against the signed Release SHA-256
and size, and requires each payload to match its signed checksum and size. A key
rotation requires a reviewed `validpgpkeys` change. makepkg itself verifies the
`.deb` against the checksum taken from that signed metadata.

Downloads are temporary, and no package is built or uploaded. Review the
packaging diff and verify launch/integration locally before installing.

See the [repository guide](../../README.md#local-build-and-installation) for the
shared local workflow and
[maintenance commands](../../README.md#recipe-checks-and-updates) for update
previews, applying recipe changes, and troubleshooting.
