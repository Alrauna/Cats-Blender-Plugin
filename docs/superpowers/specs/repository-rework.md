# Spec: repository rework and maintainer transition

Decisions recorded 2026-08-06. Delete from `main` when the milestone is
complete.

## Goal

Present this repository as Alrauna's maintained fork rather than a continuation
of Team Neoneko's archived project, with credit to prior maintainers preserved,
then reduce the branch topology to what this fork actually maintains.

## Decisions

**README.** `main` gets the `Welcome` branch README's structure — intro, Blender
version support, features, requirements, installation, help, acknowledgements —
with the accurate 5.2 build and updater content from the current `blender-52`
README folded in. The `Welcome` branch's content is absorbed here, so deleting
that branch loses no user-facing prose.

**Maintainer identity.** Alrauna is the current maintainer. Prior maintainers are
credited, not erased: Absolute Quantum with Hotox and GiveMeAllYourCats created
the original project; Team Neoneko, with Yusarina, maintained the unofficial fork
this one descends from. Named upstream contributors are carried forward verbatim:
Hotox, Shotariya, Neitri, Kiraver, Jordo, Ruubick, 989onan, rurre, Feilen,
triazo, Mysteryem.

989onan is a contributor, not a Team Neoneko maintainer. The only source claiming
otherwise was the upstream `CreditsPanel.maintainers2` string; the Welcome
README listed them under code contributors, `tools/importer.py` records their
work as donated to the project, and the commit record shows 2 commits against
Yusarina's 1311.

**Upstream wikis.** `teamneoneko` and `unofficalcats` are archived. Their wikis
remain the only feature documentation that exists, so links to them stay but are
labelled as archival and historical rather than current. No wiki is created for
this fork in this milestone.

**Material Combiner.** Repoint to `Alrauna/material-combiner-addon`, which
exists as a fork with a `blender-52` default branch. The current target,
`teamneoneko/material-combiner-addon`, is archived.

**Immersive Scaler.** Repoint to `Alrauna/immersive_scaler` once that fork
exists. It does not exist yet, so this is blocked on the maintainer. Do not
substitute `triazo/immersive_scaler`; the maintainer chose an owned fork.

**Translation dictionary.** `tools/translations.py` downloads from the archived
`teamneoneko/Cats-Blender-Plugin-Unofficial-translations` repository, branch
`5x-translations`. Repoint to an Alrauna fork once it exists, preserving that
branch name. Blocked on the maintainer. This is live runtime behavior: verify the
raw URL resolves before committing the change.

**Branch topology.** Keep `main` as default, plus `blender-52` and the
`blender-45` and `blender-45-dev` pair, because Blender 4.5 LTS is still
supported. Delete the other fifteen remote branches, delete the local
`blender-50`, and remove the `upstream` remote pointing at
`git.disroot.org/Neoneko`.

**Tags.** All 117 tags are kept, so the Releases tab and version history remain
intact. This includes the migration baseline tags.

**History preservation.** Nine of the branches slated for deletion have tips that
no tag reaches: `Welcome`, `blender-36-dev`, `blender-40`, `blender-40-dev`,
`blender-41`, `blender-41-dev`, `blender-42-dev`, `blender-43-dev`, and
`blender-44-dev`. Tag each as `archive/<branch>` before deleting, so deletion
does not silently discard commits the stated goal expects git to retain.

## Out of scope

Creating a wiki for this fork. Re-enabling the automatic updater. Changing the
`neoneko.xyz` support link or the upstream Discord references without a
maintainer decision on replacements.

## Risks

Non-English credit strings exist in `ja_JP`, `ko_KR`, and `zh_CN`. Machine
translation of a maintainer attribution is a poor idea; the English name stays
untranslated inside the localized sentence and the wording is flagged for
maintainer review.

Deleting remote branches and changing the default branch are outward-facing and
irreversible from this repository's side. Each requires explicit confirmation at
the moment of execution, not blanket approval from this spec.
