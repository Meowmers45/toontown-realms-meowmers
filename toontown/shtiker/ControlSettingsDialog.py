from direct.fsm import StateData
from direct.gui.DirectGui import *
from direct.directnotify import DirectNotifyGlobal

from otp.otpbase import OTPLocalizer

from panda3d.core import *

from otp.otpgui import OTPGUIUtils
from toontown.toonbase import HotkeySettings, TTLocalizer
from toontown.toonbase import ToontownGlobals
from toontown.toontowngui import TTDialog
from toontown.toontowngui.ToontownScrolledFrame import ToontownScrolledFrame

MARIO_KEYS = (
    HotkeySettings.MarioForward, HotkeySettings.MarioBackward,
    HotkeySettings.MarioLeft, HotkeySettings.MarioRight,
    HotkeySettings.MarioJump, HotkeySettings.MarioPunch, HotkeySettings.MarioCrouch,
)


class ControlSettingsDialog(DirectFrame, StateData.StateData):
    notify = DirectNotifyGlobal.directNotify.newCategory('ControlSettingsDialog')

    settingsButtonsModel = loader.loadModel('phase_3/models/gui/ttoff_m_gui_opts_buttons', allowInstance = True)
    settingsDropdownModel = loader.loadModel('phase_3/models/gui/ttoff_m_gui_opts_dropdown', allowInstance = True)
    colorPickerModel = loader.loadModel("phase_3/models/gui/ttoff_m_gui_opts_colorpicker", allowInstance = True)

    def __init__(self, parent = aspect2d):
        DirectFrame.__init__(self, parent = parent, relief = None, pos = (0, 0, 0.0), scale = 1.2,
                             image = self.colorPickerModel.find("**/temp_bg"),
                             image_scale = (1.7, 1, 1.7), image_pos = (0, 0, -0.05),
                             text = TTLocalizer.ControlSettingsTitle, text_scale = 0.12, text_pos = (0, 0.65),
                             borderWidth = (0.01, 0.01))
        StateData.StateData.__init__(self, 'control-settings-done')
        self.setBin('gui-popup', 0)
        self.initialiseoptions(ControlSettingsDialog)
        self.category = 0
        self.categoryButtons = []
        self.keyButtons = []
        self.controls = {}
        self.queuedKey = None
        self.button = None
        self._dialog = None
        self.unknownKey = False
        self.mario = False
        self.captureEvents = None
        return

    def unload(self):
        self.exit()
        DirectFrame.destroy(self)
        return None

    def load(self):
        guiButton = loader.loadModel('phase_3/models/gui/quit_button')
        gui = loader.loadModel('phase_3.5/models/gui/friendslist_gui')
        nameShopGui = loader.loadModel('phase_3/models/gui/nameshop_gui')
        circleModel = loader.loadModel('phase_3/models/gui/tt_m_gui_mat_nameShop')
        texture = loader.loadTexture('phase_3/maps/slider.png')
        buttonImage = (self.settingsButtonsModel.find('**/button_green_up'),
                       self.settingsButtonsModel.find('**/button_green_down'),
                       self.settingsButtonsModel.find('**/button_green_rollover'))
        scrollBkgd = OnscreenImage(image = texture)
        scrollBkgd.setTransparency(TransparencyAttrib.MAlpha)
        self.apply = DirectButton(parent = self, relief = None, pos = (0.32, 0, -0.75), image = buttonImage,
                                  image_scale = (0.4, 0, 0.11),
                                  text = TTLocalizer.DisplaySettingsApply, text_scale = 0.06,
                                  text_pos = (0.0, -0.015),
                                  pressEffect = False,
                                  command = self.__apply)
        self.cancel = DirectButton(parent = self, relief = None, pos = (0.7, 0, 0.66),
                                   image = (self.settingsButtonsModel.find('**/close_button_normal'),
                                            self.settingsButtonsModel.find('**/close_button_click'),
                                            self.settingsButtonsModel.find('**/close_button_hover')),
                                   image_scale = .14, pressEffect = False,
                                   command = self.__cancel)
        self.reset = DirectButton(parent = self, relief = None, pos = (-0.32, 0, -0.75), image = buttonImage,
                                  image_scale = (0.4, 0, 0.11),
                                  text = TTLocalizer.ControlSettingsReset, text_scale = 0.06,
                                  text_pos = (0.0, -0.015),
                                  pressEffect = False,
                                  command = self.__reset)
        self.infoLabel = DirectLabel(parent = self, relief = None, text = TTLocalizer.ControlSettingsInfoLabelDefault,
                                     text_scale = TTLocalizer.CSButton, pos = (0.0, 0, -0.65))
        settingsScrollbarModel = loader.loadModel('phase_3.5/models/gui/ttoff_m_gui_sbk_generic', allowInstance = True)
        self.hotkeysList = ToontownScrolledFrame(parent = self,
                                                 relief = DGG.SUNKEN,
                                                 borderWidth = (0.01, 0.01),
                                                 pos = (0, 0.0, -0.1),
                                                 height = 0.5,
                                                 width = .63,
                                                 itemMargin = (.36, 0),
                                                 itemPadding = .12,
                                                 frameColor = (0.85, 0.95, 1, 1),
                                                 autoHideScrollBars = True,
                                                 manageScrollBars = False,
                                                 verticalScroll_frameColor = (0, 0, 0, 0),
                                                 verticalScroll_manageButtons = False,
                                                 verticalScroll_thumb_geom = (
                                                     settingsScrollbarModel.find('**/scrollbar_normal'),
                                                     settingsScrollbarModel.find('**/scrollbar_press'),
                                                     settingsScrollbarModel.find('**/scrollbar_hover')),
                                                 verticalScroll_thumb_geom_scale = OTPGUIUtils.getImageScale(151, 399, 0.15),
                                                 verticalScroll_thumb_relief = None,
                                                 verticalScroll_resizeThumb = False,
                                                 verticalScroll_decButton_relief = None,
                                                 verticalScroll_incButton_relief = None)

        guiButton.removeNode()
        gui.removeNode()
        nameShopGui.removeNode()
        circleModel.removeNode()
        scrollBkgd.destroy()
        self.hide()

    def generateHotkeyButtons(self):
        if self.categoryButtons:
            for button in self.categoryButtons:
                button.destroy()
                del button
            self.categoryButtons = []

        if self.keyButtons:
            for button in self.keyButtons:
                label = button[3]
                label.destroy()
                del label
                button = button[2]
                button.destroy()
                del button
            self.keyButtons = []

        self.controls = {}

        guiButton = loader.loadModel('phase_3/models/gui/quit_button')
        buttonImage = (self.settingsButtonsModel.find('**/button_green_up'),
                       self.settingsButtonsModel.find('**/button_green_down'),
                       self.settingsButtonsModel.find('**/button_green_rollover'),
                       self.settingsButtonsModel.find('**/button_green_selected'))

        posX = -0.88
        xOffset = 0.35
        names = (TTLocalizer.MarioControlSettingsTitle,) if self.mario else (
            OTPLocalizer.HotkeyCategoryNames[category] for category in ToontownGlobals.Hotkeys
        )
        self.category = 0
        for index, name in enumerate(names):
            button = DirectButton(parent = self, relief = None, text = name,
                                  image = buttonImage, image_scale = (0.28, 1.0, 0.088), text_scale = TTLocalizer.CSButton,
                                  text_pos = (0.0, -0.014),
                                  pos = (0 if self.mario else posX + (xOffset * (index + 1)), 0, 0.5),
                                  pressEffect = False, command = self.__changeCategory, extraArgs = [index])
            self.categoryButtons.append(button)
        self.__changeCategory(0)

        guiButton.removeNode()

    def enter(self, inBook = True, mario = False):
        self.mario = mario
        self.unknownKey = False
        self['text'] = TTLocalizer.MarioControlSettingsTitle if mario else TTLocalizer.ControlSettingsTitle
        base.controlManager.setChanging(True)
        self.inBook = inBook
        base.transitions.fadeScreen(0.5)
        if not self.inBook:
            self.reparentTo(aspect2dp)
        if hasattr(base, 'localAvatar') and hasattr(base.localAvatar, 'chatMgr') and base.localAvatar.chatMgr:
            base.localAvatar.chatMgr.setBackgroundFocus(False, True)
        self.generateHotkeyButtons()
        if self.unknownKey:
            self.__promptUnknownNotice()
        self.show()
        return

    def exit(self):
        self.__stopKeyCapture()
        base.controlManager.setChanging(False)
        if self.inBook:
            base.transitions.noTransitions()
        if hasattr(base, 'localAvatar') and hasattr(base.localAvatar, 'chatMgr') and base.localAvatar.chatMgr:
            base.localAvatar.chatMgr.setBackgroundFocus(base.controlManager.getChatDisabled(), True)
        self.__changeCategory(0)
        self.infoLabel['text'] = TTLocalizer.ControlSettingsInfoLabelDefault
        if self.button:
            self.button['state'] = DGG.NORMAL
            self.button = None
        self.ignoreAll()
        self.hide()
        messenger.send(self.doneEvent)
        return None

    def __promptUnknownNotice(self):
        self._dialog = TTDialog.TTDialog(style = TTDialog.Acknowledge, text = TTLocalizer.ControlSettingsHotkeyWarning,
                                         command = self.__confirmUnknownNotice)
        self._dialog.show()
        self.hide()

    def __confirmUnknownNotice(self, state):
        if hasattr(self, '_dialog') and self._dialog:
            self._dialog.destroy()
            self._dialog = None
        base.transitions.fadeScreen(0.5)
        self.show()

    def __apply(self):
        self.applyChanges()
        self.infoLabel['text'] = TTLocalizer.ControlSettingsChangesApplied

    def __cancel(self):
        self.exit()

    def __reset(self):
        self._dialog = TTDialog.TTDialog(style = TTDialog.TwoChoice, text = TTLocalizer.ControlSettingsResetWarning,
                                         command = self.__confirmResetNotice)
        self._dialog.show()
        self.hide()

    def __confirmResetNotice(self, state):
        if hasattr(self, '_dialog') and self._dialog:
            self._dialog.destroy()
            self._dialog = None
        base.transitions.fadeScreen(0.5)

        if state == 1 and self.mario:
            for key in MARIO_KEYS:
                key.set(key.default)
            base.controlManager.reloadHotkeys()
            self.infoLabel['text'] = TTLocalizer.ControlSettingsResetApplied
            self.generateHotkeyButtons()
        elif state == 1:
            hotkeys = ToontownGlobals.Hotkeys
            for controlType in hotkeys:
                controlIndex = hotkeys.index(controlType)
                controlCategory = {}

                controlDefaults = ToontownGlobals.AllHotkeys[controlIndex]
                categoryNames = OTPLocalizer.HotkeyNames[controlIndex]
                for key in controlDefaults.keys():
                    default = controlDefaults.get(key)
                    hotkeyName = categoryNames.get(key)
                    if not hotkeyName:
                        continue
                    hotkeyName = hotkeyName.lower().replace(' ', '-')
                    controlCategory[hotkeyName] = default

                base.settings.updateSetting('keybinds', controlType, controlCategory)

            base.controlManager.reloadHotkeys()
            self.infoLabel['text'] = TTLocalizer.ControlSettingsResetApplied
            self.generateHotkeyButtons()

        self.show()

    def __changeCategory(self, index):
        self.categoryButtons[self.category]['state'] = DGG.NORMAL
        self.categoryButtons[index]['state'] = DGG.DISABLED

        self.category = index

        self.keyButtons = []
        self.hotkeysList.clearItems()

        buttonImage = (self.settingsButtonsModel.find('**/button_green_up'),
                       self.settingsButtonsModel.find('**/button_green_down'),
                       self.settingsButtonsModel.find('**/button_green_rollover'))
        if self.mario:
            hotkeys = range(len(MARIO_KEYS))
            names = dict(enumerate(TTLocalizer.MarioControlSettingsKeys))
            controlCategory = self.controls.setdefault('mario', {i: key.get() for i, key in enumerate(MARIO_KEYS)})
        else:
            hotkeys = ToontownGlobals.AllHotkeys[index].keys()
            categoryName = ToontownGlobals.Hotkeys[index]
            names = OTPLocalizer.HotkeyNames[index]
            controlCategory = base.settings.getOption('keybinds', categoryName, {})
            self.controls[categoryName] = controlCategory
        btns = []
        for hotkey in hotkeys:
            hotkeyName = names.get(hotkey)
            if not hotkeyName:
                continue
            setting = hotkey if self.mario else base.controlManager.parseHotkey(index, hotkey)
            keyName = base.controlManager.getControlName(controlCategory.get(setting))
            if keyName == ToontownGlobals.InvalidKey:
                self.unknownKey = True

            button = DirectButton(parent = self, relief = None, image = buttonImage, image_scale = (0.4, 1.0, 0.11),
                                  text = keyName, text_scale = TTLocalizer.CSKeyButton, pressEffect = False,
                                  text_pos = (0.0, -0.014), pos = (0.34, 0, 0))
            label = DirectLabel(parent = button, relief = None, text = hotkeyName, text_align = TextNode.ALeft,
                                text_scale = TTLocalizer.CSButton, text_pos = TTLocalizer.DSDcancelPos,
                                pos = (-.9, 0, 0))
            button.bind(DGG.B1RELEASE, self.__changeKey, extraArgs = [index, hotkey])
            self.keyButtons.append((index, hotkey, button, label))
            btns.append(button)
        self.hotkeysList.addItems(*btns)

    def __changeKey(self, category, id, event):
        self.ignoreAll()
        if self.button:
            self.button['state'] = DGG.NORMAL

        self._dialog = TTDialog.TTDialog(style = TTDialog.CancelOnly, text = TTLocalizer.ControlSettingsInfoLabelChangeKey,
                                         command = self.__cancelChangeKey)
        self._dialog.show()
        self.hide()

        self.button = self.getButton(category, id)
        self.button['state'] = DGG.DISABLED

        thrower = base.buttonThrowers[0].node()
        self.captureEvents = thrower, thrower.getButtonDownEvent(), thrower.getButtonUpEvent()

        event = 'pressButton'
        thrower.setButtonDownEvent(event)
        self.acceptOnce(event, self.pressedButton, [self.button, category, id])

        event = 'releaseButton'
        thrower.setButtonUpEvent(event)
        self.acceptOnce(event, self.releasedButton, [self.button, category, id])

    def __stopKeyCapture(self):
        self.ignore('pressButton')
        self.ignore('releaseButton')
        self.queuedKey = None
        if self.captureEvents:
            thrower, down, up = self.captureEvents
            thrower.setButtonDownEvent(down)
            thrower.setButtonUpEvent(up)
            self.captureEvents = None

    def __cancelChangeKey(self, _):
        self.__stopKeyCapture()
        self.button['state'] = DGG.NORMAL
        self.button = None
        if hasattr(self, '_dialog') and self._dialog:
            self._dialog.destroy()
            self._dialog = None

        base.transitions.fadeScreen(0.5)
        self.show()

    def getButton(self, category, id):
        for button in self.keyButtons:
            if button[0] == category and button[1] == id:
                return button[2]

    def pressedButton(self, button, category, id, key):
        if key[1:] in ('shift', 'control', 'alt') and (key.startswith('l') or key.startswith('r')):
            event = 'pressButton'
            self.acceptOnce(event, self.pressedButton, [button, category, id])
            return
        if key in ('shift', 'control', 'alt'):
            self.queuedKey = key
            event = 'pressButton'
            self.acceptOnce(event, self.pressedButton, [button, category, id])
        elif self.queuedKey:
            self.ignore('releaseButton')
            self.releasedButton(button, category, id, key)

    def releasedButton(self, button, category, hotkey, key):
        if key[1:] in ('shift', 'control', 'alt') and (key.startswith('l') or key.startswith('r')):
            return

        if key in ('shift', 'control', 'alt'):
            self.queuedKey = None

        if self.mario:
            activeHotkeys = [value for i, value in self.controls['mario'].items() if i != hotkey]
            activeHotkeys.extend(setting.get() for setting in HotkeySettings.getAllHotkeys()
                                 if setting.category not in (HotkeySettings.SettingsCategory.HOTKEY_MARIO,
                                                             HotkeySettings.SettingsCategory.HOTKEY_MOVEMENT))
        else:
            activeHotkeys = self.getActiveHotkeys()
        if key in activeHotkeys or 'mouse' in key or 'wheel' in key:
            message = TTLocalizer.ControlSettingsAlreadyInUse
            if 'mouse' in key or 'wheel' in key:
                message = TTLocalizer.ControlSettingsInfoLabelChangeKey
            self.infoLabel['text'] = message

            event = 'pressButton'
            self.acceptOnce(event, self.pressedButton, [button, category, hotkey])

            event = 'releaseButton'
            self.acceptOnce(event, self.releasedButton, [button, category, hotkey])
            return

        self.__stopKeyCapture()
        if self.mario:
            self.controls['mario'][hotkey] = key
        else:
            categoryName = ToontownGlobals.Hotkeys[category]
            self.controls[categoryName][base.controlManager.parseHotkey(category, hotkey)] = key

        self.infoLabel['text'] = TTLocalizer.ControlSettingsSuccessful

        button['state'] = DGG.NORMAL
        button['text'] = base.controlManager.getControlName(key)

        if hasattr(self, '_dialog') and self._dialog:
            self._dialog.destroy()
            self._dialog = None

        base.transitions.fadeScreen(0.5)
        self.show()

    def getActiveHotkeys(self):
        hotkeys = []
        for category in self.controls.values():
            for hotkey in category.values():
                hotkeys.append(hotkey)
        return hotkeys

    def applyChanges(self):
        if self.mario:
            for i, value in self.controls['mario'].items():
                if MARIO_KEYS[i].get() != value:
                    MARIO_KEYS[i].set(value)
            base.controlManager.reloadHotkeys()
            return

        for category in self.controls.keys():
            categoryInfo = self.controls.get(category)
            base.settings.updateSetting('keybinds', category, categoryInfo)

        base.controlManager.reloadHotkeys()
