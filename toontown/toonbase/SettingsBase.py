# SettingsBase
# Created by drewc Apr 15 2024
import enum
from typing import Any

from direct.directnotify import DirectNotifyGlobal

from toontown.datapack.DataPackManager import DataPackManager


class SettingsCategory:
    GAME = 'GAME'
    SOUND = 'SOUND'
    VIDEO = 'VIDEO'
    RETRO = 'RETRO'
    SOCIAL = 'SOCIAL'
    ACCESSIBILITY = 'ACCESSIBILITY'
    SAVED = 'SAVED'
    CONTROL = 'CONTROL'
    HIDDEN = 'HIDDEN'

    # KEYBIND
    HOTKEY_MOVEMENT = 'MOVEMENT'
    HOTKEY_INTERACTION = 'INTERACTION'
    HOTKEY_DEBUG = 'DEBUG'
    HOTKEY_MISC = 'MISC'
    HOTKEY_MARIO = 'MARIO'

    # SERVER ONLY
    SERVER_MODERATION = 'MODERATION'
    SERVER_ACCESS = 'ACCESS'
    SERVER_DISPLAY = 'DISPLAY'
    SERVER_API = 'API'

class SettingsWarning(enum.Enum):
    SWRestart = enum.auto()
    SWReload = enum.auto()
    SWEstate = enum.auto()
    SWStreet = enum.auto()


class SettingBase:
    notify = DirectNotifyGlobal.directNotify.newCategory('RealmsSettings')
    def __init__(self, identifier, settingsFile, category, prefix, default=None, changeWarning=None, onUpdate=None):
        self.identifier = identifier
        self.category = category
        self.prefix = prefix
        self.default = default
        self.settingsFile = settingsFile
        self.changeWarning = changeWarning
        self.onUpdateCommand = onUpdate

        if self.getSettingString() not in self.settingsFile.get(self.category, {}):
            self.set(self.default, False)

    def set(self, value, update=True) -> bool:
        self.notify.info(f'Setting {self.getSettingDisplayName()} to {value}')
        if self.validate(value):
            settings = self.settingsFile
            settings.setSetting(self.category, self.getSettingString(), value)
            if update:
                self.onUpdate()
            return True
        return False

    def validate(self, value):
        return True

    def onUpdate(self):
        if self.onUpdateCommand:
            self.onUpdateCommand(self.get())
        return

    def get(self):
        self.notify.debug(f'Fetching {self.getSettingString()}')
        _val = self.settingsFile.get(self.category, {}).get(self.getSettingString(), self.default)

        if not self.validate(_val):
            return self.default
        return _val

    def getSettingString(self):
        return f'{self.prefix}{self.identifier}'

    def getSettingDisplayName(self):
        return DataPackManager.getLocalizedText(f'#Setting_{self.getSettingString()}')

    def getSettingDescription(self):
        return DataPackManager.getLocalizedText(f'#SettingDesc_{self.getSettingString()}', mustExist=True)


class BoolSetting(SettingBase):
    def __init__(self, identifier, settingsFile, default=True, **kwargs):
        SettingBase.__init__(self, identifier, settingsFile, prefix='b', default=default, **kwargs)

    def validate(self, value):
        return isinstance(value, bool)


class IntegerSetting(SettingBase):
    def __init__(self, identifier, settingsFile, minVal=0, maxVal=100, step=1, default=0, **kwargs):
        self.minVal = minVal
        self.maxVal = maxVal
        self.step = step
        SettingBase.__init__(self, identifier, settingsFile, prefix='i', default=default, **kwargs)

    def validate(self, value):
        if not isinstance(value, int):
            self.notify.warning(f"setting {self.identifier} to {value} failed: is not int")
            return False
        if not self.minVal <= value <= self.maxVal:
            self.notify.warning(f"setting {self.identifier} to {value} failed: is not in range")
            return False
        return True


class FloatSetting(SettingBase):
    def __init__(self, identifier, settingsFile, minVal=0.0, maxVal=1.0, **kwargs):
        self.minVal = minVal
        self.maxVal = maxVal
        SettingBase.__init__(self, identifier, settingsFile, prefix='f', **kwargs)

    def validate(self, value):
        if not isinstance(value, (float, int)):
            return False
        if not self.minVal <= value <= self.maxVal:
            self.notify.warning(f"setting {self.identifier} to {value} failed: is not in range")
            return False
        return True


class StringSetting(SettingBase):
    def __init__(self, identifier, settingsFile, **kwargs):
        SettingBase.__init__(self, identifier, settingsFile, prefix='s', **kwargs)

    def validate(self, value):
        return isinstance(value, str)


class ListSetting(SettingBase):
    def __init__(self, identifier, settingsFile, listType=Any, length=-1, **kwargs):
        self.listType = listType
        self.length = length
        SettingBase.__init__(self, identifier, settingsFile, prefix='l', **kwargs)

    def validate(self, value):
        return isinstance(value, list)


class EnumSetting(IntegerSetting):
    def __init__(self, identifier, settingsFile, enum, **kwargs):
        self.enum = enum
        IntegerSetting.__init__(self, identifier, settingsFile, **kwargs)

    def set(self, value, update=True):
        self.notify.debug(f'Setting {self.getSettingDisplayName()} to {value}')
        if self.validate(value):
            settings = self.settingsFile
            settings.setSetting(self.category, self.getSettingString(), value.value)
            if update:
                self.onUpdate()
            return True
        return False

    def get(self):
        self.notify.debug(f'Fetching {self.getSettingString()}')
        _val = self.settingsFile.get(self.category, {}).get(self.getSettingString(), self.default)
        if isinstance(_val, int):
            _val = self.enum(_val)
        if not self.validate(_val):
            return self.default
        return _val

    def validate(self, value):
        return True

