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
bl_info = {
    "name": "Impostor maker",
    "author": "John Nagle",
    "version": (1, 0, 0),
    "blender": (2, 78, 0),
    "location": "Object > Second Life",
    "description": "Impostor object generator for Second Life",
    "category": "Object",
    "support" : "Testing",
}
 
import bpy

class ImpostorMaker(bpy.types.Operator) :
    """Impostor maker"""                # blender will use this as a tooltip for menu items and buttons.
    bl_idname = "object.impostor_maker" # unique identifier for buttons and menu items to reference.
    bl_label = "Make impostor"          # display name in the interface.
    bl_options = {'REGISTER', 'UNDO'}   # enable undo for the operator.

    def execute(self, context):         # execute() is called by blender when running the operator.
        #   Do the work here

        return {'FINISHED'}             # this lets blender know the operator finished successfully.

#   Connect to Blender menu system        
def menu_func(self, context) :
    self.layout.operator(ImpostorMaker.bl_idname,
        text=Move2Operator.__doc__,  
        icon='PLUGIN')

def register() :
    bpy.utils.register_class(ImpostorMaker)
    bpy.types.VIEW3D_MT_object.append(menu_func)

def unregister() :
    bpy.utils.unregister_class(ImpostorMaker)
    bpy.types.VIEW3D_MT_object.remove(menu_func)

    
if __name__ == "__main__":              # for debug
    register()

