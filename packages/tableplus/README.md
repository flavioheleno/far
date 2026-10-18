# tableplus

Arch recipe imported from [AUR](https://aur.archlinux.org/packages/tableplus), initially at revision [`426c310a583a869b3de623d8b854865ac1d27830`](https://aur.archlinux.org/cgit/aur.git/commit/?h=tableplus&id=426c310a583a869b3de623d8b854865ac1d27830). Original maintainer and contributor headers are preserved.

## Package policy

The vendor’s Linux Debian package is repackaged locally. FAR quotes build paths, removes the duplicate binary installation, and installs the launcher in `/usr/bin/tableplus` as a symlink to `/opt/tableplus/tableplus`, rather than placing package-managed files under `/usr/local`. The current local packaging revision is `1.1`; upstream version updates reset it to `1`.

The directory and package base retain AUR's naming. The full declared architecture list is retained, including x86_64. Read `PKGBUILD` and `.SRCINFO` for current runtime, build, and optional dependencies.

## Local use

From the repository root:

```sh
rua builddir ./packages/tableplus
```

Or enter this directory and run `makepkg -si`; makepkg builds locally and pacman installs the result. For separate steps, use `makepkg --syncdeps`, inspect `makepkg --packagelist`, then `sudo pacman -U <package-file>`. Review the recipe and update diff, and keep Arch updated first.

## Maintenance

Tracks the vendor-supported Linux APT repository documented at [TablePlus downloads](https://tableplus.com/download/linux), using its `tableplus/main` indices for amd64 and arm64. Both architectures must publish the same complete version. Debian build suffixes are retained as numeric package-version components (for example, `2.0.0-318` becomes `2.0.0.318`). The initial recipe still pins the reviewed Ubuntu 24 payload; the next upstream proposal can migrate to the current vendor repository. Review extraction layout and dependencies when merging that transition.

FAR owns the recipe and supporting files. AUR is credited for the original import and is not polled. Scheduled update PRs change only the recipe and generated `.SRCINFO`.

Repository metadata is fetched over HTTPS; these adapters do not currently authenticate the vendor APT signatures. Published payload checksums and sizes must match a fresh download.

Downloads are temporary, and no package is built or uploaded. Review the packaging diff and verify launch/integration locally before installing.
