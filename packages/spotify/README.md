# spotify

Arch recipe imported from [AUR](https://aur.archlinux.org/packages/spotify), initially at revision [`24ce1b811f5b4a821fa4b3ac332455933ff5e167`](https://aur.archlinux.org/cgit/aur.git/commit/?h=spotify&id=24ce1b811f5b4a821fa4b3ac332455933ff5e167). Original maintainer and contributor headers are preserved.

## Package policy

The AUR recipe follows Spotify’s testing repository, as its comments explain. FAR explicitly uses **wget for HTTP and HTTPS resource downloads** through PKGBUILD `DLAGENTS`, with `wget` in `makedepends`. The signed Release → Packages → Debian payload verification chain is retained, including the documented mutable-metadata checksum exceptions.

Import the reviewed Spotify signing key locally when makepkg requests it: `gpg --import packages/spotify/keys/pgp/E1096BCBFF6D418796DE78515384CE82BA52C83A.asc` (from the repository root). No signing keys are imported by CI.

The directory and package base retain AUR's naming. The full declared architecture list is retained, including x86_64. Read `PKGBUILD` and `.SRCINFO` for current runtime, build, and optional dependencies.

## Local use

From the repository root:

```sh
rua builddir ./packages/spotify
```

Or enter this directory and run `makepkg -si`; makepkg builds locally and pacman installs the result. For separate steps, use `makepkg --syncdeps`, inspect `makepkg --packagelist`, then `sudo pacman -U <package-file>`. Review the recipe and update diff, and keep Arch updated first.

## Maintenance

`.aur.json` records the current AUR revision and the SHA-256 hashes of the maintained recipe/support files. `.SRCINFO` is regenerated locally. Scheduled updates propose AUR changes, including packaging changes at the same version, as a PR. Upstream source checksums and signature verification are retained and checked by makepkg on your machine. GitHub does not download all vendor payloads or build this package.

`far.patch` records FAR's local changes and is reapplied to every new snapshot. A conflict stops the update for manual review.

AUR updates depend on the AUR maintainer publishing a new recipe. Manual/runtime verification belongs on the local machine; a passing metadata check does not establish a successful build or launch.
