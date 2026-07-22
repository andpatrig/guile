"""
guile._package — Turn a guile app into a shareable executable.

This is a thin, opinionated wrapper around PyInstaller. It exists so someone
who has never touched PyInstaller can go from `my_app.py` to a single file
they can hand to a colleague, without learning the tool's flag soup.

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
      (pip install pyinstaller). No separate/clean environment is needed —
      it bundles the interpreter and packages you already have.
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
    print("[guile] Installing PyInstaller into the current environment…")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "pyinstaller"],
        check=True,
    )


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
    onefile: bool = True,
    windowed: bool = True,
    icon: Optional[str] = None,
    add_data: Optional[Sequence[Tuple[str, str]]] = None,
    hidden_imports: Optional[Sequence[str]] = None,
    output_dir: str = "dist",
    clean: bool = True,
    install_missing: bool = False,
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
        onefile         True  → one self-contained file, easiest to share.
                        False → a folder (starts faster, many files).
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
    entry = _resolve_script(script)
    if not os.path.isfile(entry):
        raise FileNotFoundError(f"App script not found: {entry}")
    app_name = name or os.path.splitext(os.path.basename(entry))[0]

    cmd: List[str] = [
        sys.executable, "-m", "PyInstaller",
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

    # pywebview ships platform-specific backends that static analysis can miss.
    # --collect-all pulls in its submodules, data and binaries so the built
    # app can actually open a window on the target machine.
    cmd += ["--collect-all", "webview"]

    for mod in (hidden_imports or ()):
        cmd += ["--hidden-import", mod]

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

    print(f"[guile] Packaging {os.path.basename(entry)} → {app_name}")
    print("[guile] " + " ".join(cmd))
    subprocess.run(cmd, check=True)

    out = _expected_output(os.path.abspath(output_dir), app_name,
                           onefile, windowed)
    if os.path.exists(out):
        print(f"\n[guile] Done. Your executable is ready to share:\n        {out}")
    else:
        print(f"\n[guile] Build finished. Look in: {os.path.abspath(output_dir)}")
    return cmd


# Friendly alias.
pack = package
