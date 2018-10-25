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
#   Impostor maker, where the work gets done.
#
import bpy
#
#   Constants
#
DRAWABLE = ['MESH', 'CURVE', 'SURFACE', 'META', 'FONT', 'ARMATURE', 'LATTICE']      # drawable types

class ImpostorMaker(bpy.types.Operator) :
    """Impostor maker"""                # blender will use this as a tooltip for menu items and buttons.
    bl_idname = "object.impostor_maker" # unique identifier for buttons and menu items to reference.
    bl_label = "Make impostor"          # display name in the interface.
    bl_options = {'REGISTER', 'UNDO'}   # enable undo for the operator.
    
    def errormsg(self, msg) :
        print("ERROR: " + msg)           # ***TEMP*** until we find a better way

    def execute(self, context):         # execute() is called by blender when running the operator.
        #   Do the work here
        print("Impostor maker 2 starting.")           # ***TEMP***
        #   Target impostor is last selected object.
        #   Objects to render are all other selected objects.
        #   If only one object is selected, it is the impostor, 
        #   and all other visible objects will be rendered.
        if not context.selected_objects :
            self.errormsg("Nothing selected.")
            return {'FINISHED'}
        target = context.selected_objects[-1]   # target impostor
        if target.type != 'MESH' :
            self.errormsg("Impostor must be mesh.")
            return {'FINISHED'}
        sources = context.selected_objects[:-1] # source objects
        if not sources :                # if no source objects
            sources = [obj for obj in context.visible_objects if obj != target] # everything but target
        sources = [obj for obj in sources if obj.type in DRAWABLE]  # only drawables
        if not sources :
            self.errormsg("Nothing drawable to draw on the impostor.")
            return {'FINISHED'}
        self.buildimpostor(context, target, sources)
        return {'FINISHED'}             # this lets blender know the operator finished successfully.
        
    def buildimpostor(self, context, target, sources) :
        print("Target: " + target.name) 
        print("Sources: " + ",".join([obj.name for obj in sources]))
        

