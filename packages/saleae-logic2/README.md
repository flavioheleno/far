# saleae-logic2

Arch recipe imported from [AUR](https://aur.archlinux.org/packages/saleae-logic2), initially at revision [`b9e140a6328de18c0a0615b61f4771ee09a510f7`](https://aur.archlinux.org/cgit/aur.git/commit/?h=saleae-logic2&id=b9e140a6328de18c0a0615b61f4771ee09a510f7). Original maintainer and contributor headers are preserved.

## Package policy

Repackages the vendor Logic 2 AppImage locally. Review the imported udev rules and Chromium sandbox permissions in `PKGBUILD`; device access and desktop startup require local verification.

The directory and package base retain AUR's naming. The full declared architecture list is retained, including x86_64. Read `PKGBUILD` and `.SRCINFO` for current runtime, build, and optional dependencies.

## Local use

From the repository root:

```sh
rua builddir ./packages/saleae-logic2
```

Or enter this directory and run `makepkg -si`; makepkg builds locally and pacman installs the result. For separate steps, use `makepkg --syncdeps`, inspect `makepkg --packagelist`, then `sudo pacman -U <package-file>`. Review the recipe and update diff, and keep Arch updated first.

## Maintenance

Tracks the normal Linux x64 download on [Saleae downloads](https://www.saleae.com/downloads), resolving the first-party download API redirect with an HTTP HEAD request. The result must be a version-specific `downloads2.saleae.com/logic2/Logic-<version>-linux-x64.AppImage` URL. Insider builds are excluded by using the normal download endpoint.

FAR owns the recipe and supporting files. AUR is credited for the original import and is not polled. Scheduled update PRs change only the recipe and generated `.SRCINFO`.

The vendor download is hashed directly over HTTPS; the imported recipe does not provide a separate signature verification step.

Downloads are temporary, and no package is built or uploaded. Review the packaging diff and verify launch/integration locally before installing.
