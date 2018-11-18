#
#   packislands.py
#
#   Originally from "iceythe" on Blender Artists.
#   November, 2018
#
#   This is a workaround for Blender's apparent inability to 
#   pack UV islands from the "data" level. So it's
#   necessary to emulate the steps a user would go
#   through in the user interface.
#
#   There may be some way to do this at the data level, but
#   it's not documented as of Blender 2.79.
#
import bpy

def core(obj, rotate, margin):
    """
    Actually do the packing
    """
    assert obj.type == 'MESH', "Must be mesh"
    me = obj.data
    assert not me.validate(), "Mesh invalid before UV packing"
    assert bpy.context.mode == 'OBJECT', "Must be in object mode to set active objects"
    print("Entered core")
    bpy.context.scene.objects.active = obj
    bpy.ops.object.editmode_toggle()          # to edit mode
    print("In edit mode")
    bpy.ops.uv.select_all(action='SELECT')    # select all faces
    print("About to pack islands. Rotate=%s, margin=%1.2f" % (str(rotate), margin))
    bpy.ops.uv.pack_islands(rotate=rotate, margin=margin)         # pack islands
    print("pack_islands completed.")
    bpy.ops.object.editmode_toggle()
    assert not me.validate(), "Mesh invalid after UV packing"


def pack_uvs(input, rotate=False, margin=0.0):
    """
    Pack UV regions in the selected object(s)
    """
    print("bpy.context: %s" % (str(dir(bpy.context)),))  # ***TEMP***    
    oldselection, oldao, oldeditmode = bpy.context.selected_objects, bpy.context.active_object, bpy.context.mode # save UI state
    try: 
        if bpy.context.mode != 'OBJECT':              # pre-set required object mode
            bpy.ops.object.editmode_toggle()      # now in Object mode
                   
        if type(input) is list:             # if input is Python list
            for obj in input:
                if obj.type == 'MESH':
                    if obj.data.uv_textures:
                        core(obj, rotate, margin)

        elif type(input) is bpy.types.Object: # if input is single object
            if input.type == 'MESH':
                if input.data.uv_textures:
                    core(input, rotate, margin)                    
        else:
            raise ValueError("Invalid input type to pack_uvs")
    finally:
        #   Restore UI state
        for obj in bpy.data.objects:           # restore selection
            obj.select = False if not obj in oldselection else True
        bpy.context.scene.objects.active = oldao  # restore active object set
        if bpy.context.mode != oldeditmode:       # restore edit/object mode
            bpy.ops.object.editmode_toggle()  
    


if __name__ == "__main__" :             # unit test, packs selected object
    pack_uvs(bpy.context.selected_objects)
