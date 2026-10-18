# tailwindcss-bin

Arch recipe imported from [AUR](https://aur.archlinux.org/packages/tailwindcss-bin), initially at revision [`e18c8eca213ac4b9e0318d451a10d14b4af4eb44`](https://aur.archlinux.org/cgit/aur.git/commit/?h=tailwindcss-bin&id=e18c8eca213ac4b9e0318d451a10d14b4af4eb44). Original maintainer and contributor headers are preserved.

## Package policy

Prebuilt standalone Tailwind CSS CLI, retaining its upstream MIT license and both declared CPU architectures. No Node.js build is performed by FAR automation.

The directory and package base retain AUR's naming. The full declared architecture list is retained, including x86_64. Read `PKGBUILD` and `.SRCINFO` for current runtime, build, and optional dependencies.

## Local use

From the repository root:

```sh
rua builddir ./packages/tailwindcss-bin
```

Or enter this directory and run `makepkg -si`; makepkg builds locally and pacman installs the result. For separate steps, use `makepkg --syncdeps`, inspect `makepkg --packagelist`, then `sudo pacman -U <package-file>`. Review the recipe and update diff, and keep Arch updated first.

## Maintenance

FAR tracks upstream GitHub releases directly; AUR is credited only for the initial recipe. `.nvchecker.toml` declares the release source, exact assets, HTTPS hosts, and checksum mappings. Scheduled jobs propose version, source URL, checksum, and generated `.SRCINFO` changes. Recipe customizations and supporting files stay under FAR ownership.

Every declared architecture and the release-specific license are downloaded and hashed before proposing an update. Drafts and prereleases are excluded.

Downloads are temporary and discarded; no packages are built or uploaded. Review upstream packaging compatibility and test locally.
