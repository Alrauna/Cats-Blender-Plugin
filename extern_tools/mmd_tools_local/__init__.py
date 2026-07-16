# Copyright 2012 MMD Tools authors
# This file is part of MMD Tools.

# MMD Tools is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# MMD Tools is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.


bl_info = {
    "name": "mmd_tools_local",
    "author": "sugiany",
    "version": (5, 0, 0),
    "blender": (5, 2, 0),
    "location": "View3D > Sidebar > MMD Panel",
    "description": "Utility tools for MMD model editing. Bundled for Blender 5.2 LTS",
    "warning": "",
    "doc_url": "https://mmd-blender.fandom.com/wiki/mmd_tools_local",
    "wiki_url": "https://mmd-blender.fandom.com/wiki/mmd_tools_local",
    "tracker_url": "https://github.com/UuuNyaa/blender_mmd_tools_local/issues",
    "support": "COMMUNITY",
    "category": "Object",
}

mmd_tools_local_VERSION = ".".join(map(str, bl_info["version"]))

import os

PACKAGE_PATH = os.path.dirname(__file__)
PACKAGE_NAME = __package__


from . import auto_load

auto_load.init(PACKAGE_NAME)


def register():
    import bpy

    from . import handlers

    auto_load.register()

    # pylint: disable=import-outside-toplevel
    from .m17n import translations_dict

    bpy.app.translations.register(PACKAGE_NAME, translations_dict)

    handlers.MMDHanders.register()


def unregister():
    import bpy

    from . import handlers
    from .core.sdef import FnSDEF

    handlers.MMDHanders.unregister()
    FnSDEF.unregister_driver_function()
    FnSDEF.clear_cache()

    try:
        bpy.app.translations.unregister(PACKAGE_NAME)
    except (RuntimeError, ValueError):
        pass

    auto_load.unregister()


if __name__ == "__main__":
    register()
