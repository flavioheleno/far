# tailwindcss-bin

Arch recipe imported from
[AUR](https://aur.archlinux.org/packages/tailwindcss-bin), initially at revision
[`e18c8eca213ac4b9e0318d451a10d14b4af4eb44`](https://aur.archlinux.org/cgit/aur.git/commit/?h=tailwindcss-bin&id=e18c8eca213ac4b9e0318d451a10d14b4af4eb44).
Original maintainer and contributor headers are preserved.

## Package policy

Prebuilt standalone Tailwind CSS CLI, installed as `/usr/bin/tailwindcss` with
its release-specific MIT license. Tracks
[tailwindlabs/tailwindcss stable releases](https://github.com/tailwindlabs/tailwindcss/releases),
selecting `tailwindcss-linux-x64` and `tailwindcss-linux-arm64` exactly. The
recipe requires `glibc`; no Node.js build is performed by FAR automation.

The recipe declares `x86_64` and `aarch64`; FAR's local target is Arch Linux
x86_64. Read [PKGBUILD](PKGBUILD) and [.SRCINFO](.SRCINFO) for current
versions and runtime, build, and optional dependencies.

## Local use

From the repository root:

```sh
rua builddir ./packages/tailwindcss-bin
```

Or enter this directory and run `makepkg -si`; makepkg builds locally and pacman
installs the result. For separate steps, use `makepkg --syncdeps`, inspect
`makepkg --packagelist`, then `sudo pacman -U <package-file>`. Review the recipe
and update diff, and keep Arch updated first.

## Maintenance

FAR tracks upstream GitHub releases directly; AUR is credited only for the
initial recipe. `.nvchecker.toml` declares the release source, exact assets,
HTTPS hosts, and checksum mappings. Scheduled jobs propose version, source URL,
checksum, and generated `.SRCINFO` changes. Recipe customizations and supporting
files stay under FAR ownership.

Every declared architecture and the release-specific license are downloaded and
hashed before proposing an update. Drafts and prereleases are excluded.

Downloads are temporary and discarded; no packages are built or uploaded. Review
upstream packaging compatibility and test locally.

See the [repository guide](../../README.md#local-build-and-installation) for the
shared local workflow and
[maintenance commands](../../README.md#recipe-checks-and-updates) for update
previews, applying recipe changes, and troubleshooting.
