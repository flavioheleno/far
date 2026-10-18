# Extrudo AppImage

Local Arch x86_64 packaging for [Extrudo](https://github.com/zoltanf/extrudo),
initially pinned to [v0.7.0](https://github.com/zoltanf/extrudo/releases/tag/v0.7.0).
No `extrudo`, `extrudo-bin`, or `extrudo-appimage` package was listed by AUR when
this recipe was added. The `-appimage` suffix identifies the packaged format;
the package provides `extrudo` and installs that command.

## Source and policy

The requested asset is `extrudo-0.7.0-linux-x86_64.AppImage`. Its 140,308,968-byte
download was hashed and matched both the user-provided SHA-256 and GitHub's
published asset digest:

```text
1b661cfcbfe92c16bf9ab5c109a1fe8c7e9a59e122c71d1b2e4ba724689b7f9d
```

Future update PRs track stable releases, select the exact Linux x86_64 AppImage,
verify its SHA-256, and update the pinned source and metadata. Beta releases are
excluded. `update.py` fails on missing or ambiguous assets.

The AppImage is installed under `/usr/lib/extrudo/` with `/usr/bin/extrudo` as a
symlink. Icons are read using `7zip` during local packaging; packaging does not
execute the AppImage. The launcher uses `extrudo %U` with Electron's default
sandbox settings. The upstream GPL-3.0-or-later license is retained. Dependencies
are declared in `PKGBUILD`; runtime uses the bundled Electron application.

## Local use

From the repository root:

```sh
rua builddir ./packages/extrudo-appimage
```

Or enter this directory and run `makepkg -si`. For separate steps, run
`makepkg --syncdeps`, inspect `makepkg --packagelist`, then install the reported
archive with `sudo pacman -U <package-file>`. Keep Arch updated and review the
recipe and diff first. Verify launch, opening a design, and export on your local
desktop; metadata checks do not exercise the GUI or graphics stack.
