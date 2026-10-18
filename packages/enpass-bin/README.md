# enpass-bin

Arch recipe imported from [AUR](https://aur.archlinux.org/packages/enpass-bin), initially at revision [`3e1f4f225be39db7e8ddfccd4c9f1755beee2630`](https://aur.archlinux.org/cgit/aur.git/commit/?h=enpass-bin&id=3e1f4f225be39db7e8ddfccd4c9f1755beee2630). Original maintainer and contributor headers are preserved.

## Package policy

Repackages the vendor Enpass Debian package. Retains the install hook and browser-integration dependency declarations. Verify desktop launch and browser integration locally.

The directory and package base retain AUR's naming. The full declared architecture list is retained, including x86_64. Read `PKGBUILD` and `.SRCINFO` for current runtime, build, and optional dependencies.

## Local use

From the repository root:

```sh
rua builddir ./packages/enpass-bin
```

Or enter this directory and run `makepkg -si`; makepkg builds locally and pacman installs the result. For separate steps, use `makepkg --syncdeps`, inspect `makepkg --packagelist`, then `sudo pacman -U <package-file>`. Review the recipe and update diff, and keep Arch updated first.

## Maintenance

`.aur.json` records the current AUR revision and the SHA-256 hashes of the maintained recipe/support files. `.SRCINFO` is regenerated locally. Scheduled updates propose AUR changes, including packaging changes at the same version, as a PR. Upstream source checksums and signature verification are retained and checked by makepkg on your machine. GitHub does not download all vendor payloads or build this package.

AUR updates depend on the AUR maintainer publishing a new recipe. Manual/runtime verification belongs on the local machine; a passing metadata check does not establish a successful build or launch.
