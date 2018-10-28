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
import bmesh
import mathutils
import math
#
#   Constants
#
DRAWABLE = ['MESH', 'CURVE', 'SURFACE', 'META', 'FONT', 'ARMATURE', 'LATTICE']      # drawable types

NORMALERROR = 0.001                     # allowed difference for two normals being the same

#   Non-class functions

def matrixlookat(eye, targetpt, up) :
    """
    Generate a LookAt matrix. Rotates to object pointing in dirvec with given up vector.
    
    From https://github.com/mono/opentk/blob/master/Source/OpenTK/Math/Matrix4.cs
    """
    z = eye - targetpt
    x = up.cross(z)
    y = z.cross(x)
    
    x.normalize()
    y.normalize()
    z.normalize()
    
    rot = mathutils.Matrix()
    rot[0][0] = x[0]
    rot[0][1] = y[0]
    rot[0][2] = z[0]
    rot[0][3] = 0
    rot[1][0] = x[1]
    rot[1][1] = y[1]
    rot[1][2] = z[1]
    rot[1][3] = 0
    rot[2][0] = x[2]
    rot[2][1] = y[2]
    rot[2][2] = z[2]
    rot[2][3] = 0
    
    # eye not need to be minus cmp to opentk 
    # perhaps opentk has z inverse axis
    tran = mathutils.Matrix.Translation(eye)
    return tran * rot
    
def addtestpoint(pos) :
    """
    Add visible small test point for debug
    """
    bpy.ops.mesh.primitive_cube_add(location=pos)
    bpy.context.object.name = "Testpt"
    bpy.context.object.scale = (0.1,0.1,0.1)                # apply scale
    
def vecmult(v0, v1) :
    """
    Element by element vector multiply, for scaling
    """
    return mathutils.Vector((v0[0]*v1[0], v0[1]*v1[1], v0[2]*v1[2]))



class ImpostorFace :
    """
    Face of an impostor object.
    
    Contains one or more polygons, all coplanar.
    """        
    def __init__(self, context, target, poly) :
        self.normal = None                  # normal in object coords
        self.vertexids = []                 # vertex indices into 
        self.baseedge = None                # (vertID, vertID)
        self.center = None                  # center of face, object coords
        self.facebounds = None              # size bounds of face, object scale
        self.scale = target.scale           # scale to world size
        self.worldtransform = target.matrix_world  # transform to global coords
        assert target.type == "MESH", "Must be a mesh target"
        me = target.data                    # mesh info
        vertices = me.vertices
        if poly.loop_total < 3 :            # can't compute a normal
            raise RuntimeError("A face of \"%s\" has less than 3 vertices." % (target.name,))
        #   We need a normal for the face. Not a graphics normal, a geometric one based on the vertices.
        #   We also need the base edge for the image and the center of the face.
        baseedgelength = -math.inf          # no base edge length yet
        meloop = me.loops[poly.loop_start : poly.loop_start + poly.loop_total]   # vertices of this loop
        for loop_index in range(len(meloop)) :
            #   Get 3 succesive vertices for 2 edges
            vid0 = meloop[loop_index].vertex_index
            vid1 = meloop[(loop_index + 1) % poly.loop_total].vertex_index # next, circularly
            vid2 = meloop[(loop_index + 2) % poly.loop_total].vertex_index # next, circularly
            ####print("    Loop index %d: Vertex indices: %d %d %d" % (loop_index, vid0, vid1, vid2))  
            #   Get two successive edges to get a normal for the face              
            v0 = me.vertices[vid0].co       # get 3 points, wrapping around
            v1 = me.vertices[vid1].co
            v2 = me.vertices[vid2].co
            self.vertexids.append(vid0)     # save edge index
            print("    Vertex: %d: (%1.4f,%1.4f,%1.4f)" % (vid0, v0[0],v0[1],v0[2]))
            cross = (v1-v0).cross(v2-v1)    # direction of normal
            #### print("   Cross: " + str(cross))
            if cross.length < NORMALERROR : # collinear edges - cannot compute a normal
                print("  Cross length error: %f" % (cross.length))  # ***TEMP*** this is OK, not an error
                continue                    # skip this edge pair
            cross.normalize()               # normal vector, probably
            if self.normal :
                if self.normal.dot(cross) < 1.0 - NORMALERROR :
                    raise RuntimeError("A face of \"%s\" is not flat." % (target.name,))
            else :
                self.normal = cross             # we have a face normal
            #   Find longest edge. This will orient the image.
            ###edge = v1-v0
            ###edge = mathutils.Vector((edge[0]*target.scale[0], edge[1]*target.scale[1], edge[2]*target.scale[2])) # there is no mathutils fn for this
            edge = vecmult(v1 - v0, target.scale)  # element by element multiply
            edgelength = edge.length
            if edgelength > baseedgelength :
                baseedgelength = edgelength     # new winner
                self.baseedge = (v0, v1)        # save longest edge coords
            #   Compute center of face. Just the average of the corners.
            if not self.center :
                self.center = v0
            else :
                self.center = self.center + v0  # sum the vertices
        #   All vertices examined.  
        self.center = self.center / poly.loop_total # average to get center of face         
        if not self.normal :
            raise RuntimeError("Unable to compute a normal for a face of \"%s\"." % (target.name,)) # degenerate geometry of some kind    
        print("  Face normal: (%1.4f,%1.4f,%1.4f)" % (self.normal[0],self.normal[1],self.normal[2])) 
        #   Compute bounding box of face.  Use longest edge to orient the bounding box
        #   This will be the area of the image we will take and map onto the face.
        
        faceplanemat = self.getfaceplanetransform()                                 # transform points onto face
        faceplanematinv = faceplanemat.copy()
        faceplanematinv.invert()
        print(faceplanemat)
        print(faceplanematinv)
        pts = [faceplanematinv * me.vertices[vid].co for vid in self.vertexids]        # points transformed onto face, now 2D
        ####pts = [faceplanemat * vecmult(self.scale,me.vertices[vid].co) for vid in self.vertexids]        # points transformed onto face, now 2D
        ####  Scaled points did not  have zero Z coord, so not on face plane
        for pt in pts :                                                             # all points must be on face plane
            assert abs(pts[0][2]  < 0.01), "Internal error: Vertex not on face plane"   # point must be on face plane
        minx = min([pt[0] for pt in pts])                                           # size per max excursion in X
        miny = min([pt[1] for pt in pts])                                           # size per max excursion in X
        maxx = max([pt[0] for pt in pts])                                           # size per max excursion in X
        maxy = max([pt[1] for pt in pts])                                           # size per max excursion in X
        ####sizex = 2*max(max([pt[0] for pt in pts]), -min([pt[0] for pt in pts]))      # size per max excursion in X
        ####sizey = 2*max(max([pt[1] for pt in pts]), -min([pt[1] for pt in pts]))      # size per max excursion in Y
        ####self.facebounds = (sizex, sizey)                                            # scaled of bounds
        #    Compute bounding box in face plane coordinate system
        lowerleft = faceplanemat * mathutils.Vector((minx, miny, 0.0))              # we have to transfer these back to obj coords to scale
        upperright = faceplanemat * mathutils.Vector((maxx, maxy, 0.0))
        newcenter = (lowerleft + upperright)*0.5                                    # in face coords
        lowerleft = vecmult(lowerleft, self.scale)                                  # must scale in face coords
        upperright = vecmult(upperright, self.scale)
        lowerleft = faceplanematinv * lowerleft
        upperright = faceplanematinv * upperright
        width = upperright[0] - lowerleft[0]
        height = upperright[1] - lowerleft[1]
        self.facebounds = (width, height)
        ####newcenter = faceplanemat * center                                           # transform center back to object coords
        pxx = faceplanematinv * (faceplanemat * self.center) 
        assert (self.center - pxx).length < 0.001, "Inverse transform failed"
        #   Compute size
        ###self.facebounds = (maxx - minx, maxy - miny)
        #   Re-center
        ####newcenter = mathutils.Vector(((maxx + minx)*0.5, (maxy + miny)*0.5, pts[0][2]))  # new center in face coords (all have same Z coord)
        #   ***NEED TO DESCALE
        ####newcenter = faceplanemat * newcenter                                      # transform back into object coords
        print("Old center: %s  New center: %s" % (str(self.center), str(newcenter)))
        self.center = newcenter                                                     # and use it
        print("Face size, scaled: %f %f" % (self.facebounds))                     # ***TEMP***
        for pt in pts :
            print (pt)                                               ##  ***TEMP***
        ###for pt in pts :                                                 # ***TEMP***
        ###    addtestpoint(pt)
        #   ***MORE***
        
    def getfaceplanetransform(self) :
        """
        Calculate a transform which will transform coordinates of the face into
        local coordinates such that 
        1) X axis is aligned with self.baseedge
        2) Z axis is aligned with normal and +Z is in the normal direction
        3) Origin is at self.center      
        """
        #### print("Base edge" + str(self.baseedge))    # ***TEMP***
        xvec = self.baseedge[1] - self.baseedge[0]                      # +X axis of desired plane, perpendicular to normal
        upvec = xvec.cross(self.normal)                                 # up vector
        orientmat = matrixlookat(self.center, self.center + self.normal, upvec)     # rotation to proper orientation 
        return orientmat                                                
                       
    def getcameratransform(self, disttocamera = 5.0) :
        xvec = self.baseedge[1] - self.baseedge[0]                      # +X axis of desired plane, perpendicular to normal
        upvec = xvec.cross(self.normal)                                 # up vector
        orientmat = matrixlookat(self.center, self.center - self.normal, upvec)     # rotation to proper orientation 
        camerapos = self.center + self.normal*disttocamera              # location of camera, local coords
        posmat = mathutils.Matrix.Translation(camerapos)
        return self.worldtransform * (posmat * orientmat)               # camera in world coordinates
        
    def getcameraorthoscale(self) :
        """
        Get camera orthographic scale.
        (h,v)
        """
        pass
        
        
    def getedgeids(self) :
        """
        Return set of edge tuples for this face
        """
        return self.edgeids                    
                    
    def dump(self) :
        """
        Debug output
        """
        print("Face:  %d vertices, normal (%1.4f,%1.4f,%1.4f), center (%1.4f,%1.4f,%1.4f)" % 
            (len(self.vertexids), self.normal[0], self.normal[1], self.normal[2], self.center[0], self.center[1], self.center[2])) 
    


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
        print("ERROR: " + msg)          # ***TEMP*** until we find a better way

    def execute(self, context):         # execute() is called by blender when running the operator.
        """
        Target impostor is last selected object.
        Objects to render are all other selected objects.
        If only one object is selected, it is the impostor, 
        and all other visible objects will be rendered.
        """
        if not context.selected_objects :
            self.errormsg("Nothing selected.")
            return {'FINISHED'}
        target = context.selected_objects[-1]       # target impostor
        if target.type != 'MESH' :
            self.errormsg("Impostor \"%s\"must be a mesh." % (target.name,))
            return {'FINISHED'}
        sources = context.selected_objects[:-1]     # source objects
        if not sources :                            # if no source objects
            sources = [obj for obj in context.visible_objects if obj != target] # everything but target
        sources = [obj for obj in sources if obj.type in DRAWABLE]  # only drawables
        if not sources :
            self.errormsg("Nothing drawable to draw on the impostor.")
            return {'FINISHED'}
        self.buildimpostor(context, target, sources)
        return {'FINISHED'}                         # this lets blender know the operator finished successfully.
                
    def limiteddissolve(self, context, target) :
        """
        Do a limited dissolve on the target object to combine coplanar triangles into big faces.
        """
        BREAKANGLE = math.radians(0.1)              # must be very flat
        bm = bmesh.new()                            # get working mesh
        bm.from_mesh(target.data)                   # load it from target object
        #   Limited dissove with very shallow break angle
        bmesh.ops.dissolve_limit(bm, angle_limit=BREAKANGLE, verts=bm.verts, edges=bm.edges)
        bm.to_mesh(target.data)                     # put back in original object
        target.data.update()                        # and update the target
        bm.clear()                                  # clean up
        bm.free()
    
    def buildimpostor(self, context, target, sources) :
        print("Target: " + target.name) 
        print("Sources: " + ",".join([obj.name for obj in sources]))  
        #   Do a limited dissolve on the target object to combine coplanar triangles into big faces. 
        self.limiteddissolve(context, target)     
        faces = []
        for poly in target.data.polygons:
            faces.append(ImpostorFace(context, target, poly))       # build single poly face objects
        print("Faces")
        for f in faces :
            f.dump()
        #   Test by moving camera to look at first face
        for face in faces:
            ####face = faces[0]
            camera = bpy.data.objects['Camera']
            bpy.data.cameras['Camera'].type = 'ORTHO'
            bpy.data.cameras['Camera'].ortho_scale = 4.0
            #   Add an object to test the transformation
            pos = face.worldtransform * face.center                 # dummy start pos
            bpy.ops.mesh.primitive_cube_add(location=pos)
            bpy.context.object.name = "Cube1"
            xform = face.getfaceplanetransform()                    # get positioning transform
            xformworld = face.worldtransform * xform                # in world space
            bpy.context.object.matrix_world = xformworld            # apply rotation
            bpy.context.object.scale = mathutils.Vector((face.facebounds[0], face.facebounds[1], 0.1))*0.5                  # apply scale
            #   Place camera
            camera.matrix_world = face.getcameratransform()
            break   # only 1st point for now

        
        

