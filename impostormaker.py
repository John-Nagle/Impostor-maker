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
import mathutils
import collections
#
#   Constants
#
DRAWABLE = ['MESH', 'CURVE', 'SURFACE', 'META', 'FONT', 'ARMATURE', 'LATTICE']      # drawable types

NORMALERROR = 0.001                     # allowed difference for two normals being the same

class ImpostorFace :
    """
    Face of an impostor object.
    
    Contains one or more polygons, all coplanar.
    """        
    def __init__(self, context, target, poly) :
        self.normal = None                  # no normal yet
        self.polys = [poly]                 # polygons
        self.vertexids = set()              # empty set
        self.edgeids = set()                # set of pairs of vertex IDs
        me = target.data
        vertices = me.vertices
        if poly.loop_total < 3 :            # can't compute a normal
            raise RuntimeError("A face of \"%s\" has less than 3 vertices." % (target.name,))
        #   We need a normal for the face. Not a graphics normal, a geometric one based on the vertices.
        #   Get a list of coordinates
        vertexcoords = []
        meloop = me.loops[poly.loop_start : poly.loop_start + poly.loop_total]                # vertices in this loop
        for loop_index in range(len(meloop)) :
            vid0 = meloop[loop_index].vertex_index
            vid1 = meloop[(loop_index + 1) % poly.loop_total].vertex_index # next, circularly
            vid2 = meloop[(loop_index + 2) % poly.loop_total].vertex_index # next, circularly
            print("    Loop index %d: Vertex indices: %d %d %d" % (loop_index, vid0, vid1, vid2))  
            #   Get two successive vertices to get an edge ID
            self.edgeids.add(tuple(sorted((vid0, vid1))))
            self.vertexids.add(vid0)        # add to set
            coords = me.vertices[vid0].co
            vertexcoords.append(coords)         
            ####print("    Old Vertex: %d: (%1.4f,%1.4f,%1.4f)" % (vid0, coords[0],coords[1],coords[2]))
            #   Get two successive edges to get a normal for the face              
            v0 = me.vertices[vid0].co       # get 3 points, wrapping around
            v1 = me.vertices[vid1].co
            v2 = me.vertices[vid2].co
            print("    Vertex: %d: (%1.4f,%1.4f,%1.4f)" % (vid0, v0[0],v0[1],v0[2]))
            cross = (v1-v0).cross(v2-v1)    # direction of normal
            print("   Cross: " + str(cross))
            if cross.length < NORMALERROR : # collinear edges - cannot compute a normal
                print("  Cross length error: %f" % (cross.length))
                continue                    # skip this edge pair
            cross.normalize()               # normal vector, probably
            if self.normal :
                if self.normal.dot(cross) < 1.0 - NORMALERROR :
                    raise RuntimeError("A face of \"%s\" is not flat." % (target.name,))
            else :
                self.normal = cross         # we have a face normal
        if not self.normal :
            raise RuntimeError("Unable to compute a normal for a face of \"%s\"." % (target.name,)) # degenerate geometry of some kind    
        print("  Face normal: (%1.4f,%1.4f,%1.4f)" % (self.normal[0],self.normal[1],self.normal[2]))   
        
    def getedgeids(self) :
        """
        Return set of edge tuples for this face
        """
        return self.edgeids                    
            
        
    def merge(self, otherface) :            # merge in another face
        if (not self.normal) or (not otherface.normal) :
            return False                    # merge fails
        if self.normal.dot(otherface.normal) < (1.0 - NORMALERROR) :
            return False                    # not coplanar, no merge
        if not self.edgeids.intersection(otherface.edgeids) :
            return False                    # must have a common edge
        self.polys.extend(otherface.polys)      # merge
        self.edgeids = self.edgeids.union(otherface.edgeids)    
        return True
        
    def dump(self) :
        print("Face: %d polys, %d vertices, normal (%1.4f,%1.4f,%1.4f)" %  (len(self.polys), len(self.vertexids), self.normal[0],self.normal[1],self.normal[2]))  
    


class ImpostorMaker(bpy.types.Operator) :
    """Impostor maker"""                # blender will use this as a tooltip for menu items and buttons.
    #   Class static variables
    bl_idname = "object.impostor_maker" # unique identifier for buttons and menu items to reference.
    bl_label = "Make impostor"          # display name in the interface.
    bl_options = {'REGISTER', 'UNDO'}   # enable undo for the operator.
    
    def __init__(self) :
        """ Constructor """
        pass
    
    def errormsg(self, msg) :
        print("ERROR: " + msg)           # ***TEMP*** until we find a better way

    def execute(self, context):         # execute() is called by blender when running the operator.
        #   Do the work here
        print("Impostor maker starting.")           # ***TEMP***
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
        
        ####me = context.object.data
        me = target.data
        ####uv_layer = me.uv_layers.active.data
        faces = []
        #   Polygons seem to have no particular order. Successive ones may not be on the same face.
        #   So we have to do our own merging.
        for poly in me.polygons:
            print("Polygon index: %d, length: %d" % (poly.index, poly.loop_total))
            faces.append(ImpostorFace(context, target, poly))       # build single poly face objects
        # Merge faces if they have the same normal and an edge in common.
        
        print("Before merge")
        for f in faces :
            f.dump()
        #   Build list of which edges are in which faces
        edgeusage = {}
        for face in faces :
            for edge in face.getedgeids() :
                if edge in edgeusage :
                    edgeusage[edge].append(face) 
                else :
                    edgeusage[edge] = [face]
        #   Try to merge faces which share an edge
        faceset = set(faces)
        print(edgeusage)     ## ***TEMP***
        for edge, faces in edgeusage.items() :
            if len(faces) > 2  or len(faces) < 1:
                raise RuntimeError("Bad geometry: %d faces of \"%s\" share an edge." % (len(faces),target.name)) # degenerate geometry of some kind
            if (len(faces) == 2) :                              # attempt merge
                if faces[0].merge(faces[1]) :
                    faceset.remove(faces[1])
        print("After merge")
        for f in faceset :
            f.dump()
                
            
        

