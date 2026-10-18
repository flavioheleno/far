# spotify

Arch recipe imported from [AUR](https://aur.archlinux.org/packages/spotify),
initially at revision
[`24ce1b811f5b4a821fa4b3ac332455933ff5e167`](https://aur.archlinux.org/cgit/aur.git/commit/?h=spotify&id=24ce1b811f5b4a821fa4b3ac332455933ff5e167).
Original maintainer and contributor headers are preserved.

## Package policy

Tracks Spotify’s testing repository directly, preserving the initial recipe’s
release channel. FAR explicitly uses **wget for HTTP and HTTPS resource
downloads** through PKGBUILD `DLAGENTS`, with `wget` in `makedepends`. The
signed Release → Packages → Debian payload verification chain is retained,
including the documented mutable-metadata checksum exceptions.

The signing key is pinned by fingerprint in the PKGBUILD's `validpgpkeys`; FAR
stores no key files. Import Spotify's published key locally when makepkg
requests it, and confirm `gpg` reports the pinned fingerprint:
`curl -fsSL https://download.spotify.com/debian/pubkey_5384CE82BA52C83A.gpg | gpg --import -`.
CI verifies metadata in an isolated temporary keyring; it never modifies your
local keyring.

The recipe targets Arch Linux `x86_64`. Read [PKGBUILD](PKGBUILD) and [.SRCINFO](.SRCINFO) for current
versions and runtime, build, and optional dependencies.

## Local use

From the repository root:

```sh
rua builddir ./packages/spotify
```

Or enter this directory and run `makepkg -si`; makepkg builds locally and pacman
installs the result. For separate steps, use `makepkg --syncdeps`, inspect
`makepkg --packagelist`, then `sudo pacman -U <package-file>`. Review the recipe
and update diff, and keep Arch updated first.

## Maintenance

FAR reads Spotify's first-party testing repository directly over HTTPS. It
fetches Spotify's published key, accepts it only if it matches the PKGBUILD's
`validpgpkeys` fingerprint, verifies `Release.gpg` with it, checks the
`Packages` index against the signed Release SHA-256 and size, selects
`spotify-client` for amd64, then downloads and verifies the Debian payload
against its SHA-512 and size. The full vendor commit suffix is retained in
`_commit`, and `epoch=1` is preserved. Spotify's index publishes the matching
Debian epoch (`1:`); a different upstream epoch stops the update for review.

A changed signing key requires manual review and a reviewed `validpgpkeys`
change; a key whose fingerprint differs from the pinned one stops the update. The isolated
temporary keyring is discarded after discovery. Spotify's PKGBUILD continues to
use **wget** for HTTP and HTTPS downloads on your machine and retains makepkg's
signature verification and the signed metadata-to-payload verification chain.
Mutable Release and Packages checksum exceptions remain intentional.

AUR is credited only for the initial import. FAR owns the recipe, launchers,
license, signing key, and install policy. Update PRs change only `PKGBUILD` and
generated `.SRCINFO`; downloads are discarded and no package is built or
uploaded. Review the diff and test desktop/protocol integration locally. A
recipe can fail to build if Spotify has replaced its mutable repository metadata
since the update PR; refresh to the current reviewed release in that case.

See the [repository guide](../../README.md#local-build-and-installation) for the
shared local workflow and
[maintenance commands](../../README.md#recipe-checks-and-updates) for update
previews, applying recipe changes, and troubleshooting.
