from direct.controls import ControlManager
from typing import Dict

from direct.controls.InputState import InputStateToken
from direct.showbase.InputStateGlobal import inputState

from toontown.toonbase import HotkeySettings


class OTPControlManager(ControlManager.ControlManager):

    def __init__(self, enable = True):
        assert self.notify.debugCall(id(self))
        self.inputStateTokens: Dict[str, InputStateToken] = {}
        self.controls = {}
        self.currentControls = None
        self.currentControlsName = None
        self.isEnabled = False
        self.marioControls = False
        self.wantStrafe = False
        self.movementTokens = set()
        if enable:
            self.enable()
        self.forceAvJumpToken = None

    def enable(self):
        assert self.notify.debugCall(id(self))

        if self.isEnabled:
            assert self.notify.debug('already isEnabled')
            return

        self.isEnabled = True

        self.bindMovement()

        if self.currentControls:
            self.currentControls.enableAvatarControls()

    def bindMovement(self):
        keys = HotkeySettings
        if self.marioControls:
            settings = {'forward': keys.MarioForward, 'reverse': keys.MarioBackward,
                        'jump': keys.MarioJump, 'descend': keys.MarioCrouch,
                        'marioPunch': keys.MarioPunch}
            left, right = keys.MarioLeft, keys.MarioRight
        else:
            settings = {'forward': keys.MoveForward, 'reverse': keys.MoveBackward,
                        'jump': keys.Jump, 'descend': keys.FlyDescend}
            left, right = keys.MoveLeft, keys.MoveRight

        turn, slide = ('slide', 'turn') if self.wantStrafe else ('turn', 'slide')
        held = {side: inputState.isSet(turn + side, inputSource='OTPControls')
                      or inputState.isSet(slide + side, inputSource='OTPControls')
                for side in ('Left', 'Right')}
        for name, setting in ((turn + 'Left', left), (turn + 'Right', right)):
            settings[name] = setting

        for name in self.movementTokens - settings.keys():
            self.releaseToken(name)
            inputState.set(name, False, inputSource='OTPControls')

        for name, setting in settings.items():
            if name not in self.inputStateTokens:
                self.inputStateTokens[name] = inputState.watch(
                    name, setting.getPressed(), setting.getReleased(),
                    startState=held.get(name[len(turn):], False), inputSource='OTPControls')
        self.movementTokens = set(settings)

    def setMarioControls(self, enabled):
        if self.marioControls == enabled:
            return
        self.marioControls = enabled
        if self.isEnabled:
            for name in self.movementTokens:
                self.releaseToken(name)
                inputState.set(name, False, inputSource='OTPControls')
            self.movementTokens.clear()
            self.bindMovement()

    def setStrafing(self, wantStrafe):
        self.wantStrafe = wantStrafe
        if self.isEnabled:
            self.bindMovement()

    def addToken(self, tokenName, token):
        self.inputStateTokens[tokenName] = token

    def releaseToken(self, tokenName):
        if tokenName in self.inputStateTokens.keys():
            self.inputStateTokens[tokenName].release()
            del self.inputStateTokens[tokenName]

    def disable(self):
        assert self.notify.debugCall(id(self))
        self.isEnabled = False

        for tokenName in self.inputStateTokens.keys():
            inputState.set(tokenName, False, inputSource = 'OTPControls')

        for token in list(self.inputStateTokens.values()):
            token.release()
        self.inputStateTokens: Dict[str, InputStateToken] = {}
        self.movementTokens.clear()

        if self.currentControls:
            self.currentControls.disableAvatarControls()

    def delete(self):
        assert self.notify.debugCall(id(self))
        self.disable()
        for controls in list(self.controls.keys()):
            self.remove(controls)
        del self.controls
        del self.currentControls
        del self.inputStateTokens
