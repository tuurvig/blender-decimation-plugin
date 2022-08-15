# Decimace - Kvasnica

## Instalace:

**WARNING:** Plugin byl psán ve verzi Blenderu 2.90.1, je vyžadována verze alespoň 2.80, u starších verzích je zaručena nekompatibila díky změnám v Blender API.


### Python script [Decimation.py](source/Decimation.py)
- Otevřít script v blender script editoru nebo tento zdrojový kód nakopírovat do Text Editoru. Spustit daný script a plugin se zaregistruje. Pro spuštění stačí v objekt módu vybrat objekt k decimaci a pomocí vyhledávání najít "Kvasnica Decimator". 

![Run Script](img/run.jpg)

# Decimace

## Zadání:
- Vytvořte plug-in do Blenderu, který sofistikovaně snižuje složitost meshe (snížení počtu trojúhelníků)
- Plugin by měl bý sofistikovanější metodou než jakou nabízí sám blender.
- Parametricky decimovat mesh objektu.

### Metoda Vertex Clustering
- Rozkouskujeme bounding box decimovaného objektu na buňky. Do každé buňky může zapadnout více vrcholů naráz, ze kterých se vypočítá nový reprezentativní vrchol. Pokud některé vrcholy v buňce byly propojeny s vrcholy jiných buněk, tak bude existovat hrana i mezi reprezentativními vrcholy těchto sousedních buněk.

- Algoritmus má výhodu v tom, že má lineární výpočetní náročnost nad množinou n vrcholů O(n), ale výsledná mřížka při větší úrovni decimace rychle ztrácí detaily a nemusí být dostačující.

### Algoritmus:
![Algorithm](img/algo.jpg)
1. **Oznámkování vrcholů** - Pro každý vrchol se vypočítá jeho váha, která závisí na dvou faktorech.
    - pravděpodobnost, že vrchol leží v siluetě objektu z libovolného směru pohledu
    - velikost stěn, které jsou vázány tímto vrcholem

2. **Triangulace mřížky** - všechny polygony jsou převedeny na trojúhelníky. (Každý face má jenom tři vrcholy)

3. **Shlukování vrcholů** - Vytvořit buňky (kvádry uvnitř bounding boxu objektu) podle zadané velikosti a přiřadit k nim vrcholy, které v nich leží.

![Mesh](img/mesh.jpg)

4. **Syntéza** - Vypočítání reprezentativního vrcholu pro každou buňku, která obsahuje alespoň jeden vrchol původního objektu. Tento vrchol bude v nové zjednodušené mřížce nahrazovat všechny, které spadly do té jedné buňky. Spočítán jako vážený průměr vrcholů podle váhy každého vrcholu v buňce.

5. **Eliminace** - Eliminuje duplicitní trojúhelníky, vrcholy a hrany.

6. **Seřízení normál** - normály výsledných polygonů by neměly ukazovat dovnitř objektu.

### Poznámky
- Plugin vytváří nový objekt, tak aby původní zůstal nezměněný. Triangulace se provádí nad kopií decimovaného objektu.

- Při dokončení pluginu se zneviditelní původní objekt a na jeho místo se posadí nový zjednodušený.

- Bylo implementováno zlepšení ohodnocování vrcholů. Místo `1/theta` bylo použito `cos(theta/2)` pro lepší odhad váhy vrcholu. `theta` - maximální úhel mezi dvěma hranami vrcholu

- Normály byly seřízeny pomocí přidávání nových ploch do nového meshe ve stejném pořadí jakém byli získány ze struktury.

```python

# Get list of cell indices of the face (max 3 items, mesh is triangulated)
newFaceIndicies = [ v.index for v in face.verts ]
# get list of new vertices by searching
newFace = [ simpleVertDict[i] for i in newFaceIndicies ]
# add new face to final mesh
self.NewMesh.faces.new(newFace)
                
```

- Zdroje: [mtu.edu](https://pages.mtu.edu/~shene/COURSES/cs3621/SLIDES/Simplification.pdf), [comp.nus.edu.sg](https://www.comp.nus.edu.sg/~tants/Paper/simplify.pdf)


# Ukázky výstupů

## UV Sphere
- ~65K vrcholů
### Level decimace 1.5
- 185 vrcholů
- 366 trojúhelníků
![sphere1.5](examples/sphere1.5.jpg)

## Stanford Bunny
- 34817 vrcholů
- 69630 trojúhelníků

### Level decimace 0.5
- 1456 vrcholů
- 2944 trojúhelníků
![bunny0.5](examples/bunny0.5.jpg)

### Level decimace 0.15
- 13894 vrcholů
- 27841 trojúhelníků
![bunny0.15](examples/bunny0.15.jpg)

## Armadillo
- 106289 vrcholů
- 212574 trojúhelníků

### Level decimace 0.73
- 635 vrcholů
- 1327 trojúhelníků
![armadillo0.73](examples/armadillo0.73.jpg)

### Level decimace 0.2
- 8117 vrcholů
- 16618 trojúhelníků
![armadillo0.2](examples/armadillo0.2.jpg)

# Plug-in

## Uživatelské prostředí
![UI](img/ui.jpg)

- Level of decimation - určuje jak velké mají být jednotlivé buňky. Čím vyšší číslo, tím větší decimace. Např při zadání 1.0 se vytvoří buňka, kde každá zabere 10% šířky na každé ose bounding boxu daného objektu.

```python

# xyz dimensions of one cell
unit = level * self.Dimension

```

- `level` - float z uživatelského vstupu level of decimation
- `self.Dimenstion` - vektor držící rozměry bounding boxu decimovaného objektu
- `unit` - rozměry jedné buňky (cell)

## Třídy

### Cell (Buňka)
- drží svůj identifikátor
- obsahuje seznam vrcholů, které se v ní nachází. 
```python
class Cell:
    def __init__(self, id):
        # cell identifier
        self.Index = id
        # vertices in this cell. VertexInfoContainer references
        self.Verts = []
```
### VertexInfoContainer
- drží referenci pro vertex v bmesh vert
- při konstrukci vypočítá svojí váhu

```python
class VertexInfoContainer:
    def __init__(self, v):
        # BMesh.Vert reference
        self.Vertex = v
        # Vertex weight evaluation function
        self.Grade = math.cos(self.GetMaxAngle()/2)
```

- výpočet maximálního úhlu:

```python
def GetMaxAngle(self):
    res = sys.float_info.min
    edges = self.Vertex.link_edges
    
    # Foreach combination of twoedges. Combinations are unique.means no (3,2) and (2,3)
    for edge in combinations(edges,2):
        # edge vector
        ev1 = edge[0].verts[0].co -edge[0].verts[1].co
        ev2 = edge[1].verts[0].co -edge[1].verts[1].co
        
        #angle between edge vectors in radians
        tmp = abs(ev1.angle(ev2))
        
        if tmp > res:
            res = tmp
    
    return res
```

### DecimatingObj
- třída, která potřebuje pro konstrukci nějaký blender objekt
```python
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
```
- vytvoří se kopie vstupovaného objektu, ze kterého se získá mesh.
- vytvoří nový mesh pro výstupní objekt
- inicializuje dva prázdné slovníky. 
    - slovník pro buňky, které používají jako klíč tuple se souřadnicemi x, y, z
    - slovník reprezentantů, které mají klíč jako index buňky, kterou reprezentují
- bmeshe se uvolní při destrukci v metodě `__exit__`

### KvasnicaDecimator
- tělo registrované třídy
```python
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
```

