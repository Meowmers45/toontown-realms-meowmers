<!-- coderabbit-ai-generated:v1 -->

# Mario mode

Mario mode is optional. It uses your local Toon's collision body, movement, interaction keys, and zone loading. The model and animations come from libsm64. Mario's punch and crouch are visual moves; crouch also substitutes for Descend while flying. Other players still see your Toon.

## Set up

1. Create a `mario` directory at the root of the game checkout (next to `resources`).
2. Put your own unmodified Super Mario 64 US ROM in that directory as `sm64.z64`. The ROM is not included.
3. Build [libsm64](https://github.com/libsm64/libsm64) at commit `fd11813208272b4271d92bd92feb8f3fdbe61be5` with `make lib` as described by libsm64. On Windows, use the MinGW 64 environment in its build instructions. Copy the resulting library from `dist/` into `mario/`: `sm64.dll` for Windows, `libsm64.so` for Linux, or `libsm64.dylib` for macOS. Use a build that matches the game interpreter's architecture; the bindings target this specific libsm64 revision.
4. Launch Toontown and type `~mario` in chat where magic words are enabled. Type it again to switch back to your Toon.

The default Mario keys are the arrow keys for movement, **J** for jump, **K** for punch, and **L** for crouch. Change them under **Settings > Game > Mario Controls**. The usual interaction keys still work.

## Windows Panda3D

The [Windows Panda3D workflow](../.github/workflows/windows-panda3d.yml) builds an x64 Python 3.12 wheel from the [Meowmers Panda3D fork](https://github.com/Meowmers45/panda3d-ttoff-Meowmers). Download and extract its artifact from the workflow run after it passes. Install the wheel and the game's requirements using the same Python installation:

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:d5b67b1c17845ec7a8245effdc0db18b9242f525568dbb3fdc210367f07c7888 -->

```powershell
py -3.12 -m pip install ".\panda3d-<version>-cp312-cp312-win_amd64.whl"
py -3.12 -m pip install -r requirements.txt
$env:TTOFF_PLAY_TOKEN = 'dev'
$env:TTOFF_GAME_MODE = '0'
py -3.12 -m toontown.launcher.ToontownOfflineQuickStartLauncher
```

<!-- /coderabbit-ai-generated:v1 -->

Replace the wheel name with the downloaded file name. Alternatively, point the local `PPYTHON_PATH` file at that Python executable and use `win32/start_game.bat`.

## Credits

The mesh adapter and shaders are based on [TheFlowerVixen/libsm64-panda](https://github.com/TheFlowerVixen/libsm64-panda/tree/753f67d33519f1116ab620a4e5d84b64df995963), used under the [MIT license](../toontown/mario/LICENSE-MIT).
