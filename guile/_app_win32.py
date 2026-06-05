"""
guile._app_win32 — Windows-only backend. No pywebview required.

Creates a native Win32 window and embeds WebView2 via COM (ctypes only).
Zero pip dependencies beyond the Python stdlib.

Requirements
------------
WebView2 Runtime must be available:
  1. System install — ships with Windows 10 21H2+ and auto-updates with Edge.
  2. Fixed Version  — set WEBVIEW2_BROWSER_EXECUTABLE_FOLDER env var to a
     folder containing the Fixed Version runtime (downloaded from Microsoft).
     This makes the app 100% self-contained; no OS browser needed.

WebView2Loader.dll must be findable alongside this file, next to the .exe,
or in PATH. It ships in Microsoft's WebView2 SDK (NuGet → x64 folder, ~800 KB).

Event flow for a button click:
    1. User clicks → JS window._guile.trigger(cid, value)
    2. JS window.pywebview.api.handle(cid, value)   [polyfill below]
    3. Polyfill: window.chrome.webview.postMessage(JSON)
    4. WebView2 fires WebMessageReceived → _on_message() on UI thread
    5. Daemon thread: dispatch(cid) → State.set() → _render()
    6. _render() queues JS → PostMessage(_WM_EVAL_JS)
    7. Message loop wakes up → ExecuteScript() on UI thread
    8. JS patcher updates changed DOM nodes
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import json
import os
import queue as _queue_module
import sys
import tempfile
import threading
from pathlib import Path
from typing import Callable, Optional

# ── Internal guile imports ─────────────────────────────────────────────────
from .state import register as _reg_listener, unregister as _unreg_listener
from .ui import (
    Column,
    _reset_render, _commit_callbacks,
    dispatch as _dispatch,
    dispatch_silent as _dispatch_silent,
    _clear_state_store,
    _set_window as _ui_set_window,
)
from ._template import get_html


# ══════════════════════════════════════════════════════════════════════════
# pywebview compatibility stub
# ══════════════════════════════════════════════════════════════════════════
# _FilePicker in ui.py does `import webview` to read webview.FileDialog.
# We inject a minimal stub so it works when pywebview is not installed.

if 'webview' not in sys.modules:
    import types as _types
    _wv_stub = _types.ModuleType('webview')

    class _FileDialogConst:
        OPEN = 0
        SAVE = 1

    _wv_stub.FileDialog = _FileDialogConst
    sys.modules['webview'] = _wv_stub


# ══════════════════════════════════════════════════════════════════════════
# Win32 constants
# ══════════════════════════════════════════════════════════════════════════

WM_DESTROY  = 0x0002
WM_SIZE     = 0x0005
WM_CLOSE    = 0x0010
WM_PAINT    = 0x000F
WM_APP      = 0x8000
_WM_EVAL_JS = WM_APP + 1   # custom message: drain the JS queue on UI thread

CS_HREDRAW = 0x0002
CS_VREDRAW = 0x0001

WS_OVERLAPPEDWINDOW  = 0x00CF0000
WS_OVERLAPPED        = 0x00000000
WS_CAPTION           = 0x00C00000
WS_SYSMENU           = 0x00080000
WS_THICKFRAME        = 0x00040000
WS_MINIMIZEBOX       = 0x00020000
WS_MAXIMIZEBOX       = 0x00010000
WS_VISIBLE           = 0x10000000

SW_SHOW     = 5
IDC_ARROW   = 32512

# OPENFILENAME flags
OFN_EXPLORER        = 0x00080000
OFN_NOCHANGEDIR     = 0x00000008
OFN_FILEMUSTEXIST   = 0x00001000
OFN_PATHMUSTEXIST   = 0x00000800
OFN_OVERWRITEPROMPT = 0x00000002

HRESULT  = ctypes.c_long
c_void_p = ctypes.c_void_p
S_OK     = 0

WINFUNCTYPE = ctypes.WINFUNCTYPE
PTR_SZ      = ctypes.sizeof(c_void_p)   # 8 on 64-bit, 4 on 32-bit


# ══════════════════════════════════════════════════════════════════════════
# Win32 structures
# ══════════════════════════════════════════════════════════════════════════

class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ('cbSize',        ctypes.c_uint),
        ('style',         ctypes.c_uint),
        ('lpfnWndProc',   c_void_p),
        ('cbClsExtra',    ctypes.c_int),
        ('cbWndExtra',    ctypes.c_int),
        ('hInstance',     ctypes.wintypes.HINSTANCE),
        ('hIcon',         ctypes.wintypes.HANDLE),
        ('hCursor',       ctypes.wintypes.HANDLE),
        ('hbrBackground', ctypes.wintypes.HANDLE),
        ('lpszMenuName',  ctypes.wintypes.LPCWSTR),
        ('lpszClassName', ctypes.wintypes.LPCWSTR),
        ('hIconSm',       ctypes.wintypes.HANDLE),
    ]


class MSG(ctypes.Structure):
    _fields_ = [
        ('hwnd',    ctypes.wintypes.HWND),
        ('message', ctypes.c_uint),
        ('wParam',  ctypes.wintypes.WPARAM),
        ('lParam',  ctypes.wintypes.LPARAM),
        ('time',    ctypes.c_uint),
        ('pt',      ctypes.wintypes.POINT),
    ]


class RECT(ctypes.Structure):
    _fields_ = [
        ('left',   ctypes.c_long),
        ('top',    ctypes.c_long),
        ('right',  ctypes.c_long),
        ('bottom', ctypes.c_long),
    ]


class OPENFILENAMEW(ctypes.Structure):
    _fields_ = [
        ('lStructSize',       ctypes.c_uint),
        ('hwndOwner',         ctypes.wintypes.HWND),
        ('hInstance',         ctypes.wintypes.HINSTANCE),
        ('lpstrFilter',       ctypes.wintypes.LPCWSTR),
        ('lpstrCustomFilter', ctypes.wintypes.LPWSTR),
        ('nMaxCustFilter',    ctypes.c_uint),
        ('nFilterIndex',      ctypes.c_uint),
        ('lpstrFile',         ctypes.wintypes.LPWSTR),
        ('nMaxFile',          ctypes.c_uint),
        ('lpstrFileTitle',    ctypes.wintypes.LPWSTR),
        ('nMaxFileTitle',     ctypes.c_uint),
        ('lpstrInitialDir',   ctypes.wintypes.LPCWSTR),
        ('lpstrTitle',        ctypes.wintypes.LPCWSTR),
        ('Flags',             ctypes.c_uint),
        ('nFileOffset',       ctypes.c_ushort),
        ('nFileExtension',    ctypes.c_ushort),
        ('lpstrDefExt',       ctypes.wintypes.LPCWSTR),
        ('lCustData',         ctypes.c_long),
        ('lpfnHook',          c_void_p),
        ('lpTemplateName',    ctypes.wintypes.LPCWSTR),
        ('pvReserved',        c_void_p),
        ('dwReserved',        ctypes.c_uint),
        ('FlagsEx',           ctypes.c_uint),
    ]


class EventRegistrationToken(ctypes.Structure):
    """COM event token returned by add_* methods. Needed to unregister."""
    _fields_ = [('value', ctypes.c_int64)]


# ══════════════════════════════════════════════════════════════════════════
# COM vtable helpers
# ══════════════════════════════════════════════════════════════════════════

def _vtbl(ptr: int, idx: int, restype, *argtypes):
    """
    Build a callable for the COM vtable method at index idx on object at ptr.

    COM object layout (both 32- and 64-bit):
        object → [vtable_pointer] → [fn0, fn1, fn2, ...]
    """
    vtable_ptr = ctypes.c_void_p.from_address(ptr).value
    fn_ptr     = ctypes.c_void_p.from_address(vtable_ptr + idx * PTR_SZ).value
    functype   = WINFUNCTYPE(restype, c_void_p, *argtypes)
    return functype(fn_ptr)


def _read_bstr(bstr: int) -> str:
    """Read a COM-allocated BSTR and free it. Returns Python str."""
    if not bstr:
        return ""
    s = ctypes.wstring_at(bstr)
    ctypes.windll.oleaut32.SysFreeString(bstr)
    return s


# ══════════════════════════════════════════════════════════════════════════
# COM callback objects
#
# WebView2 uses COM-style async callbacks. When you call
# CreateCoreWebView2EnvironmentWithOptions, it calls back via a COM
# interface you provide. We implement these interfaces in Python by
# building a vtable (array of function pointers) and pointing a
# COM-compatible structure at it.
#
# Vtable layout for all handlers:
#   [0] QueryInterface
#   [1] AddRef
#   [2] Release
#   [3] Invoke(...)
# ══════════════════════════════════════════════════════════════════════════

class _ComCallback:
    """
    Base for Python COM callback objects.
    Subclasses call _build(fns) with an ordered list of WINFUNCTYPE callables.
    After calling _build, self.ptr is the integer address to pass to COM.
    """

    def _build(self, fns: list):
        # Keep function objects alive — GC would break the vtable otherwise
        self._keep = fns
        # Build vtable: array of function pointers
        vtbl = (c_void_p * len(fns))(*[ctypes.cast(f, c_void_p) for f in fns])
        self._vtbl      = vtbl
        self._vtbl_ptr  = ctypes.pointer(vtbl)
        # The COM object is a struct { void** lpVtbl; }.
        # We model it as a c_void_p holding the address of the vtable pointer.
        vtbl_ptr_addr   = ctypes.cast(self._vtbl_ptr, c_void_p).value
        self._com_obj   = c_void_p(vtbl_ptr_addr)
        # ptr is the address of _com_obj, which is what we pass to COM methods
        self.ptr        = ctypes.addressof(self._com_obj)

    # Default IUnknown — single-use callbacks don't need real ref counting
    @staticmethod
    def _qi(this, riid, ppv): return 0x80004002  # E_NOINTERFACE
    @staticmethod
    def _ar(this):            return 1
    @staticmethod
    def _rl(this):            return 1


class _EnvHandler(_ComCallback):
    """
    ICoreWebView2CreateCoreWebView2EnvironmentCompletedHandler
    Fires when CreateCoreWebView2EnvironmentWithOptions completes.
    """
    def __init__(self, callback: Callable):
        self._cb = callback
        QI = WINFUNCTYPE(HRESULT, c_void_p, c_void_p, c_void_p)
        AR = WINFUNCTYPE(ctypes.c_uint32, c_void_p)
        RL = WINFUNCTYPE(ctypes.c_uint32, c_void_p)
        IV = WINFUNCTYPE(HRESULT, c_void_p, HRESULT, c_void_p)
        self._build([QI(self._qi), AR(self._ar), RL(self._rl),
                     IV(self._invoke)])

    def _invoke(self, this, hr, environment):
        if hr == S_OK and environment:
            self._cb(environment)
        return S_OK


class _CtrlHandler(_ComCallback):
    """
    ICoreWebView2CreateCoreWebView2ControllerCompletedHandler
    Fires when CreateCoreWebView2Controller completes.
    """
    def __init__(self, callback: Callable):
        self._cb = callback
        QI = WINFUNCTYPE(HRESULT, c_void_p, c_void_p, c_void_p)
        AR = WINFUNCTYPE(ctypes.c_uint32, c_void_p)
        RL = WINFUNCTYPE(ctypes.c_uint32, c_void_p)
        IV = WINFUNCTYPE(HRESULT, c_void_p, HRESULT, c_void_p)
        self._build([QI(self._qi), AR(self._ar), RL(self._rl),
                     IV(self._invoke)])

    def _invoke(self, this, hr, controller):
        if hr == S_OK and controller:
            self._cb(controller)
        return S_OK


class _NavHandler(_ComCallback):
    """
    ICoreWebView2NavigationCompletedEventHandler
    Fires when NavigateToString completes — we use this as the
    'page ready' signal to trigger the first render.
    Only fires once (we remove the handler after the first call).
    """
    def __init__(self, callback: Callable):
        self._cb     = callback
        self._fired  = False
        QI = WINFUNCTYPE(HRESULT, c_void_p, c_void_p, c_void_p)
        AR = WINFUNCTYPE(ctypes.c_uint32, c_void_p)
        RL = WINFUNCTYPE(ctypes.c_uint32, c_void_p)
        IV = WINFUNCTYPE(HRESULT, c_void_p, c_void_p, c_void_p)
        self._build([QI(self._qi), AR(self._ar), RL(self._rl),
                     IV(self._invoke)])

    def _invoke(self, this, sender, args):
        if not self._fired:
            self._fired = True
            self._cb()
        return S_OK


class _MsgHandler(_ComCallback):
    """
    ICoreWebView2WebMessageReceivedEventHandler
    Fires whenever JS calls window.chrome.webview.postMessage().
    The polyfill routes all window.pywebview.api.* calls through here.
    """
    def __init__(self, callback: Callable):
        self._cb = callback
        QI = WINFUNCTYPE(HRESULT, c_void_p, c_void_p, c_void_p)
        AR = WINFUNCTYPE(ctypes.c_uint32, c_void_p)
        RL = WINFUNCTYPE(ctypes.c_uint32, c_void_p)
        IV = WINFUNCTYPE(HRESULT, c_void_p, c_void_p, c_void_p)
        self._build([QI(self._qi), AR(self._ar), RL(self._rl),
                     IV(self._invoke)])

    def _invoke(self, this, sender, args):
        # ICoreWebView2WebMessageReceivedEventArgs.get_WebMessageAsJson = index 4
        # Returns a BSTR (COM-allocated wide string)
        bstr_out = c_void_p(0)
        hr = _vtbl(args, 4, HRESULT,
                   ctypes.POINTER(c_void_p))(args, ctypes.byref(bstr_out))
        if hr == S_OK and bstr_out.value:
            msg_json = _read_bstr(bstr_out.value)
            try:
                self._cb(msg_json)
            except Exception:
                import traceback; traceback.print_exc()
        return S_OK


# ══════════════════════════════════════════════════════════════════════════
# _Win32Window — proxy object stored as _App._current._window
#
# This lets gui.notify() call app._window.evaluate_js(js) and lets
# _FilePicker call app._window.create_file_dialog(...) — exactly the
# same interface as the pywebview window object.
# ══════════════════════════════════════════════════════════════════════════

class _Win32Window:
    def __init__(self, app: '_App'):
        self._app = app

    def evaluate_js(self, js: str):
        """Thread-safe. Queues JS for execution on the UI thread."""
        self._app._js_queue.put(js)
        if self._app._hwnd:
            ctypes.windll.user32.PostMessageW(
                self._app._hwnd, _WM_EVAL_JS, 0, 0
            )

    def create_file_dialog(self, dialog_type=0, allow_multiple=False,
                           file_types=()):
        """
        Open a Win32 file dialog. Blocks until the user closes it.

        dialog_type: 0 = open (webview.FileDialog.OPEN),
                     1 = save (webview.FileDialog.SAVE)
        file_types : tuple of "Description (*.ext)" strings
        Returns    : list with one path string, or None
        """
        save = (dialog_type == 1)

        # Build the null-terminated filter string
        # Format: "Description\0*.ext\0Description\0*.ext\0\0"
        filter_parts = []
        for ft in file_types:
            # pywebview format: "CSV Files (*.csv)" → description + pattern
            ft = ft.strip()
            if '(' in ft and ')' in ft:
                desc    = ft[:ft.index('(')].strip()
                pattern = ft[ft.index('(') + 1:ft.index(')')].strip()
            else:
                desc    = ft
                pattern = '*.*'
            filter_parts += [desc, pattern]
        if filter_parts:
            filter_parts.append('')  # double-null terminator
            filter_str = '\0'.join(filter_parts)
        else:
            filter_str = 'All Files (*.*)\0*.*\0'

        buf = ctypes.create_unicode_buffer(32768)
        ofn = OPENFILENAMEW()
        ofn.lStructSize  = ctypes.sizeof(OPENFILENAMEW)
        ofn.hwndOwner    = self._app._hwnd or 0
        ofn.lpstrFilter  = filter_str
        ofn.nFilterIndex = 1
        ofn.lpstrFile    = ctypes.cast(buf, ctypes.wintypes.LPWSTR)
        ofn.nMaxFile     = len(buf)
        ofn.Flags        = OFN_EXPLORER | OFN_NOCHANGEDIR

        if save:
            ofn.Flags |= OFN_OVERWRITEPROMPT
            ok = ctypes.windll.comdlg32.GetSaveFileNameW(ctypes.byref(ofn))
        else:
            ofn.Flags |= OFN_FILEMUSTEXIST | OFN_PATHMUSTEXIST
            ok = ctypes.windll.comdlg32.GetOpenFileNameW(ctypes.byref(ofn))

        if ok:
            path = buf.value
            return [path] if path else None
        return None


# ══════════════════════════════════════════════════════════════════════════
# WebView2 loader
# ══════════════════════════════════════════════════════════════════════════

def _load_webview2():
    """
    Load WebView2Loader.dll and return the
    CreateCoreWebView2EnvironmentWithOptions function.

    Search order:
        1. Directory of this file (guile package folder)
        2. Directory of the running executable (PyInstaller bundle)
        3. System PATH
    """
    candidates = [
        Path(__file__).parent / 'WebView2Loader.dll',
        Path(sys.executable).parent / 'WebView2Loader.dll',
    ]
    dll = None
    for p in candidates:
        if p.exists():
            dll = ctypes.WinDLL(str(p))
            break
    if dll is None:
        try:
            dll = ctypes.WinDLL('WebView2Loader.dll')
        except OSError:
            raise RuntimeError(
                "[guile] WebView2Loader.dll not found.\n"
                "Place it next to the guile package or the executable.\n"
                "Download the WebView2 SDK from:\n"
                "  https://developer.microsoft.com/microsoft-edge/webview2/"
            )

    fn = dll.CreateCoreWebView2EnvironmentWithOptions
    fn.argtypes = [
        ctypes.wintypes.LPCWSTR,  # browserExecutableFolder (or NULL)
        ctypes.wintypes.LPCWSTR,  # userDataFolder
        c_void_p,                 # environmentOptions (NULL = defaults)
        c_void_p,                 # handler
    ]
    fn.restype = HRESULT
    return fn


# ══════════════════════════════════════════════════════════════════════════
# _App
# ══════════════════════════════════════════════════════════════════════════

# JS polyfill injected before page scripts via AddScriptToExecuteOnDocumentCreated.
# Translates window.pywebview.api.* calls into window.chrome.webview.postMessage()
# so _template.py works unchanged.
_POLYFILL = """
(function () {
    'use strict';

    function post(method, cid, value) {
        try {
            window.chrome.webview.postMessage(
                JSON.stringify({ method: method, cid: cid, value: value })
            );
        } catch (e) {}
    }

    window.pywebview = {
        api: {
            handle: function (cid, value) {
                post('handle', cid, value === undefined ? null : value);
            },
            silent_update: function (cid, value) {
                post('silent_update', cid, value === undefined ? null : value);
            },
            ready: function () {
                post('ready', null, null);
            }
        }
    };

    // Fire pywebviewready so _template.py's listener picks it up
    window.dispatchEvent(new Event('pywebviewready'));
})();
"""


class _App:
    """
    Windows-native guile app backend.

    Replaces guile._app (_App backed by pywebview) with a pure ctypes
    implementation using Win32 for the window and WebView2 COM for HTML
    rendering. The public interface is identical to the pywebview backend.
    """

    _current: Optional['_App'] = None

    def __init__(self, title: str, *, width: int = 800, height: int = 600,
                 resizable: bool = False, debug: bool = False):
        self.title      = title
        self.width      = width
        self.height     = height
        self.resizable  = resizable
        self.debug      = debug

        self._build         = None           # ui() function
        self._hwnd          = None           # Win32 window handle
        self._webview       = None           # ICoreWebView2 ptr (int)
        self._controller    = None           # ICoreWebView2Controller ptr
        self._window        = None           # _Win32Window proxy
        self._ready         = False          # True after first nav completes
        self._rendering     = False
        self._needs_render  = False
        self._js_queue      = _queue_module.Queue()
        self._use_leaflet   = False          # set True by gui.leaflet()

        # Keep COM callback objects alive for the app lifetime
        self._env_handler   = None
        self._ctrl_handler  = None
        self._nav_handler   = None
        self._msg_handler   = None
        self._nav_token     = EventRegistrationToken()
        self._msg_token     = EventRegistrationToken()

    # ── Public entry point ─────────────────────────────────────────────────

    def run(self, build_fn: Callable):
        """Create window, init WebView2, run message loop. Blocks until closed."""
        self._build  = build_fn
        _App._current = self
        self._window = _Win32Window(self)
        _reg_listener(self._rerender)

        self._create_window()
        self._init_webview()
        self._message_loop()

    # ── Win32 window ────────────────────────────────────────────────────────

    def _create_window(self):
        """Register a Win32 window class and create the window."""
        user32 = ctypes.windll.user32

        hInst = ctypes.windll.kernel32.GetModuleHandleW(None)

        WNDPROC_T = WINFUNCTYPE(
            ctypes.c_long,
            ctypes.wintypes.HWND, ctypes.c_uint,
            ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM
        )
        self._wndproc_fn = WNDPROC_T(self._wndproc)   # keep alive

        wc = WNDCLASSEXW()
        wc.cbSize        = ctypes.sizeof(WNDCLASSEXW)
        wc.style         = CS_HREDRAW | CS_VREDRAW
        wc.lpfnWndProc   = ctypes.cast(self._wndproc_fn, c_void_p)
        wc.hInstance     = hInst
        wc.hCursor       = user32.LoadCursorW(None, IDC_ARROW)
        wc.hbrBackground = ctypes.wintypes.HANDLE(6)  # COLOR_WINDOW + 1
        wc.lpszClassName = 'GuileApp'

        user32.RegisterClassExW(ctypes.byref(wc))

        style = WS_OVERLAPPEDWINDOW
        if not self.resizable:
            # Remove resize borders and maximize box
            style &= ~(WS_THICKFRAME | WS_MAXIMIZEBOX)

        self._hwnd = user32.CreateWindowExW(
            0,                          # dwExStyle
            'GuileApp',                 # lpClassName
            self.title,                 # lpWindowName
            style,                      # dwStyle
            0x80000000,                 # x  — CW_USEDEFAULT
            0x80000000,                 # y
            self.width,                 # nWidth
            self.height,                # nHeight
            None,                       # hWndParent
            None,                       # hMenu
            hInst,                      # hInstance
            None,                       # lpParam
        )
        if not self._hwnd:
            raise RuntimeError('[guile] CreateWindowExW failed')

        user32.ShowWindow(self._hwnd, SW_SHOW)
        user32.UpdateWindow(self._hwnd)

    def _wndproc(self, hwnd, msg, wparam, lparam):
        """Win32 window procedure."""
        if msg == WM_DESTROY:
            self._on_closed()
            ctypes.windll.user32.PostQuitMessage(0)
            return 0

        if msg == WM_SIZE:
            self._resize_webview()
            return 0

        if msg == _WM_EVAL_JS:
            self._drain_js_queue()
            return 0

        return ctypes.windll.user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _resize_webview(self):
        """Resize WebView2 to fill the client area of the Win32 window."""
        if not self._controller or not self._hwnd:
            return
        rc = RECT()
        ctypes.windll.user32.GetClientRect(self._hwnd, ctypes.byref(rc))
        # ICoreWebView2Controller.put_Bounds is vtable index 6
        # Signature: HRESULT put_Bounds(RECT bounds)
        # On x64, RECT (16 bytes) is passed by pointer (hidden first arg)
        _vtbl(self._controller, 6, HRESULT,
              ctypes.POINTER(RECT))(self._controller, ctypes.byref(rc))

    # ── WebView2 initialisation ─────────────────────────────────────────────

    def _init_webview(self):
        """
        Start async WebView2 environment creation.
        The chain: environment → controller → webview → polyfill → render.
        """
        create_env = _load_webview2()

        # User data folder: local app data / guile / <app title>
        app_data = os.environ.get('LOCALAPPDATA', tempfile.gettempdir())
        user_data = str(Path(app_data) / 'guile' / self.title)
        os.makedirs(user_data, exist_ok=True)

        # Fixed Version folder (None = use system evergreen runtime)
        fixed_folder = os.environ.get('WEBVIEW2_BROWSER_EXECUTABLE_FOLDER')

        self._env_handler = _EnvHandler(self._on_env_created)
        hr = create_env(fixed_folder, user_data, None,
                        self._env_handler.ptr)
        if hr != S_OK:
            raise RuntimeError(
                f'[guile] CreateCoreWebView2EnvironmentWithOptions failed '
                f'(HRESULT 0x{hr & 0xFFFFFFFF:08X}). '
                f'Is the WebView2 Runtime installed?'
            )

    def _on_env_created(self, environment: int):
        """
        ICoreWebView2Environment.CreateCoreWebView2Controller (vtable index 3).
        Called on the UI thread by the COM runtime.
        """
        self._ctrl_handler = _CtrlHandler(self._on_ctrl_created)
        hr = _vtbl(environment, 3, HRESULT,
                   ctypes.wintypes.HWND, c_void_p)(
            environment, self._hwnd, self._ctrl_handler.ptr
        )
        if hr != S_OK:
            raise RuntimeError(
                f'[guile] CreateCoreWebView2Controller failed '
                f'(HRESULT 0x{hr & 0xFFFFFFFF:08X})'
            )

    def _on_ctrl_created(self, controller: int):
        """
        Called when the controller is ready. Extract the ICoreWebView2,
        configure it, inject the polyfill, and load the initial HTML.
        """
        self._controller = controller

        # Set bounds to fill the client area immediately
        self._resize_webview()

        # ICoreWebView2Controller.get_CoreWebView2 — vtable index 25
        wv_out = c_void_p(0)
        hr = _vtbl(controller, 25, HRESULT,
                   ctypes.POINTER(c_void_p))(controller, ctypes.byref(wv_out))
        if hr != S_OK or not wv_out.value:
            raise RuntimeError('[guile] get_CoreWebView2 failed')
        self._webview = wv_out.value

        # ── Configure settings ─────────────────────────────────────────────
        # ICoreWebView2.get_Settings — vtable index 3
        settings_out = c_void_p(0)
        _vtbl(self._webview, 3, HRESULT,
              ctypes.POINTER(c_void_p))(
            self._webview, ctypes.byref(settings_out))

        if settings_out.value:
            s = settings_out.value
            # put_IsStatusBarEnabled      = index 10 → 0 (hide status bar)
            # put_AreDevToolsEnabled      = index 12 → debug flag
            # put_AreDefaultContextMenusEnabled = index 14 → 0 (no right-click)
            # put_IsZoomControlEnabled    = index 18 → 0 (no Ctrl+scroll zoom)
            for idx, val in [(10, 0), (12, 1 if self.debug else 0),
                             (14, 0), (18, 0)]:
                _vtbl(s, idx, HRESULT, ctypes.c_int)(s, val)

        # ── Register WebMessage handler ────────────────────────────────────
        # ICoreWebView2.add_WebMessageReceived — vtable index 34
        self._msg_handler = _MsgHandler(self._on_message)
        _vtbl(self._webview, 34, HRESULT,
              c_void_p, ctypes.POINTER(EventRegistrationToken))(
            self._webview,
            self._msg_handler.ptr,
            ctypes.byref(self._msg_token)
        )

        # ── Register NavigationCompleted handler (fires once for first load) ─
        # ICoreWebView2.add_NavigationCompleted — vtable index 15
        self._nav_handler = _NavHandler(self._on_nav_completed)
        _vtbl(self._webview, 15, HRESULT,
              c_void_p, ctypes.POINTER(EventRegistrationToken))(
            self._webview,
            self._nav_handler.ptr,
            ctypes.byref(self._nav_token)
        )

        # ── Inject pywebview polyfill before any page script runs ─────────
        # ICoreWebView2.AddScriptToExecuteOnDocumentCreated — vtable index 27
        # handler = NULL (fire-and-forget, we don't need the script ID)
        _vtbl(self._webview, 27, HRESULT,
              ctypes.wintypes.LPCWSTR, c_void_p)(
            self._webview, _POLYFILL, None
        )

        # ── Load the guile HTML shell ──────────────────────────────────────
        # ICoreWebView2.NavigateToString — vtable index 6
        html = get_html(self.title, use_leaflet=self._use_leaflet)
        _vtbl(self._webview, 6, HRESULT,
              ctypes.wintypes.LPCWSTR)(self._webview, html)

    def _on_nav_completed(self):
        """
        First page load is done. Mark ready and trigger the first render.
        Runs on the UI thread (called from the COM callback).
        """
        self._ready = True
        _ui_set_window(self._window)
        # Remove the navigation handler — we only need it once
        # ICoreWebView2.remove_NavigationCompleted — vtable index 16
        _vtbl(self._webview, 16, HRESULT,
              EventRegistrationToken)(self._webview, self._nav_token)
        self._render()

    # ── Message bridge (JS → Python) ────────────────────────────────────────

    def _on_message(self, msg_json: str):
        """
        Called on the UI thread when JS calls window.chrome.webview.postMessage.
        Dispatches to the appropriate handler on a daemon thread so the UI
        thread is never blocked.
        """
        try:
            data   = json.loads(msg_json)
            method = data.get('method', '')
            cid    = data.get('cid')
            value  = data.get('value')

            if method == 'handle':
                threading.Thread(
                    target=self._dispatch_and_render,
                    args=(cid, value),
                    daemon=True
                ).start()

            elif method == 'silent_update':
                threading.Thread(
                    target=_dispatch_silent,
                    args=(cid, value),
                    daemon=True
                ).start()

            # 'ready' is ignored — we handle it via _on_nav_completed

        except Exception:
            import traceback; traceback.print_exc()

    def _dispatch_and_render(self, cid: str, value):
        """Runs on a daemon thread. Dispatch the event then re-render."""
        _dispatch(cid, value)
        self._render()

    # ── Render loop ─────────────────────────────────────────────────────────

    def _rerender(self):
        """Called by State on every .set(). Triggers a re-render if ready."""
        if self._ready:
            self._render()

    def _render(self):
        """
        Run ui(), serialise to HTML, push to WebView2 via evaluate_js.

        Uses the same loop-not-recursion pattern as the pywebview backend
        to handle renders that arrive mid-render without infinite looping.
        """
        if not self._build or not self._webview or not self._ready:
            return
        if self._rendering:
            self._needs_render = True
            return
        while True:
            self._rendering    = True
            self._needs_render = False
            try:
                _reset_render()
                root = Column(fill=True)
                root.__enter__()
                self._build()
                root.__exit__(None, None, None)
                _commit_callbacks()
                js = f"window._guile.update({json.dumps(root.render())})"
                self._window.evaluate_js(js)   # queues + PostMessage
            except Exception:
                import traceback; traceback.print_exc()
            finally:
                self._rendering = False
            if self._needs_render:
                self._needs_render = False
            else:
                break

    def _drain_js_queue(self):
        """
        Called on the UI thread when _WM_EVAL_JS arrives.
        Executes all queued JS strings via ICoreWebView2.ExecuteScript.
        ExecuteScript MUST be called from the UI thread — this is why
        we marshal it here rather than calling it directly from _render().
        """
        if not self._webview:
            return
        while True:
            try:
                js = self._js_queue.get_nowait()
            except _queue_module.Empty:
                break
            try:
                # ICoreWebView2.ExecuteScript — vtable index 29
                # Second arg is the completion handler — NULL = fire and forget
                _vtbl(self._webview, 29, HRESULT,
                      ctypes.wintypes.LPCWSTR, c_void_p)(
                    self._webview, js, None
                )
            except Exception:
                import traceback; traceback.print_exc()

    # ── Window lifecycle ────────────────────────────────────────────────────

    def _on_closed(self):
        """Clean up when the user closes the window."""
        self._ready = False
        _ui_set_window(None)
        _unreg_listener(self._rerender)
        _clear_state_store()
        # Close the WebView2 controller
        if self._controller:
            try:
                # ICoreWebView2Controller.Close — vtable index 24
                _vtbl(self._controller, 24, HRESULT)(self._controller)
            except Exception:
                pass

    def _message_loop(self):
        """Standard Win32 message loop. Blocks until WM_QUIT."""
        msg = MSG()
        while ctypes.windll.user32.GetMessageW(
                ctypes.byref(msg), None, 0, 0) > 0:
            ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
            ctypes.windll.user32.DispatchMessageW(ctypes.byref(msg))
