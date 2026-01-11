import ctypes
import os
import sys
from krita import Extension, Krita
from pathlib import Path
from PyQt5.QtCore import QTimer

if sys.platform in ["win32", "cygwin", "msys"]:
    platform = "windows"
elif sys.platform == "linux":
    platform = "linux"
elif sys.platform == "darwin":
    platform = "macos"
else:
    raise RuntimeError(f"Unsupported platform: {sys.platform}")


def _env_add_path(var: str, *paths: str | Path):
    prev = os.environ.get(var, "")
    if not paths:
        return prev
    paths = os.pathsep.join(str(p) for p in paths)
    os.environ[var] = f"{paths}{os.pathsep}{prev}" if prev else paths
    return prev


def _restore_env(var: str, value: str):
    if value:
        os.environ[var] = value


class VisionMLExtension(Extension):
    """Loader for Vision ML tools and filters.

    This is not actually a Python plugin, it just acts as a loader for the native libraries.
    This makes distribution and installation easier.
    """

    def __init__(self, parent):
        super().__init__(parent)
        self._loaded = False
        self._env_path = None
        self._ld_path = None

    def setup(self):
        """Schedule loading of the native VisionML library.
        
        Uses QTimer to defer loading until after Python returns control to Qt's event loop.
        This avoids GIL conflicts when the native code interacts with Python.
        """
        # DISABLED: The kritavisionml.dll has ABI compatibility issues with the current
        # Krita build (compiled with different toolchain - LLVM/MinGW vs MSVC).
        # The native library needs to be rebuilt with matching compiler settings.
        print("[VisionML] Plugin disabled due to ABI compatibility issues with current Krita build")
        return
        
        if self._loaded:
            return
        
        # Schedule the actual loading for the next event loop iteration
        QTimer.singleShot(0, self._do_load)

    def _do_load(self):
        """Actually load the native VisionML library."""
        if self._loaded:
            return
            
        ext = {"windows": ".dll", "linux": ".so", "macos": ".dylib"}[platform]
        lib_dir = Path(__file__).parent / "lib"
        lib_file = lib_dir / f"kritavisionml{ext}"

        executable_dir = Path(sys.executable).parent
        bin_paths = []
        if platform == "windows":
            bin_paths = [lib_dir, executable_dir]
        self._env_path = _env_add_path("PATH", *bin_paths)

        ld_paths = []
        if platform == "linux":
            ld_paths.append(lib_dir.resolve())
        if platform == "linux" and "APPDIR" in os.environ:  # for AppImage
            ld_paths.append(Path(os.environ["APPDIR"]) / "usr" / "lib")
        self._ld_path = _env_add_path("LD_LIBRARY_PATH", *ld_paths)

        try:
            # Load the library
            lib = ctypes.CDLL(str(lib_file.resolve()))
            
            # Get the function and set its properties
            load_func = lib.load_vision_ml_plugin
            load_func.argtypes = []
            load_func.restype = None
            
            # Call the function - now we're in Qt's event loop, not Python's call stack
            load_func()
            
            self._loaded = True
            print("[VisionML] Plugin loaded successfully")

        except OSError as e:
            deps = ""
            for dependency in lib_dir.glob(f"*{ext}"):
                try:
                    ctypes.CDLL(str(dependency.resolve()))
                except OSError:
                    deps += f"\nFailed to load dependency {dependency}"
            print(f"[VisionML] Failed to load library from {lib_file}: {e}{deps}")
        finally:
            _restore_env("PATH", self._env_path)
            _restore_env("LD_LIBRARY_PATH", self._ld_path)

    def shutdown(self):
        pass

    def createActions(self, window):
        pass


Krita.instance().addExtension(VisionMLExtension(Krita.instance()))
