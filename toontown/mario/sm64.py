"""Panda3D Mario mesh adapter based on TheFlowerVixen/libsm64-panda (MIT).

The ctypes declarations below follow libsm64.h at fd11813208272b4271d92bd92feb8f3fdbe61be5.
Only the mesh, texture, and input path are used; Toontown controls world movement.
"""

import ctypes as ct
import hashlib
import math
import sys
from pathlib import Path

from panda3d.core import (
    Filename, Geom, GeomNode, GeomTriangles, GeomVertexData, GeomVertexFormat,
    GeomVertexWriter, NodePath, PNMImage, SamplerState, Shader, Texture,
)


LIBRARY_NAMES = {'win32': 'sm64.dll', 'linux': 'libsm64.so', 'darwin': 'libsm64.dylib'}
ROM_SIZE = 8 * 1024 * 1024
ROM_SHA1 = '9bef1128717f958171a4afac3ed78ee2bb4e86ce'
TEXTURE_WIDTH, TEXTURE_HEIGHT = 704, 64
MAX_VERTICES = 1024 * 3
SCALE = 50.0
ACT_IDLE = 0x0C400201


class MarioUnavailable(RuntimeError):
    pass


class Surface(ct.Structure):
    _fields_ = [('type', ct.c_int16), ('force', ct.c_int16), ('terrain', ct.c_uint16),
                ('vertices', (ct.c_int32 * 3) * 3)]


class Inputs(ct.Structure):
    _fields_ = [(name, ct.c_float) for name in ('camLookX', 'camLookZ', 'stickX', 'stickY')] + [
        (name, ct.c_uint8) for name in ('buttonA', 'buttonB', 'buttonZ')]


class State(ct.Structure):
    _fields_ = [('position', ct.c_float * 3), ('velocity', ct.c_float * 3),
                ('faceAngle', ct.c_float), ('forwardVelocity', ct.c_float),
                ('health', ct.c_int16), ('action', ct.c_uint32), ('animID', ct.c_int32),
                ('animFrame', ct.c_int16), ('flags', ct.c_uint32), ('particleFlags', ct.c_uint32),
                ('invincTimer', ct.c_int16)]


class Geometry(ct.Structure):
    _fields_ = [(name, ct.POINTER(ct.c_float)) for name in ('position', 'normal', 'color', 'uv')] + [
        ('numTrianglesUsed', ct.c_uint16)]

    def __init__(self):
        super().__init__()
        for name, width in (('position', 3), ('normal', 3), ('color', 3), ('uv', 2)):
            setattr(self, name, (ct.c_float * (MAX_VERTICES * width))())


def bind_library(path):
    lib = ct.CDLL(str(path))
    pointer = ct.POINTER
    signatures = {
        'sm64_global_init': (None, pointer(ct.c_uint8), pointer(ct.c_uint8)),
        'sm64_global_terminate': (None,),
        'sm64_static_surfaces_load': (None, pointer(Surface), ct.c_uint32),
        'sm64_mario_create': (ct.c_int32, ct.c_float, ct.c_float, ct.c_float),
        'sm64_mario_delete': (None, ct.c_int32),
        'sm64_mario_tick': (None, ct.c_int32, pointer(Inputs), pointer(State), pointer(Geometry)),
        'sm64_set_mario_action': (None, ct.c_int32, ct.c_uint32),
        'sm64_set_mario_position': (None, ct.c_int32, ct.c_float, ct.c_float, ct.c_float),
    }
    for name, (result, *args) in signatures.items():
        func = getattr(lib, name)
        func.restype = result
        func.argtypes = args
    return lib


def make_texture(pixels):
    image = PNMImage(TEXTURE_WIDTH, TEXTURE_HEIGHT, 4)
    for y in range(TEXTURE_HEIGHT):
        for x in range(TEXTURE_WIDTH):
            offset = 4 * (y * TEXTURE_WIDTH + x)
            image.setXelA(x, y, *(channel / 255 for channel in pixels[offset:offset + 4]))
    texture = Texture('MarioTex')
    texture.load(image)
    texture.setMinfilter(SamplerState.FTNearest)
    texture.setMagfilter(SamplerState.FTNearest)
    return texture


class MarioModel:
    """One native Mario instance, with a private floor for pose generation."""

    def __init__(self, directory):
        name = LIBRARY_NAMES.get(sys.platform)
        if name is None:
            raise MarioUnavailable('Mario mode is not supported on this platform.')
        rom_path = directory / 'sm64.z64'
        try:
            with rom_path.open('rb') as rom_file:
                rom = rom_file.read(ROM_SIZE + 1)
        except OSError as exc:
            raise MarioUnavailable('Place a Super Mario 64 US ROM at mario/sm64.z64.') from exc
        # Native code reads fixed offsets, so reject unsupported ROMs before calling it.
        if len(rom) != ROM_SIZE or hashlib.sha1(rom).hexdigest() != ROM_SHA1:
            raise MarioUnavailable('mario/sm64.z64 must be the original, unmodified US ROM (.z64).')
        try:
            self.lib = bind_library(directory / name)
        except (AttributeError, OSError) as exc:
            raise MarioUnavailable(f'Could not load mario/{name}. Use the libsm64 build in the setup guide.') from exc

        self.node = NodePath(GeomNode('Mario'))
        self.mario_id = -1
        self.inputs = Inputs(camLookX=1.0)
        self.state = State()
        self.geometry = Geometry()

        # Keep the ROM buffer alive until termination, including possible native references.
        self.rom = (ct.c_uint8 * ROM_SIZE).from_buffer_copy(rom)
        pixels = (ct.c_uint8 * (4 * TEXTURE_WIDTH * TEXTURE_HEIGHT))()
        self.lib.sm64_global_init(self.rom, pixels)
        try:
            shaders = Path(__file__).resolve().with_name('shaders')
            shader = Shader.load(Shader.SL_GLSL,
                                 vertex=Filename.fromOsSpecific(str(shaders / 'mario.vsh')),
                                 fragment=Filename.fromOsSpecific(str(shaders / 'mario.fsh')))
            if shader is None:
                raise MarioUnavailable('Could not load the Mario shader.')
            self.node.setShader(shader)
            self.node.setTexture(make_texture(pixels))

            floor = (Surface * 2)()
            corners = [(-1024, 0, -1024), (-1024, 0, 1024), (1024, 0, 1024), (1024, 0, -1024)]
            for surface, vertices in zip(floor, ((0, 1, 2), (0, 2, 3))):
                for vertex, index in zip(surface.vertices, vertices):
                    vertex[:] = corners[index]
            self.lib.sm64_static_surfaces_load(floor, len(floor))
            self.mario_id = self.lib.sm64_mario_create(0, 0, 0)
            if self.mario_id < 0:
                raise MarioUnavailable('libsm64 could not create Mario.')
            self.lib.sm64_set_mario_action(self.mario_id, ACT_IDLE)
            self.tick(False, False, False, False)
        except Exception:
            self.close()
            raise

    def tick(self, moving, jump, punch, crouch):
        self.inputs.stickY = float(moving)
        self.inputs.buttonA = jump
        self.inputs.buttonB = punch
        self.inputs.buttonZ = crouch
        # Keep pose simulation centered; the Toon controller applies world translation.
        self.lib.sm64_set_mario_position(self.mario_id, 0, self.state.position[1], 0)
        self.lib.sm64_mario_tick(self.mario_id, self.inputs, self.state, self.geometry)
        geo = self.geometry
        count = geo.numTrianglesUsed * 3
        if not 0 < count <= MAX_VERTICES:
            raise MarioUnavailable('libsm64 did not return a valid Mario mesh.')

        data = GeomVertexData('mario', GeomVertexFormat.getV3n3c4t2(), Geom.UHStream)
        data.setNumRows(count)
        pos, normal, color, uv = (GeomVertexWriter(data, column)
                                  for column in ('vertex', 'normal', 'color', 'texcoord'))
        ox, oy, oz = self.state.position
        for i in range(count):
            j = 3 * i
            x, y, z = geo.position[j:j + 3]
            pos.addData3((x - ox) / SCALE, (oz - z) / SCALE, (y - oy) / SCALE)
            x, y, z = geo.normal[j:j + 3]
            normal.addData3(x, -z, y)
            color.addData4(*geo.color[j:j + 3], 1)
            uv.addData2(geo.uv[2 * i], -geo.uv[2 * i + 1])

        triangles = GeomTriangles(Geom.UHStream)
        for i in range(0, count, 3):
            triangles.addVertices(i, i + 1, i + 2)
        mesh = Geom(data)
        mesh.addPrimitive(triangles)
        node = self.node.node()
        node.removeAllGeoms()
        node.addGeom(mesh)
        self.node.setH(180 - math.degrees(self.state.faceAngle))

    def close(self):
        if self.mario_id >= 0:
            self.lib.sm64_mario_delete(self.mario_id)
            self.mario_id = -1
        self.lib.sm64_global_terminate()
        self.node.removeNode()
