# sublime-text-dev

Arch recipe imported from [AUR](https://aur.archlinux.org/packages/sublime-text-dev), initially at revision [`6e4ed7eb667785b5f04da71aa55f7821ea6d10e0`](https://aur.archlinux.org/cgit/aur.git/commit/?h=sublime-text-dev&id=6e4ed7eb667785b5f04da71aa55f7821ea6d10e0). Original maintainer and contributor headers are preserved.

## Package policy

Tracks Sublime Text’s development build, retaining the AUR wrapper, install hook, full build version, and both declared CPU architectures.

The directory and package base retain AUR's naming. The full declared architecture list is retained, including x86_64. Read `PKGBUILD` and `.SRCINFO` for current runtime, build, and optional dependencies.

## Local use

From the repository root:

```sh
rua builddir ./packages/sublime-text-dev
```

Or enter this directory and run `makepkg -si`; makepkg builds locally and pacman installs the result. For separate steps, use `makepkg --syncdeps`, inspect `makepkg --packagelist`, then `sudo pacman -U <package-file>`. Review the recipe and update diff, and keep Arch updated first.

## Maintenance

Tracks the current build on [Sublime Text development builds](https://www.sublimetext.com/dev). Both x64 and arm64 version-specific tarballs are hashed with SHA-512. The complete upstream build remains in `pkgver`, for example `4.4214`.

FAR owns the recipe and supporting files. AUR is credited for the original import and is not polled. Scheduled update PRs change only the recipe and generated `.SRCINFO`.

The vendor download is hashed directly over HTTPS; the imported recipe does not provide a separate signature verification step.

Downloads are temporary, and no package is built or uploaded. Review the packaging diff and verify launch/integration locally before installing.
