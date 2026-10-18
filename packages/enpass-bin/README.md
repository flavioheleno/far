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

Tracks the vendor stable Debian index at `https://apt.enpass.io/dists/stable/main/binary-amd64/Packages`. The exact filename, version, size, and SHA-256 come from that HTTPS index. The payload is independently downloaded and hashed before an update is proposed.

FAR owns the recipe and supporting files. AUR is credited for the original import and is not polled. Scheduled update PRs change only the recipe and generated `.SRCINFO`.

Repository metadata is fetched over HTTPS; these adapters do not currently authenticate the vendor APT signatures. Published payload checksums and sizes must match a fresh download.

Downloads are temporary, and no package is built or uploaded. Review the packaging diff and verify launch/integration locally before installing.
