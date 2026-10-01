"""
Visualizador 3D com galeria — texturas, pastas ao vivo e resize
================================================================

Uso:
    python SpriteGenerator.py                 -> abre vazio
    python SpriteGenerator.py modelo.glb      -> abre com o arquivo
    python SpriteGenerator.py ./pasta         -> abre e observa a pasta

Controles:
    Arrastar (área 3D)  : orbitar
    Scroll              : zoom (na área 3D) / scroll da lista (na galeria)
    Setas ← → ↑ ↓       : orbitar
    R                   : resetar câmera
    T                   : alternar textura
    ESC                 : sair

Recursos:
    - Carregamento incremental: a UI NÃO trava ao abrir pastas grandes
    - Watch de pasta: adiciona/remove modelos automaticamente a cada 5s
    - Janela redimensionável (arraste as bordas)
    - Preview (thumbnail) de cada modelo com textura na galeria
    - Sem dependência de scipy (normais calculadas com numpy)
"""

# ====================================================================
#  AUTO-INSTALAÇÃO
# ====================================================================
import importlib, subprocess, sys

REQUIRED = [
    ("numpy",   "numpy"),
    ("PIL",     "pillow"),
    ("pygame",  "pygame"),
    ("OpenGL",  "PyOpenGL"),
    ("trimesh", "trimesh"),
]

def _has(mod):
    try:
        importlib.import_module(mod); return True
    except ImportError:
        return False

def _ensure_dependencies():
    missing = [pip for mod, pip in REQUIRED if not _has(mod)]
    if not missing:
        return
    print("[i] Instalando:", ", ".join(missing))
    subprocess.check_call([sys.executable, "-m", "pip", "install",
                           "--upgrade", "pip"])
    subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])
    print("[+] Reiniciando...\n")
    subprocess.check_call([sys.executable] + sys.argv)
    sys.exit(0)

_ensure_dependencies()

# ====================================================================
#  IMPORTS
# ====================================================================
import os, time
import numpy as np
import trimesh
import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
from PIL import Image

import tkinter as tk
from tkinter import filedialog


# ====================================================================
#  CONFIG
# ====================================================================
DEFAULT_WIN_W = 1400
DEFAULT_WIN_H = 900
MIN_WIN_W     = 720
MIN_WIN_H     = 500

TOP_BAR_H     = 64
GALLERY_W     = 250

THUMB_SIZE    = 96
THUMB_CELL_W  = 112
THUMB_CELL_H  = 132
GALLERY_COLS  = 2
GALLERY_PAD   = 8

FOLDER_SCAN_MS = 5000     # re-escaneia a pasta a cada 5s
LOAD_PER_FRAME = 1        # modelos processados por frame

SUPPORTED_EXTS = (".glb", ".gltf", ".obj", ".stl",
                  ".ply", ".fbx", ".dae", ".off")

# Paleta
C_BG        = (22, 24, 32)
C_PANEL     = (30, 33, 42)
C_PANEL_D   = (26, 28, 36)
C_BORDER    = (55, 60, 75)
C_TEXT      = (228, 230, 238)
C_TEXT_DIM  = (145, 150, 170)
C_ACCENT    = (95, 160, 230)
C_PRIMARY   = (52, 140, 88)
C_PRIMARY_H = (74, 175, 112)
C_SEL       = (60, 120, 180)

GL_FLAGS = DOUBLEBUF | OPENGL | RESIZABLE


# ====================================================================
#  GL
# ====================================================================
def setup_gl_state():
    glEnable(GL_DEPTH_TEST)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    try:
        glEnable(GL_MULTISAMPLE)
    except Exception:
        pass

    glEnable(GL_LIGHTING)
    glEnable(GL_LIGHT0)
    glEnable(GL_LIGHT1)
    glEnable(GL_COLOR_MATERIAL)
    glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
    glEnable(GL_NORMALIZE)

    glLightfv(GL_LIGHT0, GL_AMBIENT,  [0.30, 0.32, 0.38, 1.0])
    glLightfv(GL_LIGHT0, GL_DIFFUSE,  [0.85, 0.85, 0.85, 1.0])
    glLightfv(GL_LIGHT0, GL_SPECULAR, [0.25, 0.25, 0.25, 1.0])
    glLightfv(GL_LIGHT1, GL_AMBIENT,  [0.0, 0.0, 0.0, 1.0])
    glLightfv(GL_LIGHT1, GL_DIFFUSE,  [0.25, 0.25, 0.30, 1.0])
    glLightfv(GL_LIGHT1, GL_SPECULAR, [0.0, 0.0, 0.0, 1.0])

    glMaterialfv(GL_FRONT_AND_BACK, GL_SPECULAR,  [0.12, 0.12, 0.12, 1.0])
    glMaterialf (GL_FRONT_AND_BACK, GL_SHININESS, 28.0)


def setup_camera(azimuth, elevation, ortho_size, aspect, distance=100.0):
    glMatrixMode(GL_PROJECTION); glLoadIdentity()
    glOrtho(-ortho_size * aspect, ortho_size * aspect,
            -ortho_size, ortho_size, 0.1, 4000.0)

    glMatrixMode(GL_MODELVIEW); glLoadIdentity()

    az = np.radians(azimuth); el = np.radians(elevation)
    ex = distance * np.cos(el) * np.sin(az)
    ey = distance * np.sin(el)
    ez = distance * np.cos(el) * np.cos(az)

    if abs(elevation) >= 89.9:
        upx, upy, upz = -np.sin(az), 0.0, -np.cos(az)
    else:
        upx, upy, upz = 0.0, 1.0, 0.0

    gluLookAt(ex, ey, ez, 0, 0, 0, upx, upy, upz)
    glLightfv(GL_LIGHT0, GL_POSITION, [ 0.6,  1.0,  0.7, 0.0])
    glLightfv(GL_LIGHT1, GL_POSITION, [-0.6, -0.2, -0.5, 0.0])


def draw_grid(extent=12, step=1.0, major=5):
    glDisable(GL_LIGHTING); glDisable(GL_COLOR_MATERIAL)
    glLineWidth(1.0)
    glBegin(GL_LINES)
    n = int(extent / step)
    for i in range(-n, n + 1):
        if i % major == 0:
            glColor3f(0.45, 0.48, 0.55)
        else:
            glColor3f(0.22, 0.24, 0.30)
        x = i * step
        glVertex3f(x, 0.0, -extent); glVertex3f(x, 0.0, extent)
        glVertex3f(-extent, 0.0, x); glVertex3f(extent, 0.0, x)
    glEnd()

    glLineWidth(2.0)
    glBegin(GL_LINES)
    glColor3f(0.80, 0.35, 0.35)
    glVertex3f(-extent, 0.002, 0); glVertex3f(extent, 0.002, 0)
    glColor3f(0.35, 0.50, 0.90)
    glVertex3f(0, 0.002, -extent); glVertex3f(0, 0.002, extent)
    glEnd()

    glEnable(GL_LIGHTING); glEnable(GL_COLOR_MATERIAL)


def create_fbo(size):
    fbo = glGenFramebuffers(1); glBindFramebuffer(GL_FRAMEBUFFER, fbo)
    tex = glGenTextures(1); glBindTexture(GL_TEXTURE_2D, tex)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, size, size, 0,
                 GL_RGBA, GL_UNSIGNED_BYTE, None)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0,
                           GL_TEXTURE_2D, tex, 0)
    dep = glGenRenderbuffers(1); glBindRenderbuffer(GL_RENDERBUFFER, dep)
    glRenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH_COMPONENT24, size, size)
    glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT,
                              GL_RENDERBUFFER, dep)
    st = glCheckFramebufferStatus(GL_FRAMEBUFFER)
    glBindFramebuffer(GL_FRAMEBUFFER, 0)
    if st != GL_FRAMEBUFFER_COMPLETE:
        raise RuntimeError(f"FBO incompleto ({st})")
    return fbo, tex, dep


def delete_fbo(fbo, tex, dep):
    glDeleteFramebuffers(1, [fbo])
    glDeleteTextures([tex])
    glDeleteRenderbuffers(1, [dep])


# ====================================================================
#  MODELO
# ====================================================================
def _to_rgba_image(tex):
    if tex is None:
        return None
    if isinstance(tex, np.ndarray):
        try:
            tex = Image.fromarray(tex)
        except Exception:
            return None
    if isinstance(tex, Image.Image):
        return tex.convert('RGBA') if tex.mode != 'RGBA' else tex
    if hasattr(tex, 'convert'):
        return tex.convert('RGBA')
    return None


def _extract_material(visual):
    color = [0.8, 0.8, 0.85, 1.0]
    image = None
    if not hasattr(visual, 'material'):
        return color, image
    mat = visual.material

    bcf = None
    if hasattr(mat, 'baseColorFactor') and mat.baseColorFactor is not None:
        bcf = list(mat.baseColorFactor)
    elif hasattr(mat, 'diffuse') and mat.diffuse is not None:
        bcf = list(mat.diffuse)

    if bcf:
        if len(bcf) == 3:
            bcf.append(1.0)
        if max(bcf[:4]) > 1.0:
            bcf = [c / 255.0 for c in bcf[:4]]
        color = bcf[:4]

    raw = None
    if hasattr(mat, 'baseColorTexture') and mat.baseColorTexture is not None:
        raw = mat.baseColorTexture
    elif hasattr(mat, 'image') and mat.image is not None:
        raw = mat.image
    image = _to_rgba_image(raw)

    return color, image


class Model:
    def __init__(self, path):
        self.path = path
        self.name = os.path.splitext(os.path.basename(path))[0]
        self.parts = []
        self.max_extent = 1.0
        self.raw_size = (1.0, 1.0, 1.0)
        self._load()

    def _load(self):
        loaded = trimesh.load(self.path)

        parts_src = []
        if isinstance(loaded, trimesh.Scene):
            scene = loaded
            try:
                nodes = list(scene.graph.nodes_geometry)
            except Exception:
                nodes = []
            for node in nodes:
                transform, geom_name = scene.graph[node]
                geom = scene.geometry.get(geom_name)
                if isinstance(geom, trimesh.Trimesh):
                    parts_src.append((geom, transform))
            if not parts_src:
                for g in scene.geometry.values():
                    if isinstance(g, trimesh.Trimesh):
                        parts_src.append((g, np.eye(4)))
        elif isinstance(loaded, trimesh.Trimesh):
            parts_src.append((loaded, np.eye(4)))

        if not parts_src:
            raise ValueError("Sem geometria válida no arquivo")

        all_verts = []
        for geom, transform in parts_src:
            geom = geom.copy()
            if geom.faces.shape[1] != 3:
                geom = geom.triangulate()

            verts = np.asarray(geom.vertices, dtype=np.float64)
            faces = np.asarray(geom.faces, dtype=np.uint32)

            # --- Vertex normals calculadas manualmente (sem scipy) ---
            # Somar cross products por face dá normais ponderadas por área
            # (a magnitude do cross é proporcional à área do triângulo).
            tris = verts[faces]                    # (F, 3, 3)
            e1 = tris[:, 1] - tris[:, 0]
            e2 = tris[:, 2] - tris[:, 0]
            face_normals = np.cross(e1, e2)        # (F, 3)
            vn = np.zeros_like(verts, dtype=np.float64)
            np.add.at(vn, faces[:, 0], face_normals)
            np.add.at(vn, faces[:, 1], face_normals)
            np.add.at(vn, faces[:, 2], face_normals)
            ln = np.linalg.norm(vn, axis=1, keepdims=True)
            ln[ln == 0] = 1.0
            vnormals = vn / ln                     # (V, 3) normalizado

            # Aplica transform da cena
            T = np.asarray(transform, dtype=np.float64)
            homog = np.hstack([verts, np.ones((len(verts), 1))])
            verts_w = (T @ homog.T).T[:, :3]

            rot = T[:3, :3]
            nrm_w = vnormals @ rot.T
            norms = np.linalg.norm(nrm_w, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            nrm_w = nrm_w / norms

            uvs = None
            vis = geom.visual
            if hasattr(vis, 'uv') and vis.uv is not None:
                uvs = np.asarray(vis.uv, dtype=np.float32)

            color, image = _extract_material(vis)
            all_verts.append(verts_w)

            self.parts.append({
                'vertices': np.ascontiguousarray(verts_w, dtype=np.float32),
                'faces':    np.ascontiguousarray(faces, dtype=np.uint32),
                'normals':  np.ascontiguousarray(nrm_w, dtype=np.float32),
                'uvs':      None if uvs is None else np.ascontiguousarray(uvs, dtype=np.float32),
                'color':    color,
                'image':    image,
                'texture_id': None,
            })

        big = np.concatenate(all_verts, axis=0)
        bmin = big.min(axis=0); bmax = big.max(axis=0)
        center = (bmin + bmax) * 0.5
        size = bmax - bmin
        self.raw_size = tuple(float(s) for s in size)
        self.max_extent = float(max(size)) if max(size) > 0 else 1.0

        for p in self.parts:
            p['vertices'] = np.ascontiguousarray(
                p['vertices'] - center.astype(np.float32), dtype=np.float32)

    def upload_textures(self):
        for p in self.parts:
            if p['texture_id'] is not None:
                continue
            img = p['image']
            if img is None:
                continue
            try:
                flipped = img.transpose(Image.FLIP_TOP_BOTTOM)
                w, h = flipped.size
                data = flipped.tobytes()
                tex = glGenTextures(1)
                glBindTexture(GL_TEXTURE_2D, tex)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
                glPixelStorei(GL_UNPACK_ALIGNMENT, 1)
                glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, w, h, 0,
                             GL_RGBA, GL_UNSIGNED_BYTE, data)
                p['texture_id'] = tex
            except Exception as e:
                print(f"[!] Textura falhou: {e}")

    def draw(self, use_textures=True):
        glEnableClientState(GL_VERTEX_ARRAY)
        glEnableClientState(GL_NORMAL_ARRAY)

        for p in self.parts:
            use_tex = use_textures and p['texture_id'] is not None and p['uvs'] is not None
            if use_tex:
                glEnable(GL_TEXTURE_2D)
                glBindTexture(GL_TEXTURE_2D, p['texture_id'])
                glEnableClientState(GL_TEXTURE_COORD_ARRAY)
                glTexCoordPointer(2, GL_FLOAT, 0, p['uvs'])
            else:
                glDisable(GL_TEXTURE_2D)
                glDisableClientState(GL_TEXTURE_COORD_ARRAY)

            glColor4f(*p['color'])
            glVertexPointer(3, GL_FLOAT, 0, p['vertices'])
            glNormalPointer(GL_FLOAT, 0, p['normals'])
            glDrawElements(GL_TRIANGLES, p['faces'].size,
                           GL_UNSIGNED_INT, p['faces'])

        glDisableClientState(GL_VERTEX_ARRAY)
        glDisableClientState(GL_NORMAL_ARRAY)
        glDisableClientState(GL_TEXTURE_COORD_ARRAY)
        glDisable(GL_TEXTURE_2D)

    def free(self):
        for p in self.parts:
            if p['texture_id']:
                try:
                    glDeleteTextures([p['texture_id']])
                except Exception:
                    pass
                p['texture_id'] = None


# ====================================================================
#  PREVIEW RENDERER (FBO)
# ====================================================================
class PreviewRenderer:
    def __init__(self, size):
        self.size = size
        self.fbo, self.tex, self.dep = create_fbo(size)

    def render(self, model):
        glBindFramebuffer(GL_FRAMEBUFFER, self.fbo)
        glViewport(0, 0, self.size, self.size)
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        glClearColor(0, 0, 0, 0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        ortho = max(0.001, model.max_extent * 0.68)
        setup_camera(35.0, 22.0, ortho_size=ortho, aspect=1.0)

        model.draw(use_textures=True)
        glFinish()

        glPixelStorei(GL_PACK_ALIGNMENT, 1)
        data = glReadPixels(0, 0, self.size, self.size,
                            GL_RGBA, GL_UNSIGNED_BYTE)
        img = Image.frombytes("RGBA", (self.size, self.size), data)
        img = img.transpose(Image.FLIP_TOP_BOTTOM)

        glBindFramebuffer(GL_FRAMEBUFFER, 0)
        return img

    def free(self):
        delete_fbo(self.fbo, self.tex, self.dep)


# ====================================================================
#  OVERLAY 2D
# ====================================================================
class Overlay:
    def __init__(self, size):
        self.size = size
        self.surface = pygame.Surface(size, pygame.SRCALPHA)
        self.tex = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.tex)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)

    def resize(self, size):
        if size == self.size:
            return
        self.size = size
        self.surface = pygame.Surface(size, pygame.SRCALPHA)

    def commit(self):
        data = pygame.image.tobytes(self.surface, "RGBA", False)
        glPixelStorei(GL_UNPACK_ALIGNMENT, 1)
        glBindTexture(GL_TEXTURE_2D, self.tex)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA,
                     self.size[0], self.size[1], 0,
                     GL_RGBA, GL_UNSIGNED_BYTE, data)

    def draw(self):
        glMatrixMode(GL_PROJECTION); glLoadIdentity()
        glOrtho(0, self.size[0], self.size[1], 0, -1, 1)
        glMatrixMode(GL_MODELVIEW); glLoadIdentity()

        glDisable(GL_DEPTH_TEST); glDisable(GL_LIGHTING)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, self.tex)
        glColor4f(1, 1, 1, 1)

        w, h = self.size
        glBegin(GL_QUADS)
        glTexCoord2f(0, 0); glVertex2f(0, 0)
        glTexCoord2f(1, 0); glVertex2f(w, 0)
        glTexCoord2f(1, 1); glVertex2f(w, h)
        glTexCoord2f(0, 1); glVertex2f(0, h)
        glEnd()

        glDisable(GL_TEXTURE_2D); glDisable(GL_BLEND)
        glEnable(GL_DEPTH_TEST); glEnable(GL_LIGHTING)


# ====================================================================
#  DIALOGS
# ====================================================================
def dialog_file():
    root = tk.Tk(); root.withdraw(); root.attributes("-topmost", True)
    p = filedialog.askopenfilename(
        title="Selecione um modelo 3D",
        filetypes=[
            ("Modelos 3D", "*.glb *.gltf *.obj *.stl *.ply *.fbx *.dae *.off"),
            ("GLB / glTF", "*.glb *.gltf"),
            ("Todos os arquivos", "*.*"),
        ])
    root.destroy()
    return p or None


def dialog_folder():
    root = tk.Tk(); root.withdraw(); root.attributes("-topmost", True)
    p = filedialog.askdirectory(title="Selecione uma pasta com modelos")
    root.destroy()
    return p or None


def list_models_in_folder(folder):
    folder = os.path.abspath(folder)
    out = []
    try:
        for f in sorted(os.listdir(folder)):
            ext = os.path.splitext(f)[1].lower()
            if ext in SUPPORTED_EXTS:
                full = os.path.join(folder, f)
                if os.path.isfile(full):
                    out.append(full)
    except Exception as e:
        print(f"[!] Erro lendo pasta: {e}")
    return out


# ====================================================================
#  WIDGETS
# ====================================================================
def draw_button(surface, font, rect, label, mouse_pos,
                base=C_PANEL, hover=(46, 50, 64),
                text=C_TEXT, enabled=True, primary=False, active=False):
    if primary or active:
        base, hover = C_PRIMARY, C_PRIMARY_H
    hovered = enabled and rect.collidepoint(mouse_pos)
    col = hover if hovered else base
    if not enabled:
        col = (36, 40, 50)
    pygame.draw.rect(surface, col, rect, border_radius=8)
    border = C_ACCENT if (primary or active) else C_BORDER
    pygame.draw.rect(surface, border, rect, 1, border_radius=8)
    txt = font.render(label, True, text if enabled else (115, 118, 128))
    surface.blit(txt, txt.get_rect(center=rect.center))


# ====================================================================
#  VIEWER
# ====================================================================
class Viewer:
    def __init__(self, win_w, win_h, preview_renderer):
        self.win_w = win_w
        self.win_h = win_h
        self.preview_renderer = preview_renderer

        self.entries = []
        self.current = 0
        self.gallery_scroll = 0.0

        self.watched_folder = None
        self.last_scan_time = 0.0

        self.azimuth = 35.0
        self.elevation = 22.0
        self.ortho = 3.0
        self.use_textures = True
        self.show_grid = True

        self.status = "Carregue um arquivo ou pasta para começar"
        self.status_color = C_TEXT_DIM

        self.dragging = False
        self.last_mouse = (0, 0)
        self.ui_rects = {}

    # ---------------- HELPERS ----------------
    def set_size(self, w, h):
        self.win_w = max(MIN_WIN_W, w)
        self.win_h = max(MIN_WIN_H, h)

    @property
    def current_model(self):
        if 0 <= self.current < len(self.entries):
            return self.entries[self.current].get('model')
        return None

    def _loaded_count(self):
        return sum(1 for e in self.entries if e['model'] is not None)

    def _failed_count(self):
        return sum(1 for e in self.entries if e['error'] is not None)

    def _pending_count(self):
        return sum(1 for e in self.entries
                   if e['model'] is None and e['error'] is None)

    # ---------------- LOAD ----------------
    def _unload_all(self):
        for e in self.entries:
            if e['model']:
                e['model'].free()
        self.entries = []
        self.current = 0
        self.gallery_scroll = 0.0

    def load_single(self, path):
        self.watched_folder = None
        self._unload_all()
        self.entries = [{'path': os.path.abspath(path),
                         'model': None, 'surf': None, 'error': None}]
        self.status = f"Carregando {os.path.basename(path)}..."
        self.status_color = C_TEXT_DIM

    def load_folder(self, folder, watch=True):
        folder = os.path.abspath(folder)
        self.watched_folder = folder if watch else None
        self._unload_all()

        paths = list_models_in_folder(folder)
        if not paths:
            self.status = "Nenhum modelo válido na pasta"
            self.status_color = (230, 140, 140)
            return

        self.entries = [{'path': p, 'model': None, 'surf': None, 'error': None}
                        for p in paths]
        self.status = f"Carregando {len(paths)} modelo(s)..."
        self.status_color = C_TEXT_DIM
        print(f"[i] Pasta: {folder}  ({len(paths)} modelo(s))")

    def _process_pending(self, max_count=LOAD_PER_FRAME):
        count = 0
        for e in self.entries:
            if count >= max_count:
                break
            if e['model'] is not None or e['error'] is not None:
                continue

            try:
                m = Model(e['path'])
                m.upload_textures()
                img = self.preview_renderer.render(m)
                thumb = img.resize((THUMB_SIZE, THUMB_SIZE), Image.LANCZOS)
                surf = pygame.image.frombytes(thumb.tobytes(),
                                               thumb.size, "RGBA").convert_alpha()
                e['model'] = m
                e['surf'] = surf

                if self.current_model is None and self.current == 0:
                    self._fit_camera_to(m)

            except Exception as ex:
                print(f"[!] {os.path.basename(e['path'])}: {ex}")
                e['error'] = str(ex)

            count += 1

        if count > 0:
            total = len(self.entries)
            loaded = self._loaded_count()
            failed = self._failed_count()
            if loaded + failed >= total:
                if failed > 0:
                    self.status = f"{loaded} OK, {failed} falha(s)"
                    self.status_color = (230, 180, 120)
                else:
                    self.status = f"{loaded} modelo(s) carregado(s)"
                    self.status_color = (150, 210, 170)
                if self.current_model:
                    self._fit_camera_to(self.current_model)
            else:
                self.status = f"Carregando... {loaded + failed}/{total}"
                self.status_color = C_TEXT_DIM

    def _fit_camera_to(self, model):
        self.ortho = max(0.3, model.max_extent * 1.6)

    def select(self, idx):
        if 0 <= idx < len(self.entries):
            self.current = idx
            if self.entries[idx].get('model'):
                self._fit_camera_to(self.entries[idx]['model'])
            self.status = self.entries[idx]['path'].split(os.sep)[-1]
            self.status_color = C_TEXT_DIM

    # ---------------- FOLDER WATCH ----------------
    def _rescan_folder(self):
        if not self.watched_folder:
            return
        if self._pending_count() > 0:
            return

        try:
            new_paths = list_models_in_folder(self.watched_folder)
        except Exception as e:
            print(f"[!] Rescan falhou: {e}")
            return

        current_paths = [e['path'] for e in self.entries]
        if new_paths == current_paths:
            return

        added = [p for p in new_paths if p not in current_paths]
        removed = [p for p in current_paths if p not in new_paths]

        if added or removed:
            print(f"[i] Pasta mudou: +{len(added)} -{len(removed)}")

        old_sel_path = None
        if 0 <= self.current < len(self.entries):
            old_sel_path = self.entries[self.current]['path']

        old_by_path = {e['path']: e for e in self.entries}

        for p in removed:
            old = old_by_path.get(p)
            if old and old.get('model'):
                old['model'].free()

        new_entries = []
        for p in new_paths:
            if p in old_by_path and old_by_path[p].get('model') is not None:
                new_entries.append(old_by_path[p])
            elif p in old_by_path and old_by_path[p].get('error') is not None:
                new_entries.append({'path': p, 'model': None, 'surf': None, 'error': None})
            else:
                new_entries.append({'path': p, 'model': None, 'surf': None, 'error': None})

        self.entries = new_entries

        if old_sel_path:
            for i, e in enumerate(self.entries):
                if e['path'] == old_sel_path:
                    self.current = i
                    break
            else:
                self.current = min(self.current, len(self.entries) - 1)
        else:
            self.current = 0

        if self.current_model:
            self._fit_camera_to(self.current_model)

    def maybe_scan_folder(self):
        if not self.watched_folder:
            return
        now = time.monotonic() * 1000.0
        if now - self.last_scan_time < FOLDER_SCAN_MS:
            return
        self.last_scan_time = now
        self._rescan_folder()

    # ---------------- LAYOUT ----------------
    def gallery_cell_rect(self, idx):
        row = idx // GALLERY_COLS
        col = idx % GALLERY_COLS
        x = GALLERY_PAD + col * THUMB_CELL_W
        y = GALLERY_PAD + row * THUMB_CELL_H - self.gallery_scroll
        return pygame.Rect(x, TOP_BAR_H + y, THUMB_CELL_W - 4, THUMB_CELL_H - 4)

    def viewport_3d(self):
        return pygame.Rect(GALLERY_W, TOP_BAR_H,
                           self.win_w - GALLERY_W, self.win_h - TOP_BAR_H)

    # ---------------- UI ----------------
    def draw_ui(self, surface, fonts, mouse_pos):
        self.ui_rects.clear()
        W, H = self.win_w, self.win_h

        pygame.draw.rect(surface, C_PANEL, (0, 0, W, TOP_BAR_H))
        pygame.draw.line(surface, C_BORDER, (0, TOP_BAR_H), (W, TOP_BAR_H), 1)

        btn_file   = pygame.Rect(16, 14, 175, 36)
        btn_folder = pygame.Rect(200, 14, 175, 36)
        self.ui_rects['load_file'] = btn_file
        self.ui_rects['load_folder'] = btn_folder

        draw_button(surface, fonts['normal'], btn_file,
                    "Carregar Arquivo...", mouse_pos)
        draw_button(surface, fonts['normal'], btn_folder,
                    "Carregar Pasta...", mouse_pos)

        title = self.current_model.name if self.current_model else "Visualizador 3D"
        t = fonts['h1'].render(title, True, C_TEXT)
        surface.blit(t, (W // 2 - t.get_width() // 2, 12))

        if self.entries:
            extra = " (observando pasta)" if self.watched_folder else ""
            sub = fonts['small'].render(
                f"{self.current + 1} de {len(self.entries)}{extra}",
                True, C_TEXT_DIM)
            surface.blit(sub, (W // 2 - sub.get_width() // 2, 40))

        btn_tex  = pygame.Rect(W - 300, 14, 130, 36)
        btn_grid = pygame.Rect(W - 162, 14, 146, 36)
        self.ui_rects['toggle_tex'] = btn_tex
        self.ui_rects['toggle_grid'] = btn_grid
        draw_button(surface, fonts['small'], btn_tex,
                    ("Textura: ON" if self.use_textures else "Textura: OFF"),
                    mouse_pos, active=self.use_textures)
        draw_button(surface, fonts['small'], btn_grid,
                    ("Grid: ON" if self.show_grid else "Grid: OFF"),
                    mouse_pos, active=self.show_grid)

        pygame.draw.rect(surface, C_PANEL_D, (0, TOP_BAR_H, GALLERY_W,
                                              H - TOP_BAR_H))
        pygame.draw.line(surface, C_BORDER,
                         (GALLERY_W, TOP_BAR_H), (GALLERY_W, H), 1)

        clip = pygame.Rect(0, TOP_BAR_H, GALLERY_W, H - TOP_BAR_H)
        old_clip = surface.get_clip()
        surface.set_clip(clip)

        if not self.entries:
            msg = fonts['small'].render(
                "Use os botões acima para carregar",
                True, C_TEXT_DIM)
            surface.blit(msg, (GALLERY_W // 2 - msg.get_width() // 2,
                               TOP_BAR_H + 30))
        else:
            for i, e in enumerate(self.entries):
                cell = self.gallery_cell_rect(i)
                if cell.bottom < TOP_BAR_H or cell.top > H:
                    continue

                selected = (i == self.current)
                hovered = cell.collidepoint(mouse_pos)
                has_model = e['model'] is not None
                has_error = e['error'] is not None

                bg = C_SEL if selected else ((42, 46, 60) if hovered else C_PANEL)
                pygame.draw.rect(surface, bg, cell, border_radius=8)
                border = C_ACCENT if selected else C_BORDER
                pygame.draw.rect(surface, border, cell, 2 if selected else 1,
                                 border_radius=8)

                tx = cell.x + (cell.w - THUMB_SIZE) // 2
                ty = cell.y + 6
                if e['surf'] is not None:
                    surface.blit(e['surf'], (tx, ty))
                else:
                    ph = pygame.Rect(tx, ty, THUMB_SIZE, THUMB_SIZE)
                    pygame.draw.rect(surface, (22, 24, 32), ph, border_radius=4)
                    if has_error:
                        txt = fonts['small'].render("erro", True, (230, 140, 140))
                    else:
                        txt = fonts['small'].render("...", True, C_TEXT_DIM)
                    surface.blit(txt, txt.get_rect(center=ph.center))

                name = e['model'].name if has_model else os.path.splitext(
                    os.path.basename(e['path']))[0]
                if len(name) > 13:
                    name = name[:11] + "…"
                nt = fonts['small'].render(
                    name, True, C_TEXT if selected else C_TEXT_DIM)
                surface.blit(nt, (cell.x + (cell.w - nt.get_width()) // 2,
                                  cell.y + cell.h - 20))

        surface.set_clip(old_clip)

        pygame.draw.rect(surface, C_PANEL, (0, H - 28, W, 28))
        pygame.draw.line(surface, C_BORDER, (0, H - 28), (W, H - 28), 1)
        st = fonts['small'].render(self.status, True, self.status_color)
        surface.blit(st, (12, H - 22))

        hint = fonts['small'].render(
            "Arrastar=orbitar  Scroll=zoom  R=reset  T=textura  ESC=sair",
            True, C_TEXT_DIM)
        surface.blit(hint, (W - hint.get_width() - 12, H - 22))

    def draw_3d(self):
        vp = self.viewport_3d()
        glViewport(vp.x, self.win_h - vp.y - vp.h, vp.w, vp.h)
        aspect = max(0.001, vp.w / vp.h)

        setup_camera(self.azimuth, self.elevation,
                     ortho_size=self.ortho, aspect=aspect)

        glClearColor(0.11, 0.12, 0.16, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        if self.show_grid:
            draw_grid(extent=12, step=1.0, major=5)

        m = self.current_model
        if m is not None:
            m.draw(use_textures=self.use_textures)

    # ---------------- EVENTS ----------------
    def handle_event(self, event, mouse_pos):
        W, H = self.win_w, self.win_h

        if event.type == KEYDOWN:
            if event.key == K_ESCAPE:
                return "quit"
            elif event.key == K_r:
                self.azimuth, self.elevation = 35.0, 22.0
                if self.current_model:
                    self._fit_camera_to(self.current_model)
            elif event.key == K_t:
                self.use_textures = not self.use_textures

        elif event.type == MOUSEBUTTONDOWN and event.button == 1:
            if self.ui_rects.get('load_file') and self.ui_rects['load_file'].collidepoint(event.pos):
                p = dialog_file()
                if p:
                    self.load_single(p)
            elif self.ui_rects.get('load_folder') and self.ui_rects['load_folder'].collidepoint(event.pos):
                f = dialog_folder()
                if f:
                    self.load_folder(f, watch=True)
            elif self.ui_rects.get('toggle_tex') and self.ui_rects['toggle_tex'].collidepoint(event.pos):
                self.use_textures = not self.use_textures
            elif self.ui_rects.get('toggle_grid') and self.ui_rects['toggle_grid'].collidepoint(event.pos):
                self.show_grid = not self.show_grid
            elif event.pos[0] < GALLERY_W and event.pos[1] > TOP_BAR_H:
                for i in range(len(self.entries)):
                    if self.gallery_cell_rect(i).collidepoint(event.pos):
                        self.select(i)
                        break
            elif event.pos[0] >= GALLERY_W and event.pos[1] > TOP_BAR_H:
                self.dragging = True
                self.last_mouse = event.pos

        elif event.type == MOUSEBUTTONUP and event.button == 1:
            self.dragging = False

        elif event.type == MOUSEMOTION and self.dragging:
            dx = event.pos[0] - self.last_mouse[0]
            dy = event.pos[1] - self.last_mouse[1]
            self.azimuth += dx * 0.4
            self.elevation = max(-89.0, min(89.0, self.elevation + dy * 0.4))
            self.last_mouse = event.pos

        elif event.type == MOUSEWHEEL:
            if mouse_pos[0] < GALLERY_W and mouse_pos[1] > TOP_BAR_H:
                total_rows = (len(self.entries) + GALLERY_COLS - 1) // GALLERY_COLS
                content_h = total_rows * THUMB_CELL_H + GALLERY_PAD * 2
                avail_h = H - TOP_BAR_H
                max_scroll = max(0, content_h - avail_h)
                self.gallery_scroll = max(0.0, min(
                    max_scroll, self.gallery_scroll - event.y * 40))
            else:
                factor = 0.9 if event.y > 0 else 1.1
                self.ortho = max(0.05, min(200.0, self.ortho * factor))

        return None

    def update_continuous(self):
        keys = pygame.key.get_pressed()
        if keys[K_LEFT]:  self.azimuth -= 1.2
        if keys[K_RIGHT]: self.azimuth += 1.2
        if keys[K_UP]:    self.elevation = min(89.0, self.elevation + 0.8)
        if keys[K_DOWN]:  self.elevation = max(-89.0, self.elevation - 0.8)


# ====================================================================
#  MAIN
# ====================================================================
def main():
    pygame.init()
    pygame.display.set_mode((DEFAULT_WIN_W, DEFAULT_WIN_H), GL_FLAGS)
    pygame.display.set_caption("Visualizador 3D")

    setup_gl_state()

    fonts = {
        'h1':     pygame.font.SysFont("Segoe UI", 18, bold=True),
        'normal': pygame.font.SysFont("Segoe UI", 14),
        'small':  pygame.font.SysFont("Segoe UI", 12),
    }

    overlay = Overlay((DEFAULT_WIN_W, DEFAULT_WIN_H))
    preview_renderer = PreviewRenderer(THUMB_SIZE * 2)
    viewer = Viewer(DEFAULT_WIN_W, DEFAULT_WIN_H, preview_renderer)

    if len(sys.argv) >= 2:
        arg = sys.argv[1]
        if os.path.isdir(arg):
            viewer.load_folder(arg, watch=True)
        elif os.path.isfile(arg):
            viewer.load_single(arg)

    clock = pygame.time.Clock()
    running = True

    while running:
        mouse_pos = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == QUIT:
                running = False
                break

            elif event.type == VIDEORESIZE:
                new_w = max(MIN_WIN_W, event.w)
                new_h = max(MIN_WIN_H, event.h)
                viewer.set_size(new_w, new_h)
                try:
                    pygame.display.set_mode((new_w, new_h), GL_FLAGS)
                except Exception as e:
                    print(f"[!] set_mode no resize falhou: {e}")
                overlay.resize((new_w, new_h))
                setup_gl_state()

            else:
                res = viewer.handle_event(event, mouse_pos)
                if res == "quit":
                    running = False
                    break

        surf = pygame.display.get_surface()
        if surf is not None:
            aw, ah = surf.get_size()
            if aw != viewer.win_w or ah != viewer.win_h:
                viewer.set_size(aw, ah)
                overlay.resize((viewer.win_w, viewer.win_h))

        viewer.update_continuous()
        viewer._process_pending(LOAD_PER_FRAME)
        viewer.maybe_scan_folder()

        viewer.draw_3d()

        overlay.surface.fill((0, 0, 0, 0))
        viewer.draw_ui(overlay.surface, fonts, mouse_pos)
        overlay.commit()

        glViewport(0, 0, viewer.win_w, viewer.win_h)
        overlay.draw()

        pygame.display.flip()
        clock.tick(60)

    for e in viewer.entries:
        if e.get('model'):
            e['model'].free()
    preview_renderer.free()
    pygame.quit()


if __name__ == "__main__":
    main()