import re
import warnings
from collections import defaultdict
from typing import Dict, List, Type

from direct.directnotify import DirectNotifyGlobal
from direct.showbase.DirectObject import DirectObject

from otp.otpbase import OTPLocalizer

from toontown.toonbase import ToontownGlobals, HotkeySettings

import string
import sys

from toontown.toonbase.HotkeySettings import HotkeySetting


class ControlManager(DirectObject):
    notify = DirectNotifyGlobal.directNotify.newCategory('ControlManager')
    KeyStringToSetting: Dict[str, Type[HotkeySetting]] = {}

    def __init__(self):
        DirectObject.__init__(self)
        self.changing = False
        self.marioHotkeys = False
        self.disableChat = 1
        self.disabledHotkeys = []
        self.activeHotkeys = []
        self.pressedHotkeys = set()
        self.changedHotkeys = {ToontownGlobals.HotkeyMovement: [],
                               ToontownGlobals.HotkeyInteraction: [],
                               ToontownGlobals.HotkeyDebug: [],
                               ToontownGlobals.HotkeyMisc: []}
        self.disableAlphaNumericHotkeys = False
        self.reloadHotkeys(True)

        for key in HotkeySettings.getAllHotkeys():
            ControlManager.KeyStringToSetting[key.getSettingString()] = key

    def reloadHotkeys(self, realtime=False):
        self.releaseHeldHotkeys()
        self.ignoreAll()
        bindings = defaultdict(list)
        disableChat = 1
        activeHotkeys = []

        allKeys: List[Type[HotkeySetting]] = HotkeySettings.getAllHotkeys()

        for key in allKeys:
            if key.category == HotkeySettings.SettingsCategory.HOTKEY_MARIO and not self.marioHotkeys:
                continue
            boundKey = key.get()
            isAlphaNumeric: bool = self.isAlphaNumericHotkey(boundKey)
            if disableChat and isAlphaNumeric:
                disableChat = False
            activeHotkeys.append(boundKey)
            bindings[boundKey].append(key)
        for boundKey, keys in bindings.items():
            self.accept(boundKey, self.dispatchHotkeys, [boundKey, keys, False])
            self.accept(f'{boundKey}-up', self.dispatchHotkeys, [boundKey, keys, True])
        self.disableChat = disableChat
        self.activeHotkeys = activeHotkeys
        if hasattr(base, 'localAvatar') and hasattr(base.localAvatar, 'chatMgr') and base.localAvatar.chatMgr:
            base.localAvatar.chatMgr.setBackgroundFocus(disableChat, realtime)

    def setMarioHotkeys(self, enabled):
        if self.marioHotkeys != enabled:
            self.marioHotkeys = enabled
            self.reloadHotkeys()

    def dispatchHotkeys(self, boundKey, keys, released):
        for key in keys:
            if released:
                self.pressedHotkeys.discard(key)
                self.hotkeyPressed(key.getReleased(), boundKey, key)
            elif self.hotkeyPressed(key.getPressed(), boundKey, key) and not self.changing:
                self.pressedHotkeys.add(key)

    def releaseHeldHotkeys(self):
        for key in self.pressedHotkeys.copy():
            messenger.send(key.getReleased())
        self.pressedHotkeys.clear()

    def setChanging(self, state):
        if state:
            self.releaseHeldHotkeys()
        self.changing = state

    def getChanging(self):
        return self.changing

    def hotkeyPressed(self, hotkeyName, hotkey, key):
        self.notify.info(hotkeyName)
        if self.getChanging() or key in self.disabledHotkeys:
            return False
        if self.disableAlphaNumericHotkeys:
            if 'enter' in hotkey:
                messenger.send('exitChat')
                return False
            if self.isAlphaNumericHotkey(hotkey) and not hotkeyName.endswith('-up'):
                return False
        messenger.send(hotkeyName)
        return True

    def getKeyName(self, category: str, hotkey: int) -> str:
        setting = HotkeySettings.STANDARD_HOTKEYS[category].get(hotkey)
        if setting is not None:
            return setting.get()
        categoryIndex = ToontownGlobals.Hotkeys.index(category)
        return ToontownGlobals.AllHotkeys[categoryIndex][hotkey]

    @staticmethod
    def getControlName(name, label=False):
        if not name:
            name = ToontownGlobals.InvalidKey
            return name

        if ToontownGlobals.Separator in name:
            name = name.replace(ToontownGlobals.Separator, ' + ')

        for key in ToontownGlobals.SpecialKeys.keys():
            if key in name:
                value = ToontownGlobals.SpecialKeys.get(key)
                if type(value) is list:
                    if not sys.platform == 'darwin':
                        # Windows/Linux
                        value = value[0]
                    else:
                        # macOS
                        value = value[1]
                name = name.replace(key, value)
                break

        name = name.title()

        if label:
            name += ' Key'
            if '+' in name:
                name += 's'

        return name

    @staticmethod
    def parseHotkeyString(baseString: str, label: bool = False, useGlyphs = False) -> str:
        pattern = r'\$\$(.*?)\$\$'

        def replace(match):
            key = match.group(1)
            keySetting: Type[HotkeySetting] = ControlManager.KeyStringToSetting.get('s' + key, None)
            if keySetting is None:
                return f'#UNKNOWN_HOTKEY_{key}'

            if useGlyphs:
                return f'\x01white\x01\5kbm_{keySetting.get().lower()}\5\x02'
            else:
                return ControlManager.getControlName(keySetting.get(), label)

        return re.sub(pattern, replace, baseString)


    def isAlphaNumericHotkey(self, hotkey):
        for prefix in ('shift', 'control', 'alt'):
            if prefix in hotkey:
                hotkey = hotkey.replace(prefix, '')
                if ToontownGlobals.Separator in hotkey:
                    hotkey = hotkey.replace(ToontownGlobals.Separator, '')
                else:
                    return False

        if len(hotkey) > 1:
            if hotkey == 'space':
                return True
            return False

        characters = string.printable
        if hotkey in characters:
            return True

        return False

    def getChatDisabled(self):
        return self.disableChat

    def addDisabledHotkey(self, category, hotkey):
        if type(hotkey) == int:
            hotkey = self.parseHotkey(category, hotkey)

        if hotkey not in self.disabledHotkeys:
            self.disabledHotkeys.append(hotkey)

    def removeDisabledHotkey(self, category, hotkey):
        if type(hotkey) == int:
            hotkey = self.parseHotkey(category, hotkey)

        if hotkey in self.disabledHotkeys:
            self.disabledHotkeys.remove(hotkey)

    def parseHotkey(self, category, hotkey):
        if type(hotkey) != int:
            return hotkey

        if type(category) != int:
            category = ToontownGlobals.Hotkeys.index(category)

        hotkeyNames = OTPLocalizer.HotkeyNames[category]
        hotkey = hotkeyNames.get(hotkey)
        hotkey = hotkey.lower().replace(' ', '-')

        return hotkey

    def getKeyInUse(self, hotkey):
        for key in self.activeHotkeys:
            if hotkey in key:
                return True
        return False
