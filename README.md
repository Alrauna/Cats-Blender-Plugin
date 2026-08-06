# Cats Blender Plugin

Cats is a tool that shortens the steps needed to import and optimize avatar
models for VRChat. Compatible models include MMD, XNALara, Mixamo, Source
Engine, Unreal Engine, DAZ/Poser, Blender Rigify, Sims 2, MotionBuilder, 3ds
Max, and more. Processes that would take hours by hand are compressed into a
few operators.

This repository is a personal fork maintained by **Alrauna**, targeting Blender
5.2 LTS. It continues from the unofficial Cats Blender Plugin after that project
was archived. See [History and credit](#history-and-credit).

> **This is not the original Cats.** Do not ask for support with this version in
> the original Cats Discord, or in the archived unofficial project's Discord.
> Neither is run by this fork. Open an
> [issue](https://github.com/Alrauna/Cats-Blender-Plugin/issues) here instead.

## Blender version support

**Supported:** Blender 5.2 LTS.

`blender_manifest.toml` declares `blender_version_min = "5.2.0"`, and Blender
will refuse to enable the extension on anything older. Branches for earlier
Blender versions exist in this repository's history and in the
[Releases](https://github.com/Alrauna/Cats-Blender-Plugin/releases) tab, but
they are not maintained here.

## Requirements

- Blender 5.2 LTS or newer, from [blender.org](https://www.blender.org/download/)
- If Blender uses a custom Python installation, NumPy must be available in it

Not supported: the Windows Store build of Blender, due to known permission
issues, and the Linux package-manager, Snap, and Flatpak builds.

### Optional dependencies

Some features need additional add-ons:

- **Material Combiner**, for texture atlasing:
  [Alrauna/material-combiner-addon](https://github.com/Alrauna/material-combiner-addon)
- **Immersive Scaler**, for scaling tools:
  [Alrauna/immersive_scaler](https://github.com/Alrauna/immersive_scaler)

## Install

Use a ZIP built as a Blender extension. In Blender 5.2, open **Edit >
Preferences > Get Extensions**, use the menu in the upper right, choose
**Install from Disk**, select the Cats ZIP, and enable the extension.

Do not install a repository source ZIP downloaded from a hosting website. That
archive may carry an extra wrapper directory and has not been through Blender's
extension builder.

## Features

- **Import and export:** MMD, VRM, FBX, Source Engine, and more
- **Optimization:** material combining, texture atlasing, bone merging,
  decimation
- **Eye tracking:** SDK3 and legacy setup
- **Visemes:** automatic lip-sync configuration
- **Custom model creation:** merge armatures, attach meshes
- **Translation:** convert Japanese names to English
- **Pose mode:** including shape-key-preserving pose controls

## Build from source

Requires Blender 5.2 on the system. From the repository root:

```text
python scripts/build.py --blend <path to blender>
```

The script reads the package metadata, writes the ZIP into
`.packaged-releases/`, validates the source and the package, and runs
`tests/verify_package.py`. It refuses to build a tree with uncommitted tracked
changes. Build rules intentionally exclude tests, repository metadata, caches,
and user-specific mutable state.

## Updates

Automatic updates are intentionally disabled. This fork has no release
repository configured yet, and leaving updates enabled would let the archived
upstream project overwrite this Blender 5.2 build. A maintainer can re-enable
them by setting the fork-owned `UPDATE_REPOSITORY`, `UPDATE_API_URL`, and
`UPDATE_DEV_BRANCH` constants in `updater.py`.

## Documentation

This fork has no wiki of its own yet. The archived unofficial project's wiki
remains the most complete feature documentation and is still readable, but it
describes older versions and is **historical, not current**:

- [Archived wiki](https://github.com/teamneoneko/Cats-Blender-Plugin-Unofficial-/wiki)
  (archival)
- [Archived feature list](https://github.com/teamneoneko/Cats-Blender-Plugin-Unofficial-/wiki/Features)
  (archival)

Where the archived wiki and this repository disagree, this repository is
correct.

## History and credit

Cats has passed through several hands, and this fork exists because of all of
them.

**Originally created** by [Absolute
Quantum](https://github.com/absolute-quantum/cats-blender-plugin) — Hotox and
GiveMeAllYourCats. That project is no longer developed.

**Then maintained** as the unofficial Cats Blender Plugin by **Team Neoneko**,
with **Yusarina** carrying it through Blender 3.6 to 5.0. That
project is now archived. The Blender 5.2 work here starts from their 5.0 release
and would not have been possible without it. Thank you.

**Now maintained** by Alrauna, targeting Blender 5.2 LTS and later.

### Contributors

Carried forward from the projects above: Hotox, GiveMeAllYourCats, Shotariya,
Neitri, Kiraver, Jordo, Ruubick, 989onan, rurre, Feilen, triazo, Mysteryem,
Yusarina.

### Bundled and companion projects

- [MMD Tools](https://github.com/UuuNyaa/blender_mmd_tools), bundled as
  `extern_tools/mmd_tools_local`
- [Material Combiner](https://github.com/Alrauna/material-combiner-addon), forked
  from Team Neoneko's fork of
  [Grim-es/material-combiner-addon](https://github.com/Grim-es/material-combiner-addon)
- [Immersive Scaler](https://github.com/Alrauna/immersive_scaler), forked from
  [triazo/immersive_scaler](https://github.com/triazo/immersive_scaler)

## Feedback

Open an [issue](https://github.com/Alrauna/Cats-Blender-Plugin/issues).

## License

GPL-3.0-or-later. See [LICENSE](LICENSE). Bundled third-party code keeps its own
license and attribution files.
