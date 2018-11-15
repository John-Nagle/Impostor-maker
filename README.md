# Impostor-maker
Blender impostor maker for creating Second Life content

PRE-ALPHA - suggested for developers only at this time.

# Installation
(To be provided)

After installation, there should be a "Make Impostor" item in the Object menu.

# Usage instructions (preliminary)

Start with a high-detail 3D model. Build a low-detail model around it.
Try enclosing it with a cube as a first try. This is enough for squared off
buildings. The low-detail model must be one object, and it must be located
in the same place as the high-detail model. It doesn't have to be in the same
layer.

Make sure the high-detail model and low-detail model are both visible. Turn off
rendering for any irrelevant objects in the scene. Set Cycles renderer.
Select the low-detail model. Click on Object->Make Impostor. Wait while it renders.
It takes a few seconds per face in the low-detail model.

The high-detail model is rendered from the viewpoint of each face of the low-detail model,
and that gets pasted on the appropriate face of the low-detail model. Material generation
and UV setup is automatic. The material and image will be named "IMP-<name of object>"

Unlike Blender baking, you do not have to adjust object scales or centers. That's all automatic. 

# Limitations and bugs

Currently, the output image is always 512 wide, and as high as it has to be to fit all the faces.
Packing of all the faces into the image is inefficient.

Display of the impostor in "Rendered" setting does not have proper alpha transparency. "Textured" 
is OK.  This does not affect the generated impostor; it's just a Blender problem.


