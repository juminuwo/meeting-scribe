"""Preload CUDA 13 shared libs bundled by the torch wheel.

PyTorch 2.11+cu130 ships NVRTC under site-packages/nvidia/cu13/lib but does not
add that directory to the dynamic-loader search path. Lazy JIT kernel compiles
then fail with "libnvrtc-builtins.so.13.0 not found". Preloading the libs with
RTLD_GLOBAL puts their symbols in the global namespace so subsequent dlopens
resolve siblings by soname.
"""

import ctypes
from pathlib import Path

try:
    import nvidia  # type: ignore[import-not-found]
except ImportError:
    nvidia = None

if nvidia is not None:
    for parent in nvidia.__path__:
        lib_dir = Path(parent) / "cu13" / "lib"
        if not lib_dir.is_dir():
            continue
        for so in lib_dir.iterdir():
            if ".so" not in so.name:
                continue
            try:
                ctypes.CDLL(str(so), mode=ctypes.RTLD_GLOBAL)
            except OSError:
                pass
