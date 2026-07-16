# Cats Blender Plugin for Blender 5.2 LTS

This repository is a maintained personal fork of the archived unofficial Cats
Blender Plugin. It targets Blender 5.2 LTS and preserves the existing Cats
workflows for importing and optimizing avatar models, including MMD, XNALara,
Mixamo, Source Engine, Unreal Engine, DAZ/Poser, Rigify, Sims, MotionBuilder,
and 3ds Max models.

The historical Cats feature documentation is available in the
[archived project wiki](https://github.com/unofficalcats/Cats-Blender-Plugin-Unofficial-/wiki/Features).

## Install

Use a ZIP built as a Blender extension. In Blender 5.2, open **Edit >
Preferences > Get Extensions**, use the menu in the upper-right, choose
**Install from Disk**, select the Cats ZIP, and enable the extension.

Do not install the repository source ZIP downloaded from a hosting website.
That archive may have an extra wrapper directory and has not been validated by
Blender's extension builder.

## Build an installable ZIP

Run these commands from this repository directory with Blender 5.2 on the
system:

```text
blender --command extension validate .
blender --command extension build --source-dir . --output-filepath Cats-Blender-Plugin-5.2.0.zip
blender --command extension validate Cats-Blender-Plugin-5.2.0.zip
python tests/verify_package.py Cats-Blender-Plugin-5.2.0.zip --source-dir .
```

On Windows, replace `blender` with the full path to `blender.exe` if Blender is
not available on the command line. The build rules intentionally exclude test
code, repository metadata, caches, and user-specific mutable state.

## Updates

Automatic updates are intentionally disabled until this personal fork has its
own release repository. This prevents the archived upstream project from
overwriting the Blender 5.2 build. A maintainer can re-enable updates by setting
the fork-owned `UPDATE_REPOSITORY`, `UPDATE_API_URL`, and `UPDATE_DEV_BRANCH`
constants in `updater.py`.
