# Bambu Studio AppImage

An x86_64 Arch package wrapping the official Bambu Studio Ubuntu 24 AppImage.
The upstream application is downloaded and packaged locally; it is not compiled
from source. FAR tracks **stable and beta releases**, using the full four-part
upstream version (`v02.08.04.57` becomes `2.8.4.57`).

## Provenance and packaging

Based on Joao Costa's [AUR recipe](https://aur.archlinux.org/packages/bambustudio-appimage)
at commit [`80b5a43634ff1478789092d4a700259c4a1acdce`](https://aur.archlinux.org/cgit/aur.git/commit/?h=bambustudio-appimage&id=80b5a43634ff1478789092d4a700259c4a1acdce),
dated 2026-09-25. Contributor attribution is retained in `PKGBUILD`.

FAR retains the package name, runtime dependency (`webkit2gtk-4.1`), provided
`bambustudio` name, conflicts, and desktop integration from that recipe. It uses
the complete upstream build number, separates the upstream tag and asset name,
and extracts desktop resources in `prepare()` for rua compatibility. Missing
icons or desktop files fail the local packaging operation.

The AppImage is installed as `/usr/bin/bambustudio`. Its desktop entry and icon
are installed under `/usr/share/`. The upstream AppImage runtime and licensing
are retained. Check local FUSE support if the AppImage runtime reports a mount
error; GUI, graphics, and printer connectivity must be checked on your machine.

## Local use

From the root of a current FAR checkout, build with rua:

```sh
rua builddir ./packages/bambustudio-appimage
```

This builds, reviews, and installs the local recipe. Rua's usual `install` and
`upgrade` commands look up AUR packages and do not track this GitHub monorepo.

Alternatively, using `base-devel` and the declared dependencies:

```sh
cd packages/bambustudio-appimage
makepkg --syncdeps
makepkg --packagelist
```

Install the reported archive with `sudo pacman -U <package-file>`. `makepkg -si`
combines the build and installation steps. Run a normal Arch system upgrade
before installing newly updated recipes. Read the recipe and diff before use.

## Updates and checks

`.nvchecker.toml` declares the GitHub source, beta policy, and version
normalization. `update.py` resolves the exact timestamped Ubuntu 24 asset, accepts
the known `ubu24`, `ubuntu24.04`, and `ubuntu-24.04` naming forms, and rejects
missing or ambiguous assets. It selects the highest complete version among
eligible published releases, independently of API listing order. Changing
`pkgver` alone cannot update this recipe correctly.

Current source SHA-256 was checked against the downloaded 243,841,528-byte asset
and GitHub's release-asset digest. Metadata and source integrity checks do not
prove GUI startup or compatibility with a particular desktop or printer.
