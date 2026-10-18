# rtk-bin

Arch recipe imported from [AUR](https://aur.archlinux.org/packages/rtk-bin),
initially at revision
[`18d73f37a4f2d3274ed4d23fe28a8f9b77cd4fc1`](https://aur.archlinux.org/cgit/aur.git/commit/?h=rtk-bin&id=18d73f37a4f2d3274ed4d23fe28a8f9b77cd4fc1).
Original maintainer and contributor headers are preserved.

## Package policy

Prebuilt RTK command-line proxy, installed as `/usr/bin/rtk` with its
release-specific MIT license. Tracks
[rtk-ai/rtk stable releases](https://github.com/rtk-ai/rtk/releases). The exact
payloads are `rtk-x86_64-unknown-linux-musl.tar.gz` for x86_64 and
`rtk-aarch64-unknown-linux-gnu.tar.gz` for aarch64. The aarch64 recipe retains
its `glibc` and `libgcc` dependencies.

The recipe declares `x86_64` and `aarch64`; FAR's local target is Arch Linux
x86_64. Read [PKGBUILD](PKGBUILD) and [.SRCINFO](.SRCINFO) for current
versions and runtime, build, and optional dependencies.

## Local use

From the repository root:

```sh
rua builddir ./packages/rtk-bin
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
