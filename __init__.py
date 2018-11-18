#
#   Impostor maker for Second Life
#
#   Renders selected objects orthographically and puts
#   those images on the faces of the last-selected object.
#
#   John Nagle
#   October, 2018
#   License: GPL 3
#
#   Init file
#
import bpy
import importlib
from . import impostormaker
importlib.reload(impostormaker)                                 # force a reload. Blender will not do this by default.

bl_info = {
    "name": "Impostor maker",
    "author": "John Nagle",
    "version": (1, 0, 5),
    "blender": (2, 78, 0),
    "location": "Object > Second Life",
    "description": "Impostor object generator for Second Life",
    "category": "Object",
    "support" : "Testing",
}

#   Connect to Blender menu system        
def menu_func(self, context) :
    self.layout.operator(impostormaker.ImpostorMaker.bl_idname) 

def register() :
    bpy.utils.register_class(impostormaker.ImpostorMaker)
    bpy.types.VIEW3D_MT_object.append(menu_func)

def unregister() :
    bpy.utils.unregister_class(impostormaker.ImpostorMaker)
    bpy.types.VIEW3D_MT_object.remove(menu_func)

    
if __name__ == "__main__":              # for debug
    register()

