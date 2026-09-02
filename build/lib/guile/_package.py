"""
guile._package — Turn a guile app into a shareable executable.

This is a thin, opinionated wrapper around PyInstaller. It exists so someone
who has never touched PyInstaller can go from `my_app.py` to a shareable app
they can hand to a colleague, without learning the tool's flag soup.

By default it builds a folder (package_mode="onedir"): the executable plus its
libraries, which draws fewer antivirus/SmartScreen false positives and starts
faster — zip it up or wrap it in an installer to share. Pass
package_mode="onefile" for a single self-contained executable instead.

It is a BUILD step, not a runtime feature: call it from a small build script
or a `if __name__ == "__main__"` guard, NOT from inside your ui() function.

    # build.py
    import guile as gui
    gui.package("my_app.py", name="MyApp")

PyInstaller only bundles what your entry script actually imports, so the
executable already contains just the modules and data your app reaches —
nothing else from your environment. That is PyInstaller's default import
analysis; guile doesn't add anything to broaden it.

Requirements:
    - PyInstaller installed in the SAME environment as your app
      (pip install pyinstaller). It bundles that environment's interpreter
      and packages.
    - Build from a CLEAN virtual environment holding only what the app
      needs. PyInstaller follows optional imports, so a build from a full
      Anaconda install can reach several GB (torch, tensorflow, dask...) or
      fail outright; package() prints a note when it detects that.

          python -m venv build-env
          build-env\\Scripts\\pip install guile pyinstaller <your packages>
          build-env\\Scripts\\python build.py
    - On Windows the resulting app relies on the WebView2 runtime, which is
      preinstalled on current Windows 10/11. Very old machines may need it:
      https://developer.microsoft.com/microsoft-edge/webview2/

Deliberately out of scope: installers (Inno Setup, DMGs, .deb). package()
stops at the raw executable; wrapping it in an installer is a separate step
you can take later.
"""

from __future__ import annotations

import os
import subprocess
import sys
from typing import List, Optional, Sequence, Tuple


def _resolve_script(script: Optional[str]) -> str:
    """Return the entry script path, defaulting to the running __main__."""
    if script:
        return os.path.abspath(script)
    main = sys.modules.get("__main__")
    path = getattr(main, "__file__", None) or (sys.argv[0] if sys.argv else None)
    if not path:
        raise ValueError(
            "Could not determine the app script automatically. "
            "Pass it explicitly, e.g. gui.package('my_app.py')."
        )
    return os.path.abspath(path)


def _have_pyinstaller() -> bool:
    try:
        import PyInstaller  # noqa: F401
        return True
    except ImportError:
        return False


def _pip_install_pyinstaller() -> None:
    print("[guile] Installing PyInstaller into the current environment...")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "pyinstaller"],
        check=True,
    )


# ── pywebview backends ──────────────────────────────────────────────────────
# pywebview picks a backend at runtime, but its selector (guilib.py) imports
# every backend inside try-functions, and PyInstaller follows those static
# imports. On a machine with PyQt/PySide installed that pulls the Qt backend
# and all of Qt into the bundle, or aborts with "multiple Qt bindings". So we
# name the native chain for this platform and exclude the rest.
#
# Windows: winforms hosts the window and imports edgechromium (WebView2),
#          mshtml (legacy fallback) and win32 helpers. The WebView2 DLLs in
#          webview/lib are collected by PyInstaller's contrib hook; the
#          collect-data/binaries flags below cover older hook versions.
_NATIVE_BACKENDS = {
    "win32":  ["winforms", "edgechromium", "mshtml", "win32"],
    "darwin": ["cocoa"],
}
_LINUX_BACKENDS = ["gtk", "qt"]          # whichever the target machine has
_ALL_BACKENDS   = ["android", "cef", "cocoa", "edgechromium", "gtk", "mshtml",
                   "qt", "win32", "winforms"]
_QT_BINDINGS    = ["PyQt5", "PyQt6", "PySide2", "PySide6", "qtpy"]

# Modules a desktop app never uses that PyInstaller nevertheless follows into
# the bundle: matplotlib.pyplot optionally imports IPython, which leads to
# jedi -> parso -> docutils -> sphinx -> babel. Besides adding tens of MB, that
# chain nests deeply enough to hit Python's recursion limit during analysis
# ("A RecursionError occurred") in typical Anaconda environments.
_DEFAULT_EXCLUDES = ["IPython", "jedi", "parso", "docutils", "sphinx", "babel"]

# PyInstaller is run through this bootstrap rather than `-m PyInstaller` so
# the recursion limit is raised first - PyInstaller's own documented remedy
# for deep import chains. Arguments after the code are PyInstaller's.
_BOOTSTRAP = ("import sys; sys.setrecursionlimit(5000); "
              "from PyInstaller.__main__ import run; run(sys.argv[1:])")


def _webview_args(native_only: bool) -> List[str]:
    """PyInstaller flags that make the built app able to open its window."""
    if not native_only:
        return ["--collect-all", "webview"]
    linux = sys.platform not in _NATIVE_BACKENDS
    keep  = _LINUX_BACKENDS if linux else _NATIVE_BACKENDS[sys.platform]
    args  = ["--collect-data", "webview", "--collect-binaries", "webview"]
    for b in keep:
        args += ["--hidden-import", f"webview.platforms.{b}"]
    for b in _ALL_BACKENDS:
        if b not in keep:
            args += ["--exclude-module", f"webview.platforms.{b}"]
    if not linux:                         # native backends never need Qt
        for q in _QT_BINDINGS:
            args += ["--exclude-module", q]
    return args


# Packages whose presence marks a "kitchen sink" environment. None is needed
# by guile; if several are importable, the build is probably running from a
# full Anaconda install and PyInstaller will follow optional imports into them.
_HEAVY = ["torch", "tensorflow", "transformers", "dask", "scipy", "cv2",
          "numba", "sklearn"]


def _environment_hint() -> Optional[str]:
    """A note to print before building from a large environment, or None."""
    import importlib.util
    found = []
    for m in _HEAVY:
        try:
            if importlib.util.find_spec(m):
                found.append(m)
        except Exception:          # a broken package must not break a build
            pass
    conda_base = (os.path.isdir(os.path.join(sys.prefix, "conda-meta"))
                  and os.environ.get("CONDA_DEFAULT_ENV", "base") == "base")
    if len(found) < 2 and not conda_base:
        return None
    where = "the Anaconda base environment" if conda_base else "a large environment"
    pip = "build-env\\Scripts\\pip" if os.name == "nt" else "build-env/bin/pip"
    py  = "build-env\\Scripts\\python" if os.name == "nt" else "build-env/bin/python"
    return (
        f"[guile] note: building from {where}"
        + (f" ({', '.join(found)} installed)" if found else "") + ".\n"
        "        PyInstaller follows optional imports, so the bundle can reach\n"
        "        several GB or fail to build. For a small, reliable build use a\n"
        "        clean virtual environment holding only what the app needs:\n"
        "            python -m venv build-env\n"
        f"            {pip} install guile pyinstaller <your app's packages>\n"
        f"            {py} build.py"
    )


def _subprocess_env() -> dict:
    """
    Environment for the PyInstaller subprocess.

    A venv created from an Anaconda/Miniconda Python keeps using conda's
    interpreter, whose extension modules (_ctypes, _lzma, _bz2, pyexpat...)
    depend on DLLs in <conda>\\Library\\bin. The venv never puts that folder
    on PATH, so PyInstaller logs "Library not found: could not resolve
    ffi-8.dll" and the built app dies at launch with "DLL load failed while
    importing _ctypes". Putting the folder on PATH for the build fixes it.
    """
    env = os.environ.copy()
    if os.name != "nt":
        return env
    extra = []
    for prefix in dict.fromkeys([sys.prefix, sys.base_prefix]):   # ordered, unique
        lib_bin = os.path.join(prefix, "Library", "bin")
        if os.path.isdir(os.path.join(prefix, "conda-meta")) and os.path.isdir(lib_bin):
            extra.append(lib_bin)
    if extra:
        env["PATH"] = os.pathsep.join(extra + [env.get("PATH", "")])
    return env


def _expected_output(dist_dir: str, name: str, onefile: bool,
                     windowed: bool) -> str:
    """Best-effort path of the artifact PyInstaller will produce."""
    if sys.platform == "darwin" and windowed:
        return os.path.join(dist_dir, f"{name}.app")
    exe = f"{name}.exe" if os.name == "nt" else name
    if onefile:
        return os.path.join(dist_dir, exe)
    return os.path.join(dist_dir, name, exe)   # onedir: dist/<name>/<exe>


def package(
    script: Optional[str] = None,
    *,
    name: Optional[str] = None,
    package_mode: str = "onedir",
    windowed: bool = True,
    icon: Optional[str] = None,
    add_data: Optional[Sequence[Tuple[str, str]]] = None,
    hidden_imports: Optional[Sequence[str]] = None,
    output_dir: str = "dist",
    clean: bool = True,
    install_missing: bool = False,
    native_only: bool = True,
    exclude_modules: Optional[Sequence[str]] = None,
    run: bool = True,
) -> List[str]:
    """
    Build a standalone executable from a guile app using PyInstaller.

    Returns the PyInstaller command as a list of strings. When run=True
    (default) it also runs that command and prints where the executable
    landed; set run=False to just get the command back without building.

    Arguments:
        script          Path to your app's entry .py file. Defaults to the
                        script that is currently running (__main__).
        name            Name of the executable. Defaults to the script's
                        filename without extension.
        package_mode    "onedir" (default) → a folder holding the executable
                        and its libraries. Fewer antivirus/SmartScreen false
                        positives and a faster startup; share it as a zip or
                        wrap it in an installer. This is PyInstaller's own
                        default and the recommended way to distribute.
                        "onefile" → a single self-contained executable, tidy
                        to hand over but more likely to trip antivirus
                        heuristics (it unpacks itself to a temp dir at launch)
                        and slower to start.
        windowed        True  → no console window (normal for a GUI app).
                        False → keep a console so you can see tracebacks —
                                use this while debugging a build.
        icon            Path to a .ico (Windows) or .icns (macOS) icon.
        add_data        Extra runtime files to bundle, as (src, dest) pairs:
                        add_data=[("presets.yaml", "."), ("img/logo.png", "img")]
                        PyInstaller finds imported *code* on its own; use this
                        only for data files your app opens at runtime.
        hidden_imports  Modules imported dynamically (importlib, plugins) that
                        PyInstaller's static analysis can't see.
        native_only     True (default): bundle only this platform's native
                        pywebview backend (WebView2 on Windows, Cocoa on
                        macOS, GTK/Qt on Linux) and exclude the others.
                        pywebview's backend selector imports every backend,
                        so without this a machine that has PyQt or PySide
                        installed drags all of Qt into the build — hundreds
                        of MB — or fails with "multiple Qt bindings". On
                        Windows and macOS the Qt bindings themselves are
                        excluded too. Set False to fall back to PyInstaller's
                        --collect-all webview (everything, no excludes).
        exclude_modules Extra modules to leave out (--exclude-module), e.g.
                        ["tkinter", "scipy"] to slim a build. IPython, jedi,
                        parso, docutils, sphinx and babel are always excluded:
                        matplotlib drags them in, a desktop app never uses
                        them, and their import depth crashes PyInstaller's
                        analysis with a RecursionError on many machines.
        output_dir      Where the finished executable goes (default "dist").
        clean           Pass --clean --noconfirm for a fresh, unattended build.
        install_missing If PyInstaller isn't installed, pip install it instead
                        of raising. Default False (fail with instructions).
        run             Execute the build. False returns the command only.

    Example:
        import guile as gui
        gui.package("weather.py", name="Weather",
                    add_data=[("stations.csv", ".")],
                    icon="weather.ico")
    """
    if package_mode not in ("onedir", "onefile"):
        raise ValueError(
            f"package_mode must be 'onedir' or 'onefile', got {package_mode!r}."
        )
    onefile = package_mode == "onefile"

    entry = _resolve_script(script)
    if not os.path.isfile(entry):
        raise FileNotFoundError(f"App script not found: {entry}")
    app_name = name or os.path.splitext(os.path.basename(entry))[0]

    cmd: List[str] = [
        sys.executable, "-c", _BOOTSTRAP,
        "--name", app_name,
        "--distpath", os.path.abspath(output_dir),
    ]
    if onefile:
        cmd.append("--onefile")
    if windowed:
        cmd.append("--windowed")
    if clean:
        cmd += ["--clean", "--noconfirm"]
    if icon:
        cmd += ["--icon", os.path.abspath(icon)]

    cmd += _webview_args(native_only)

    for mod in (hidden_imports or ()):
        cmd += ["--hidden-import", mod]
    for mod in list(_DEFAULT_EXCLUDES) + list(exclude_modules or ()):
        cmd += ["--exclude-module", mod]

    for src, dest in (add_data or ()):
        # PyInstaller wants "src<sep>dest"; the separator is OS-specific.
        cmd += ["--add-data", f"{os.path.abspath(src)}{os.pathsep}{dest}"]

    cmd.append(entry)

    if not run:
        return cmd

    if not _have_pyinstaller():
        if install_missing:
            _pip_install_pyinstaller()
        else:
            raise SystemExit(
                "[guile] PyInstaller is not installed in this environment.\n"
                "        Install it, then run package() again:\n\n"
                f"            {os.path.basename(sys.executable)} -m pip install pyinstaller\n\n"
                "        Or call gui.package(..., install_missing=True) to let\n"
                "        guile install it for you."
            )

    # ASCII only: with stdout redirected to a file, Windows encodes prints
    # as cp1252 and a non-ASCII character raises UnicodeEncodeError here.
    hint = _environment_hint()
    if hint:
        print(hint)
    print(f"[guile] Packaging {os.path.basename(entry)} -> {app_name}")
    print("[guile] pyinstaller " + " ".join(cmd[3:]))   # skip the bootstrap
    subprocess.run(cmd, check=True, env=_subprocess_env())

    out = _expected_output(os.path.abspath(output_dir), app_name,
                           onefile, windowed)
    if os.path.exists(out):
        print(f"\n[guile] Done. Your executable is ready to share:\n        {out}")
    else:
        print(f"\n[guile] Build finished. Look in: {os.path.abspath(output_dir)}")
    return cmd


# Friendly alias.
pack = package
