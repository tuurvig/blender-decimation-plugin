import sys
import bpy
import bmesh
import math 

from bpy.props import *
from itertools import combinations
from mathutils import Vector

bl_info = {
    "name": "Vertex Clustering Decimator",
    "author": "Richard Kvasnica",
    "blender": (2, 90, 1),
    "version": (1, 0, 0),
    "location": "View3D > Tools > Misc > Mesh Decimation",
    "description": "Reduces polygons in a mesh.",
    "warning": "",
    "wiki_url": "https://gitlab.fit.cvut.cz/BI-PGA/b201/kvasnric/tree/master/3D",
    "category": "Object"
}


def main(context):
    for ob in context.scene.objects:
        print(ob)


class Cell:
    def __init__(self, id):
        # cell identifier
        self.Index = id
        # vertices in this cell. BMesh.Vert references
        self.Verts = []
        
        
class VertexInfoContainer:
    def __init__(self, v):
        # BMesh.Vert reference
        self.Vertex = v
        # Vertex weight evaluation function
        self.Grade = math.cos(self.GetMaxAngle()/2)


    # Returns the widest angle between two edges of a vertex in radians
    def GetMaxAngle(self):
        res = sys.float_info.min
        edges = self.Vertex.link_edges
        
        # Foreach combination of two edges. Combinations are unique. means no (3,2) and (2,3)
        for edge in combinations(edges,2):
            # edge vector
            ev1 = edge[0].verts[0].co - edge[0].verts[1].co
            ev2 = edge[1].verts[0].co - edge[1].verts[1].co
            
            #angle between edge vectors in radians
            tmp = abs(ev1.angle(ev2))
            
            if tmp > res:
                res = tmp
        
        return res
            
        
# class for holding the decimating object
class DecimatingObj:
    # setups the decimating object
    def __init__(self, object):
        # Makes a copy of a original object
        self.Object = object.copy()
        self.Object.data = object.data.copy()
        self.Object.animation_data_clear()
        self.Object.name = "_" + object.name
        self.Dimension = object.dimensions
            
        bbLocal = [Vector(v) for v in object.bound_box]
        worldMat = object.matrix_world        
    
        # World coordinates of objects bounding box
        # operant @ is a matrix and vector multiplication operation. For some reason
        # Asterisk * is unsupported in blender 2.80 >= version and @ is unsupported in version < 2.80
        self.BoundBox = [worldMat @ v for v in bbLocal]
        
        minX = min([v.x for v in self.BoundBox])
        minY = min([v.y for v in self.BoundBox])
        minZ = min([v.z for v in self.BoundBox])
        self.Min = Vector((minX, minY, minZ))
        
        # Creates bmesh instance of the original objects mesh data
        self.Mesh = bmesh.new()
        self.NewMesh = bmesh.new()
        self.Mesh.from_mesh(self.Object.data)
        
        # Triangulate the mesh
        bmesh.ops.triangulate(self.Mesh, faces=self.Mesh.faces[:], quad_method='BEAUTY', ngon_method='BEAUTY')
        
        # Dictionary of decimated vertices ((key = cellIndex, value = new BMeshVert))
        self.simpleVertDict = dict()
        
        # Dictionary of cells (( key = tuple(x, y, z), value= Cell Class ))
        self.cellDict = dict()
        

    def Decimate(self, level):
        # xyz dimensions of one cell
        unit = level * self.Dimension
        
        self.CreateStructure(unit)
        self.VertexSynthesis()
        self.CreateFaces()
        
        self.Object.name = "decimated" + self.Object.name
        self.NewMesh.to_mesh(self.Object.data)
        
        
    # Creating data structure.
    # 1. Iterate through all vertices in input object mesh
    #    and create VertexInfoContainer out of all of them
    # 2. Calculate cell position for each vertex and add the cell to the dictionary
    # 3. Store cell indicies inside vertex blender object
    def CreateStructure(self, unit): 
        ct = self.cellDict  
        
        # cell index incrementing variable
        cells = 0

        # assigns every vertex to some cell
        for v in self.Mesh.verts:
            
            # vertexInfoContainer calculates weight for the vertex in constructor
            vert = VertexInfoContainer(v)
            
            # Get cell coordinates of a vertex by the unit
            cellCoords = self.getCell(vert, unit)
            
            # Check if cell coordinates are in the dictionary. If not, the function return None
            cell = ct.get(cellCoords)
            
            # Check if cell is None
            if not cell:
                # Create new cell with cell index
                cell = Cell(cells)
                cells += 1
                # Insert new cell to dictionary 
                ct[cellCoords] = cell
            
            # Stores Cell index inside blender vertex object
            vert.Vertex.index = cell.Index
            cell.Verts.append(vert)
            
    
    # Returns cell coordinates in object bounds
    def getCell(self, vert, unit):
        min = self.Min
        
        # Length of vert from a minimal coordinate corner of objects bounding box
        length = vert.Vertex.co - min
        
        # Coordinates of a cell
        xCor = min.x + unit.x * int( length.x / unit.x )
        yCor = min.y + unit.y * int( length.y / unit.y )
        zCor = min.z + unit.z * int( length.z / unit.z )
        return (round(xCor, 10), round(yCor, 10), round(zCor, 10))


    # Creates new blender vertices for simplified mesh 
    # by computing cell representatives based on their grade. 
    def VertexSynthesis(self):
        svd = self.simpleVertDict
        
        # Iterates through each cell in cell dictionary
        for c in self.cellDict.values():
            # Initiate weight and first vector position
            loc = Vector((0,0,0))
            weight = 0.0
            
            # Iterates through vertices inside one cell
            for v in c.Verts:
                # Calculate synthesised vector by multiplying vertex grade and its vector
                loc = loc + v.Grade * v.Vertex.co
                # add grade to overall weight
                weight += v.Grade
            
            # Divide weight from the location vector to get the resulting synthesised vertex     
            representant = loc/weight
            
            # Add a new vertex to a final simplified mesh
            newV = self.NewMesh.verts.new(representant)
            
            # Assing cell index to the new vertex
            newV.index = c.Index
            
            # Add the vertex to dictionary 
            svd[ newV.index ] = newV
    
    
    # Create new faces from original topology
    # 1. Iterate every original face
    # 2. Get Vertex indicies (which are stored cell indicies) of each cell
    # 3. If the original face has unique indicies, create new face in the new mesh
    def CreateFaces(self):
        # set of already created faces
        faces = set()
        svd = self.simpleVertDict
        
        # Iterate through every face in original mesh
        for f in self.Mesh.faces:
            # Get list of cell indices of the face (max 3 items, mesh is triangulated)
            newFaceIndicies = [ v.index for v in f.verts ]
            
            # create a frozenset (immutable) from indicies
            frSet = frozenset(newFaceIndicies)
            # Check if the vertices are unique and are not in result face set
            if len(frSet) > 2 and frSet not in faces:
                # get list of new vertices by searching
                newFace = [ svd[i] for i in newFaceIndicies ]
                # add a frozenset (hashable) to result face set 
                faces.add(frSet)
                # add new face to final mesh
                self.NewMesh.faces.new(newFace)
    
    
    def __exit__(self):
        self.Mesh.free()
        self.NewMesh.free()
    
        
    def LinkToScene(self):
        bpy.context.collection.objects.link(self.Object)
        

class KvasnicaDecimator(bpy.types.Operator):
    bl_idname = "object.kvasnica_decimator"
    bl_label = "Kvasnica Decimator"
    
    decimationLevel : FloatProperty(
        name = "Level of decimation",
        description = "Bigger the value, bigger the simplification of mesh",
        default = 0.01,
        min = 0.01,
        max = 2.0
    )
    
    # Invokes UI dialog of the plugin. After pressing OK, procedure will be executed.
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)
    
    
    def execute(self, context):
        original = bpy.context.active_object

        obj = DecimatingObj(original)
        
        #hides original object in viewport
        original.hide_set(True)
        
        obj.Decimate(self.decimationLevel/10)
        
        obj.LinkToScene()
        
        bpy.ops.object.select_all(action='DESELECT')
        obj.Object.select_set(True)
        
        return {'FINISHED'}


def menu_func(self, context):
    self.layout.operator(KvasnicaDecimator.bl_idname)


def register():
    bpy.utils.register_class(KvasnicaDecimator)
    bpy.types.VIEW3D_MT_object.append(menu_func)


def unregister():
    bpy.utils.unregister_class(KvasnicaDecimator)
    bpy.types.VIEW3D_MT_object.remove(menu_func)


if __name__ == "__main__":
    register()
