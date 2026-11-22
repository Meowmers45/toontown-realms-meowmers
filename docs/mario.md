<!-- coderabbit-ai-generated:v1 -->

# Mario mode

Mario mode is optional. It uses your local Toon's collision body, movement, interaction keys, and zone loading. The model and animations come from libsm64. Mario's punch and crouch are visual moves; crouch also substitutes for Descend while flying. Other players still see your Toon.

## Set up

1. Create a `mario` directory at the root of the game checkout (next to `resources`).
2. Put your own unmodified Super Mario 64 US ROM in that directory as `sm64.z64`. The ROM is not included.
3. Build [libsm64](https://github.com/libsm64/libsm64) at commit `fd11813208272b4271d92bd92feb8f3fdbe61be5` with `make lib` as described by libsm64. On Windows, use the MinGW 64 environment in its build instructions. Copy the resulting library from `dist/` into `mario/`: `sm64.dll` for Windows, `libsm64.so` for Linux, or `libsm64.dylib` for macOS. Use a build that matches the game interpreter's architecture; the bindings target this specific libsm64 revision.
4. Launch Toontown and type `~mario` in chat where magic words are enabled. Type it again to switch back to your Toon.

The default Mario keys are the arrow keys for movement, **J** for jump, **K** for punch, and **L** for crouch. Change them under **Settings > Game > Mario Controls**. The usual interaction keys still work.

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:8771dac91c14a29f73b3d3ceefb0184273a28e1cf6799f0911929fae3ef20a47 -->

## Windows Panda3D

The [Windows build](../.github/workflows/windows-panda3d.yml) produces an x64 Panda3D installer for Windows 11, including the Lenovo Legion Go. Open the **panda3d-ttoff-windows-x64-installer** artifact from a successful run and run the installer. It includes Python 3.12 and defaults to `%LOCALAPPDATA%\Panda3D-TTRMDev-1.11.0-x64`.

In the game checkout, run the following to install the game's Python dependency:

```bat
"%LOCALAPPDATA%\Panda3D-TTRMDev-1.11.0-x64\python\ppython.exe" -m pip install -r requirements.txt
```

Then run `win32\start_game.bat` from its directory. The launcher uses a valid `PPYTHON_PATH` first and otherwise finds the per-user installation. If you install Panda3D somewhere else, put the full path to its `python\ppython.exe` in `PPYTHON_PATH`.

The Lenovo Legion Go has a touch screen, touchpad, and detachable controllers. The game's existing controls are keyboard and mouse bindings; the installer does not configure controller mappings.

<!-- /coderabbit-ai-generated:v1 -->

## Credits

The mesh adapter and shaders are based on [TheFlowerVixen/libsm64-panda](https://github.com/TheFlowerVixen/libsm64-panda/tree/753f67d33519f1116ab620a4e5d84b64df995963), used under the [MIT license](../toontown/mario/LICENSE-MIT).
