""" Universal Settings Screen - drewcification 010321 """
import os
import webbrowser
from subprocess import call
from sys import platform

from direct.fsm.FSM import FSM

from otp.otpgui import OTPGUIUtils
from otp.speedchat import SpeedChat, SCColorScheme, SCStaticTextTerminal
from . import FileBrowser
from .SettingsGUI import *
from toontown.shtiker import ControlSettingsDialog, DisplaySettingsDialog
from toontown.toonbase.ToontownSettings import speedChatStyles
from toontown.toontowngui.AnimatedButton import AnimatedButton
from .ToontownScrolledFrame import ToontownScrolledFrame
from ..toonbase.ToonBaseGlobal import base

FRAME_POS = (0, 0, -0.066)
FRAME_WIDTH = 0.84
FRAME_HEIGHT = 0.64


class SettingsScreen(DirectFrame, FSM):
    settingsDecorationModel = loader.loadModel('phase_3/models/gui/ttoff_m_gui_opts_decor', allowInstance = True)
    settingsScrollbarModel = loader.loadModel('phase_3.5/models/gui/ttoff_m_gui_sbk_generic', allowInstance = True)
    settingsButtonsModel = loader.loadModel('phase_3/models/gui/ttoff_m_gui_opts_buttons', allowInstance = True)

    def __init__(self, inBook = False, book = None):
        """
        :param inBook: Specifies if the screen is being loaded from the book in order to override some things
        """
        DirectFrame.__init__(self)
        FSM.__init__(self, 'SettingsScreen')

        self.inBook = inBook
        self.gameOptions = []
        self.audioOptions = []
        self.videoOptions = []
        self.book = book

        self.fileBrowser = FileBrowser.FileBrowser(wantTransitions = inBook)

        self.displaySettings = None
        self.displaySettingsChanged = 0
        self.displaySettingsSize = (None, None)
        self.displaySettingsFullscreen = None
        self.displaySettingsEmbedded = None
        self.displaySettingsApi = None
        self.displaySettingsApiChanged = 0

        self.controlSettings = None

        self.createUI()
        self.request('Game')

    def createUI(self):
        if not self.inBook:
            # If it's not in the book, we need to add a background
            bookModel = loader.loadModel('phase_3.5/models/gui/stickerbook_gui')
            newUiModel = loader.loadModel('phase_3.5/models/gui/ttoff_m_gui_hud_actionBar')
            self.background = OnscreenImage(parent = self,
                                            scale = (2, 1, 1.5),
                                            image = bookModel.find('**/big_book'))

            base.transitions.fadeScreen(0.5)
            self.reparentTo(aspect2d, 8000)
            self.bookCloseButton = AnimatedButton(
                    image = (newUiModel.find('**/actionbar_sticker_open'), newUiModel.find('**/actionbar_sticker_rollover_close'),
                             newUiModel.find('**/actionbar_sticker_rollover_close')), relief = None, pos = (-0.16, 0, 0.16),
                    parent = base.a2dpBottomRight,
                    scale = 0.305, command = self.exit)
            bookModel.removeNode()
            newUiModel.removeNode()

        gui = loader.loadModel('phase_3.5/models/gui/fishingBook')

        # TODO: Move this to a nicer area like ToontownGlobals
        normalColor = (1, 1, 1, 1)
        clickColor = (0.8, 0.8, 0, 1)
        rolloverColor = (0.15, 0.82, 1.0, 1)
        disabledColor = (1.0, 0.98, 0.15, 1)

        # self.settingsBackground = OnscreenImage(parent = self, scale = (1.75, 1, 1.5), pos = (0, 0, -0.02),
        #                                        image = self.settingsDecorationModel.find('**/ttoff_settingsPage_bg'))
        self.titleBG = OnscreenImage(parent = self, pos = (0, 0, .64), scale = (0.6, 0, 0.155),
                                     image = self.settingsDecorationModel.find('**/ttoff_settingsPage_title'))

        self.gameTab = DirectButton(parent = self, relief = None, text = TTLocalizer.SettingsTabGame,
                                    text_scale = TTLocalizer.OPoptionsTab, text_align = TextNode.ACenter,
                                    text_pos = (0.125, 0.0, 0.0), image = gui.find('**/tabs/polySurface1'),
                                    image_pos = (0.55, 1, -0.91), image_hpr = (0, 0, -90),
                                    image_scale = (0.033, 0.033, 0.035), image_color = normalColor,
                                    image1_color = clickColor, image2_color = rolloverColor,
                                    image3_color = disabledColor,
                                    text_fg = Vec4(0.2, 0.1, 0, 1), command = lambda: self.request('Game'),
                                    pos = (-0.83, 0, 0.77))
        self.audioTab = DirectButton(parent = self, relief = None, text = TTLocalizer.SettingsTabAudio,
                                     text_scale = TTLocalizer.OPoptionsTab, text_align = TextNode.ACenter,
                                     text_pos = (0.125, 0.0, 0.0), image = gui.find('**/tabs/polySurface1'),
                                     image_pos = (0.55, 1, -0.91), image_hpr = (0, 0, -90),
                                     image_scale = (0.033, 0.033, 0.035), image_color = normalColor,
                                     image1_color = clickColor, image2_color = rolloverColor,
                                     image3_color = disabledColor,
                                     text_fg = Vec4(0.2, 0.1, 0, 1), command = lambda: self.request('Audio'),
                                     pos = (-0.36, 0, 0.77) if self.inBook else (-0.13, 0, 0.77))
        self.videoTab = DirectButton(parent = self, relief = None, text = TTLocalizer.SettingsTabVideo,
                                     text_scale = TTLocalizer.OPoptionsTab, text_align = TextNode.ACenter,
                                     text_pos = (0.125, 0.0, 0.0), image = gui.find('**/tabs/polySurface1'),
                                     image_pos = (0.55, 1, -0.91), image_hpr = (0, 0, -90),
                                     image_scale = (0.033, 0.033, 0.035), image_color = normalColor,
                                     image1_color = clickColor, image2_color = rolloverColor,
                                     image3_color = disabledColor,
                                     text_fg = Vec4(0.2, 0.1, 0, 1), command = lambda: self.request('Video'),
                                     pos = (0.11, 0, 0.77) if self.inBook else (0.57, 0, 0.77))
        if self.inBook:
            self.codesTab = DirectButton(parent = self, relief = None, text = TTLocalizer.SettingsTabCodes,
                                         text_scale = TTLocalizer.OPoptionsTab, text_align = TextNode.ACenter,
                                         text_pos = (0.125, 0.0, 0.0), image = gui.find('**/tabs/polySurface1'),
                                         image_pos = (0.55, 1, -0.91), image_hpr = (0, 0, -90),
                                         image_scale = (0.033, 0.033, 0.035), image_color = normalColor,
                                         image1_color = clickColor, image2_color = rolloverColor,
                                         image3_color = disabledColor,
                                         text_fg = Vec4(0.2, 0.1, 0, 1), command = lambda: self.request('Codes'),
                                         pos = (0.58, 0, 0.77))
        gui.removeNode()
        del gui

    def unload(self):
        """

        """
        pass

    def enterHidden(self):
        pass

    def exitHidden(self):
        pass

    def enterGame(self):
        """
        Create the Game page
        Contains social and misc options
        """
        self.gameTab['state'] = DGG.DISABLED
        title = OnscreenImage(parent = self, pos = (0, 0, .65), scale = (0.5, 0, 0.125),
                              image = self.settingsDecorationModel.find('**/title_game'))
        # Create the Scroll frame
        frame = ToontownScrolledFrame(parent = self,
                                      relief = None,
                                      itemMargin = (0.45, 0),
                                      useItemBoundsForPadding = False,
                                      itemPadding = 0.15,
                                      pos = FRAME_POS,
                                      width = FRAME_WIDTH,
                                      height = FRAME_HEIGHT,
                                      manageScrollBars = False,
                                      verticalScroll_frameColor = (0, 0, 0, 0),
                                      verticalScroll_manageButtons = False,
                                      verticalScroll_thumb_geom = (
                                          self.settingsScrollbarModel.find('**/scrollbar_normal'),
                                          self.settingsScrollbarModel.find('**/scrollbar_press'),
                                          self.settingsScrollbarModel.find('**/scrollbar_hover')),
                                      verticalScroll_thumb_geom_scale = OTPGUIUtils.getImageScale(151, 399, 0.15),
                                      verticalScroll_thumb_relief = None,
                                      verticalScroll_resizeThumb = False,
                                      verticalScroll_decButton_relief = None,
                                      verticalScroll_incButton_relief = None)

        self.gameOptions = [
            title,
            frame,
            ToggleOption(self, ClientSettings.AcceptingNewFriends),
            ToggleOption(self, ClientSettings.AcceptingNonFriendWhispers),
            ToggleOption(self, ClientSettings.GlobalChatPopups),
            DropdownOption(self, ClientSettings.LoginMessages),
            DropdownOption(self, ClientSettings.TeleportRequests),
            DropdownOption(self, ClientSettings.ScreenshotFormat),
            DropdownOption(self, ClientSettings.ChatFilterMode),
            ToggleOption(self, ClientSettings.SmoothThrowing),
            SettingsButton(self, TTLocalizer.ControlSettingsTitle,
                           text = TTLocalizer.SettingsKeyBinds,
                           command = self.__doKeymapSettings),
            SettingsButton(self, TTLocalizer.MarioControlSettingsTitle,
                           text = TTLocalizer.SettingsKeyBinds,
                           command = self.__doKeymapSettings, extraArgs = [True]),
            SettingsButton(self, TTLocalizer.SettingsRetro,
                           text = TTLocalizer.SettingsChangeSettings,
                           command = lambda: self.request('Retro')),
            SliderOption(self, ClientSettings.CameraSensitivity,
                         minimum = .1, maximum = 1, multiplier = 100),
            ToggleOption(self, ClientSettings.DoorInteraction),
            ToggleOption(self, ClientSettings.NPCInteraction),
            ToggleOption(self, ClientSettings.ActivityInteraction),
            ToggleOption(self, ClientSettings.CogInteraction),
            ToggleOption(self, ClientSettings.PropGeneratorCollisions),
            DropdownOption(self, ClientSettings.DefaultCameraMode),
            ToggleOption(self, ClientSettings.AllowServerPATScreens)
        ]
        if platform == 'win32':
            self.gameOptions.append(DropdownOption(self, ClientSettings.ScreenshotDirectory))

        if hasattr(base, 'localAvatar'):
            # If we are in-game, add the teleport greeting field setting
           # teleportGreetingDropdown = TeleportGreetingDropdown(self,
           #                                                     updateCommand = self.updateTeleportGreeting)
           # self.gameOptions.append(teleportGreetingDropdown)

            # If we are in-game, add the speedchat style option
            speedchatStyleHolder = DirectFrame(relief = None)
            self.speedChatStyleText = SpeedChat.SpeedChat(name = 'OptionsPageStyleText', structure = [2000])
            self.speedChatStyleText.reparentTo(speedchatStyleHolder)
            self.speedChatStyleText.setPos(0, 0, 0.03)
            self.speedChatStyleText.setScale(0.055)
            self.speedChatStyleText.enter()

            self.speedChatStyleLeftArrow = DirectButton(parent = speedchatStyleHolder, relief = None,
                                                        image = (self.settingsButtonsModel.find('**/arrow_l_normal'),
                                                                 self.settingsButtonsModel.find('**/arrow_l_click'),
                                                                 self.settingsButtonsModel.find('**/arrow_l_hover'),
                                                                 self.settingsButtonsModel.find('**/arrow_l_disabled')),
                                                        image3_color = Vec4(1, 1, 1, 0.5), scale = 0.08,
                                                        pos = (-0.2, 0, 0),
                                                        command = lambda: self.switchSpeedChatStyle(-1))
            self.speedChatStyleRightArrow = DirectButton(parent = speedchatStyleHolder, relief = None,
                                                         image = (self.settingsButtonsModel.find('**/arrow_r_normal'),
                                                                  self.settingsButtonsModel.find('**/arrow_r_click'),
                                                                  self.settingsButtonsModel.find('**/arrow_r_hover'),
                                                                  self.settingsButtonsModel.find(
                                                                          '**/arrow_r_disabled')),
                                                         image3_color = Vec4(1, 1, 1, 0.5), scale = 0.08,
                                                         pos = (0.2, 0, 0),
                                                         command = lambda: self.switchSpeedChatStyle(1))
            self.speedChatStyleIndex = base.localAvatar.getSpeedChatStyleIndex()
            self.updateSpeedChatStyle()
            speedChatStyleLabel = OnscreenText(parent = speedchatStyleHolder, align = TextNode.ALeft,
                                               text = TTLocalizer.OptionsPageSpeedChatStyleLabel,
                                               pos = (-1.1, -0.02), scale = 0.06, wordwrap = 20, mayChange = False)
            self.gameOptions.append(speedchatStyleHolder)
            exitBtn = SettingsButton(self, '',
                                     text = TTLocalizer.OptionsPageExitToontown,
                                     command = self.__handleExitShowWithConfirm)
            self.gameOptions.append(exitBtn)

        frame.addItems(*self.gameOptions[2:])

    def exitGame(self):
        for option in self.gameOptions[0:2]:
            option.destroy()
            del option
        self.gameOptions = []
        self.gameTab['state'] = DGG.NORMAL

    def enterAudio(self):
        self.audioTab['state'] = DGG.DISABLED
        title = OnscreenImage(parent = self, pos = (0, 0, .65), scale = (0.5, 0, 0.125),
                              image = self.settingsDecorationModel.find('**/title_audio'))
        # Create the Scroll frame
        # To increase the length, subtract from the third value in the canvasSize property.
        # Subtract 0.10 for each item
        # Always leave frame size the same
        frame = ToontownScrolledFrame(parent = self,
                                      relief = None,
                                      itemMargin = (0.45, 0),
                                      useItemBoundsForPadding = False,
                                      itemPadding = 0.15,
                                      pos = FRAME_POS,
                                      width = FRAME_WIDTH,
                                      height = FRAME_HEIGHT,
                                      manageScrollBars = False,
                                      verticalScroll_frameColor = (0, 0, 0, 0),
                                      verticalScroll_manageButtons = False,
                                      verticalScroll_thumb_geom = (
                                          self.settingsScrollbarModel.find('**/scrollbar_normal'),
                                          self.settingsScrollbarModel.find('**/scrollbar_press'),
                                          self.settingsScrollbarModel.find('**/scrollbar_hover')),
                                      verticalScroll_thumb_geom_scale = OTPGUIUtils.getImageScale(151, 399, 0.15),
                                      verticalScroll_thumb_relief = None,
                                      verticalScroll_resizeThumb = False,
                                      verticalScroll_decButton_relief = None,
                                      verticalScroll_incButton_relief = None)

        self.audioOptions = [
            title,
            frame,
            ToggleSlider(self, ClientSettings.VolumeMasterEnabled, ClientSettings.VolumeMaster, minimum = 0, maximum = 1, multiplier = 100, unit = '%'),
            ToggleSlider(self, ClientSettings.MusicEnabled, ClientSettings.MusicVolume, minimum = 0, maximum = 1, multiplier = 100, unit = '%'),
            ToggleSlider(self, ClientSettings.VolumeSFXEnabled, ClientSettings.VolumeSFX, minimum = 0, maximum = 1, multiplier = 100, unit = '%'),
            ToggleSlider(self, ClientSettings.VolumeDialogEnabled, ClientSettings.VolumeDialog, minimum = 0, maximum = 1, multiplier = 100, unit = '%'),
            ToggleSlider(self, ClientSettings.VolumeBattleEnabled, ClientSettings.VolumeBattle, minimum = 0, maximum = 1, multiplier = 100, unit = '%'),
            ToggleSlider(self, ClientSettings.VolumeEnvironmentEnabled, ClientSettings.VolumeEnvironment, minimum = 0, maximum = 1, multiplier = 100, unit = '%'),
            ToggleSlider(self, ClientSettings.VolumeStreetPropsEnabled, ClientSettings.VolumeStreetProps, minimum = 0, maximum = 1, multiplier = 100, unit = '%'),
            ToggleSlider(self, ClientSettings.VolumeGuiEnabled, ClientSettings.VolumeGui, minimum = 0, maximum = 1, multiplier = 100, unit = '%')
            #ToggleSlider(self, ClientSettings.VolumePropsEnabled, ClientSettings.VolumeProps, minimum = 0, maximum = 1, multiplier = 100, unit = '%'),
        ]

        # Text-To-Speech button
        try:
            if platform != "darwin":
                nullDevice = open(os.devnull, 'wb')
                if base.textToSpeechPath:
                    filePath = base.textToSpeechPath
                else:
                    filePath = base.defaultTextToSpeechPath
                call([filePath, '--version'], stdout = nullDevice)
                nullDevice.close()
            ttsButton = ToggleSlider(self, ClientSettings.TextToSpeechEnabled, ClientSettings.TextToSpeechVolume,
                                     minimum = 0, maximum = 1, multiplier = 100, unit = '%')
            self.audioOptions.append(ttsButton)
        except:
            ttsButton = SettingsButton(self, TTLocalizer.ExtraOptionsPageTextToSpeechNotInstalledLabel,
                                       text = TTLocalizer.ExtraOptionsPageGetEspeak,
                                       command = lambda: webbrowser.open(ToontownGlobals.TextToSpeechLink, new = 2))
            ttsSetPath = SettingsButton(self, TTLocalizer.ExtraOptionsPagePickEspeakDirectory,
                                        text = TTLocalizer.ExtraOptionsPageSetEspeakPath,
                                        command = self.__doBrowseForTextToSpeechFilePath)
            self.audioOptions.append(ttsButton)
            self.audioOptions.append(ttsSetPath)

        frame.addItems(*self.audioOptions[2:])

    def exitAudio(self):
        for option in self.audioOptions[0:2]:
            option.destroy()
            del option
        self.audioOptions = []
        self.audioTab['state'] = DGG.NORMAL

    def enterVideo(self):
        self.videoTab['state'] = DGG.DISABLED
        title = OnscreenImage(parent = self, pos = (0, 0, .65), scale = (0.5, 0, 0.125),
                              image = self.settingsDecorationModel.find('**/title_video'))
        # Create the Scroll frame
        frame = ToontownScrolledFrame(parent = self,
                                      relief = None,
                                      itemMargin = (0.45, 0),
                                      useItemBoundsForPadding = False,
                                      itemPadding = 0.15,
                                      pos = FRAME_POS,
                                      width = FRAME_WIDTH,
                                      height = FRAME_HEIGHT,
                                      manageScrollBars = False,
                                      verticalScroll_frameColor = (0, 0, 0, 0),
                                      verticalScroll_manageButtons = False,
                                      verticalScroll_thumb_geom = (
                                          self.settingsScrollbarModel.find('**/scrollbar_normal'),
                                          self.settingsScrollbarModel.find('**/scrollbar_press'),
                                          self.settingsScrollbarModel.find('**/scrollbar_hover')),
                                      verticalScroll_thumb_geom_scale = OTPGUIUtils.getImageScale(151, 399, 0.15),
                                      verticalScroll_thumb_relief = None,
                                      verticalScroll_resizeThumb = False,
                                      verticalScroll_decButton_relief = None,
                                      verticalScroll_incButton_relief = None)

        self.videoOptions = [
            title,
            frame,
            SettingsButton(self, TTLocalizer.SettingsResolutionSettings,
                           text = TTLocalizer.SettingsChangeSettings,
                           command = self.__doDisplaySettings),
            DropdownOption(self, ClientSettings.AntiAliasing),
            DropdownOption(self, ClientSettings.AnisotropicFiltering),
            DropdownOption(self, ClientSettings.AspectRatio),
            DropdownOption(self, ClientSettings.ReflectionQuality),
            SliderOption(self, ClientSettings.CameraFOV, minimum = 30, maximum = 120),
            ToggleOption(self, ClientSettings.AvatarFrustumCulling),
            ToggleOption(self, ClientSettings.AvatarLODs),
            ToggleOption(self, ClientSettings.GUIAnimations),
            DropdownOption(self, ClientSettings.FrameRateCap),
            ColorPickerOption(self, ClientSettings.ShtickerBookBackground,
                              includedSwatches = ToontownGlobals.BackgroundColors),
            SliderOption(self, ClientSettings.ShtickerBookScale, minimum = 0.9, maximum = 1.1, multiplier = 100, unit = '%'),
            SliderOption(self, ClientSettings.PropSpawnerGUIScale, minimum = 0.75, maximum = 1.0, multiplier = 100, unit = '%'),
            ToggleOption(self, ClientSettings.SmoothAnimations),
            SliderOption(self, ClientSettings.StreetMapOpacity, minimum = 0.25, maximum = 1.0, multiplier = 100, unit = '%'),
            ToggleOption(self, ClientSettings.VerticalSync),
            ToggleOption(self, ClientSettings.VisualizeCollisionGenerators)
        ]

        frame.addItems(*self.videoOptions[2:])

    def exitVideo(self):
        for option in self.videoOptions:
            option.destroy()
            del option
        self.videoOptions = []
        self.videoTab['state'] = DGG.NORMAL

    def enterCodes(self):
        self.codesTab['state'] = DGG.DISABLED
        self.title = OnscreenImage(parent = self, pos = (0, 0, .65), scale = OTPGUIUtils.getImageScale(2048, 512, 0.15),
                                   image = self.settingsDecorationModel.find('**/title_codes'))

        cdrGui = loader.loadModel('phase_3.5/models/gui/tt_m_gui_sbk_codeRedemptionGui')
        instructionGui = cdrGui.find('**/tt_t_gui_sbk_cdrPresent')
        flippyGui = cdrGui.find('**/tt_t_gui_sbk_cdrFlippy')
        codeBoxGui = cdrGui.find('**/tt_t_gui_sbk_cdrCodeBox')
        self.resultPanelSuccessGui = cdrGui.find('**/tt_t_gui_sbk_cdrResultPanel_success')
        self.resultPanelFailureGui = cdrGui.find('**/tt_t_gui_sbk_cdrResultPanel_failure')
        self.resultPanelErrorGui = cdrGui.find('**/tt_t_gui_sbk_cdrResultPanel_error')
        self.successSfx = base.loader.loadSfx('phase_3.5/audio/sfx/tt_s_gui_sbk_cdrSuccess.ogg')
        self.failureSfx = base.loader.loadSfx('phase_3.5/audio/sfx/tt_s_gui_sbk_cdrFailure.ogg')
        self.instructionPanel = DirectFrame(parent = self, relief = None, image = instructionGui, image_scale = 0.8,
                                            text = TTLocalizer.CdrInstructions,
                                            text_pos = TTLocalizer.OPCodesInstructionPanelTextPos,
                                            text_align = TextNode.ACenter,
                                            text_scale = TTLocalizer.OPCodesResultPanelTextScale,
                                            text_wordwrap = TTLocalizer.OPCodesInstructionPanelTextWordWrap,
                                            pos = (-0.429, 0, -0.05))
        self.codeBox = DirectFrame(parent = self, relief = None, image = codeBoxGui, pos = (0.433, 0, 0.35))
        self.flippyFrame = DirectFrame(parent = self, relief = None, image = flippyGui, pos = (0.44, 0, -0.353))
        self.codeInput = DirectEntry(parent = self.codeBox, relief = DGG.GROOVE, scale = 0.08, pos = (-0.33, 0, -0.006),
                                     borderWidth = (0.05, 0.05),
                                     frameColor = ((1, 1, 1, 1), (1, 1, 1, 1), (0.5, 0.5, 0.5, 0.5)),
                                     state = DGG.NORMAL,
                                     text_align = TextNode.ALeft, text_scale = TTLocalizer.OPCodesInputTextScale,
                                     width = 10.5, numLines = 1, focus = 0, backgroundFocus = 0, cursorKeys = 1,
                                     text_fg = (0, 0, 0, 1), suppressMouse = 1, autoCapitalize = 0,
                                     command = self.__submitCode, focusInCommand = self.toggleSpeedchat,
                                     focusInExtraArgs = [False], focusOutCommand = self.toggleSpeedchat,
                                     focusOutExtraArgs = [True])
        submitButtonGui = loader.loadModel('phase_3/models/gui/quit_button')
        self.submitButton = DirectButton(parent = self, relief = None, image = (submitButtonGui.find('**/QuitBtn_UP'),
                                                                                submitButtonGui.find('**/QuitBtn_DN'),
                                                                                submitButtonGui.find('**/QuitBtn_RLVR'),
                                                                                submitButtonGui.find('**/QuitBtn_UP')),
                                         image3_color = Vec4(0.5, 0.5, 0.5, 0.5), image_scale = 1.15,
                                         state = DGG.NORMAL, text = TTLocalizer.NameShopSubmitButton,
                                         text_scale = TTLocalizer.OPCodesSubmitTextScale, text_align = TextNode.ACenter,
                                         text_pos = TTLocalizer.OPCodesSubmitTextPos, text3_fg = (0.5, 0.5, 0.5, 0.75),
                                         textMayChange = 0, pos = (0.45, 0.0, 0.0896), command = self.__submitCode)
        self.resultPanel = DirectFrame(parent = self, relief = None, image = self.resultPanelSuccessGui, text = '',
                                       text_pos = TTLocalizer.OPCodesResultPanelTextPos, text_align = TextNode.ACenter,
                                       text_scale = TTLocalizer.OPCodesResultPanelTextScale,
                                       text_wordwrap = TTLocalizer.OPCodesResultPanelTextWordWrap,
                                       pos = (-0.42, 0, -0.0567))
        self.resultPanel.hide()
        closeButtonGui = loader.loadModel('phase_3/models/gui/dialog_box_buttons_gui')
        self.closeButton = DirectButton(parent = self.resultPanel, pos = (0.296, 0, -0.466), relief = None,
                                        state = DGG.NORMAL, image = (
            closeButtonGui.find('**/CloseBtn_UP'), closeButtonGui.find('**/CloseBtn_DN'),
            closeButtonGui.find('**/CloseBtn_Rllvr')), image_scale = (1, 1, 1), command = self.__hideResultPanel)
        closeButtonGui.removeNode()
        cdrGui.removeNode()
        submitButtonGui.removeNode()

        base.controlManager.addDisabledHotkey(ToontownGlobals.HotkeyMovement, ToontownGlobals.HotkeyLeft)
        base.controlManager.addDisabledHotkey(ToontownGlobals.HotkeyMovement, ToontownGlobals.HotkeyRight)
        self.__enableCodeEntry()
        self.accept('mouse1', self.toggleEntryFocus, extraArgs = [True])

    def toggleSpeedchat(self, state):
        if not state:
            localAvatar.chatMgr.setBackgroundFocus(False, True)
            base.controlManager.disableAlphaNumericHotkeys = True
        else:
            localAvatar.chatMgr.setBackgroundFocus(base.controlManager.getChatDisabled(), True)
            base.controlManager.disableAlphaNumericHotkeys = False

    def toggleEntryFocus(self, state):
        if state:
            self.codeInput['focus'] = 0
            self.codeInput.setFocus()
        self.toggleSpeedchat(not state)

    def __submitCode(self, input = None):
        if input == None:
            input = self.codeInput.get()
        if input == '':
            return
        messenger.send('wakeup')
        if hasattr(base, 'codeRedemptionMgr'):
            base.codeRedemptionMgr.redeemCode(input, self.__getCodeResult)
        self.codeInput.enterText('')
        self.__disableCodeEntry()

    def __getCodeResult(self, result, awardMgrResult):
        if hasattr(self, 'resultPanel') and self.resultPanel == None:
            return
        self.notify.debug('result = %s' % result)
        self.notify.debug('awardMgrResult = %s' % awardMgrResult)
        self.__enableCodeEntry()
        if result == 0:
            self.resultPanel['image'] = self.resultPanelSuccessGui
            self.resultPanel['text'] = TTLocalizer.CdrResultSuccess
        elif result == 1 or result == 3:
            self.resultPanel['image'] = self.resultPanelFailureGui
            self.resultPanel['text'] = TTLocalizer.CdrResultInvalidCode
        elif result == 2:
            self.resultPanel['image'] = self.resultPanelFailureGui
            self.resultPanel['text'] = TTLocalizer.CdrResultExpiredCode
        elif result == 4:
            self.resultPanel['image'] = self.resultPanelErrorGui
            if awardMgrResult == 0:
                self.resultPanel['text'] = TTLocalizer.CdrResultSuccess
            elif awardMgrResult == 1 or awardMgrResult == 2 or awardMgrResult == 15 or awardMgrResult == 16:
                self.resultPanel['text'] = TTLocalizer.CdrResultUnknownError
            elif awardMgrResult == 3 or awardMgrResult == 4:
                self.resultPanel['text'] = TTLocalizer.CdrResultMailboxFull
            elif awardMgrResult == 5 or awardMgrResult == 10:
                self.resultPanel['text'] = TTLocalizer.CdrResultAlreadyInMailbox
            elif awardMgrResult == 6 or awardMgrResult == 7 or awardMgrResult == 11:
                self.resultPanel['text'] = TTLocalizer.CdrResultAlreadyInQueue
            elif awardMgrResult == 8:
                self.resultPanel['text'] = TTLocalizer.CdrResultAlreadyInCloset
            elif awardMgrResult == 9:
                self.resultPanel['text'] = TTLocalizer.CdrResultAlreadyBeingWorn
            elif awardMgrResult == 12 or awardMgrResult == 13 or awardMgrResult == 14:
                self.resultPanel['text'] = TTLocalizer.CdrResultAlreadyReceived
        elif result == 5:
            self.resultPanel['text'] = TTLocalizer.CdrResultTooManyFails
            self.__disableCodeEntry()
        elif result == 6:
            self.resultPanel['text'] = TTLocalizer.CdrResultServiceUnavailable
            self.__disableCodeEntry()
        if result == 0:
            self.successSfx.play()
        else:
            self.failureSfx.play()
        self.resultPanel.show()

    def __hideResultPanel(self):
        self.resultPanel.hide()

    def __disableCodeEntry(self):
        self.codeInput['state'] = DGG.DISABLED
        self.submitButton['state'] = DGG.DISABLED

    def __enableCodeEntry(self):
        self.codeInput['state'] = DGG.NORMAL
        self.submitButton['state'] = DGG.NORMAL

    def exitCodes(self):
        self.title.destroy()
        self.title = None
        self.instructionPanel.destroy()
        self.instructionPanel = None
        self.codeBox.destroy()
        self.codeBox = None
        self.flippyFrame.destroy()
        self.flippyFrame = None
        self.codeInput.destroy()
        self.codeInput = None
        self.submitButton.destroy()
        self.submitButton = None
        self.resultPanel.destroy()
        self.resultPanel = None
        self.closeButton.destroy()
        self.closeButton = None
        base.loader.unloadSfx(self.successSfx)
        base.loader.unloadSfx(self.failureSfx)
        del self.successSfx
        del self.failureSfx

        self.toggleSpeedchat(True)
        base.controlManager.removeDisabledHotkey(ToontownGlobals.HotkeyMovement, ToontownGlobals.HotkeyLeft)
        base.controlManager.removeDisabledHotkey(ToontownGlobals.HotkeyMovement, ToontownGlobals.HotkeyRight)

        self.ignore('mouse1')

        self.codesTab['state'] = DGG.NORMAL

    def enterRetro(self):
        # Change the game tab to act as a back button
        self.gameTab['text'] = TTLocalizer.SettingsTabBack
        title = OnscreenImage(parent = self, pos = (0, 0, .65), scale = (0.5, 0, 0.125),
                              image = self.settingsDecorationModel.find('**/title_retro'))
        # Create the Scroll frame
        frame = ToontownScrolledFrame(parent = self,
                                      relief = None,
                                      itemMargin = (0.45, 0),
                                      useItemBoundsForPadding = False,
                                      itemPadding = 0.15,
                                      pos = FRAME_POS,
                                      width = FRAME_WIDTH,
                                      height = FRAME_HEIGHT,
                                      manageScrollBars = False,
                                      verticalScroll_frameColor = (0, 0, 0, 0),
                                      verticalScroll_manageButtons = False,
                                      verticalScroll_thumb_geom = (
                                          self.settingsScrollbarModel.find('**/scrollbar_normal'),
                                          self.settingsScrollbarModel.find('**/scrollbar_press'),
                                          self.settingsScrollbarModel.find('**/scrollbar_hover')),
                                      verticalScroll_thumb_geom_scale = OTPGUIUtils.getImageScale(151, 399, 0.15),
                                      verticalScroll_thumb_relief = None,
                                      verticalScroll_resizeThumb = False,
                                      verticalScroll_decButton_relief = None,
                                      verticalScroll_incButton_relief = None)

        self.retroOptions = [
            frame,
            title,
            ToggleOption(self, ClientSettings.BetaPlaygroundInterface, frame.getCanvas(), 'retro'),
            ToggleOption(self, ClientSettings.BetaPlaygroundMovement, frame.getCanvas(), 'retro'),
            ToggleOption(self, ClientSettings.CEOTableSquish, frame.getCanvas(), 'retro'),
            ToggleOption(self, ClientSettings.ClassicDogs, frame.getCanvas(), 'retro'),
            ToggleOption(self, ClientSettings.ClassicLoadingScreen, frame.getCanvas(), 'retro'),
            ToggleOption(self, ClientSettings.ClassicMakeAToon, frame.getCanvas(), 'retro'),
            ToggleOption(self, ClientSettings.ClassicNametags, frame.getCanvas(), 'retro'),
            ToggleOption(self, ClientSettings.ClassicChatBubbles, frame.getCanvas(), 'retro'),
            ToggleOption(self, ClientSettings.ClassicPickAToon, frame.getCanvas(), 'retro'),
            ToggleOption(self, ClientSettings.ClassicSFX, frame.getCanvas(), 'retro'),
            ToggleOption(self, ClientSettings.ClassicTrolleyGamePortraits, frame.getCanvas(), 'retro'),
            # ToggleOption(self, 'new-battle-interface', frame.getCanvas(), 'retro'),
            # ToggleOption(self, 'cog-health-bars', frame.getCanvas(), 'retro'),
            ToggleOption(self, ClientSettings.CogBattlePanels, frame.getCanvas(), 'retro'),
            ToggleOption(self, ClientSettings.EstateMusic, frame.getCanvas(), 'retro'),
            ToggleOption(self, ClientSettings.EstatePopsicleTreasures, frame.getCanvas(), 'retro'),
            ToggleOption(self, ClientSettings.NewRecordColor, frame.getCanvas(), 'retro'),
            ToggleOption(self, ClientSettings.NewSpeedchatPhrases, frame.getCanvas(), 'retro'),
            ToggleOption(self, ClientSettings.PhotoAlbumPage, frame.getCanvas(), 'retro'),
            ToggleOption(self, ClientSettings.NewStreetBattleMusic, frame.getCanvas(), 'retro'),
            ToggleOption(self, ClientSettings.PerPlaygroundTrolleyGagShops, frame.getCanvas(), 'retro'),
            ToggleOption(self, ClientSettings.UpdatedMap, frame.getCanvas(), 'retro'),
        ]

        frame.addItems(*self.retroOptions[2:])

        self.audioTab.hide()
        self.videoTab.hide()
        if hasattr(self, 'codesTab'):
            self.codesTab.hide()

    def exitRetro(self):
        self.gameTab['text'] = TTLocalizer.SettingsTabGame
        for option in self.retroOptions[0:2]:
            option.destroy()
            del option
        self.retroOptions = []
        self.audioTab.show()
        self.videoTab.show()
        if hasattr(self, 'codesTab'):
            self.codesTab.show()

    def exit(self):
        if not self.inBook:
            self.background.removeNode()
            del self.background
            base.transitions.noFade()
            self.bookCloseButton.destroy()
        if self.fileBrowser.browserCreated and not self.fileBrowser.browser.isHidden():
            self.fileBrowser.closeFileBrowser()
        self.destroy()

    ''' Speedchat Style Functions '''

    def switchSpeedChatStyle(self, offset):
        """
        Offsets and bounds the speedchat style index
        :param offset: 1 (right) or -1 (left)
        """
        self.speedChatStyleIndex += offset
        if self.speedChatStyleIndex < 0:
            self.speedChatStyleIndex = len(speedChatStyles) - 1
        elif self.speedChatStyleIndex > len(speedChatStyles) - 1:
            self.speedChatStyleIndex = 0
        self.updateSpeedChatStyle()

    def updateSpeedChatStyle(self):
        """
        Updates Speedchat Style button
        """
        nameKey, arrowColor, rolloverColor, frameColor = speedChatStyles[self.speedChatStyleIndex]
        newSCColorScheme = SCColorScheme.SCColorScheme(arrowColor = arrowColor, rolloverColor = rolloverColor,
                                                       frameColor = frameColor)
        self.speedChatStyleText.setColorScheme(newSCColorScheme)
        self.speedChatStyleText.clearMenu()
        colorName = SCStaticTextTerminal.SCStaticTextTerminal(nameKey)
        self.speedChatStyleText.append(colorName)
        self.speedChatStyleText.finalize()
        self.speedChatStyleText.setPos(0 - self.speedChatStyleText.getWidth() * 0.055 / 2, 0,
                                       self.speedChatStyleText.getPos()[2])

        base.localAvatar.b_setSpeedChatStyleIndex(self.speedChatStyleIndex)

    ''' TTS Functions '''

    def __doBrowseForTextToSpeechFilePath(self):
        messenger.send('wakeup')
        if not self.inBook:
            self.reparentTo(aspect2d)
        self.fileBrowser.openFileBrowser()
        self.fileBrowser.accept('selectionMade', self.__setTextToSpeechFilePath)

    def __setTextToSpeechFilePath(self, filePath = None):
        filePath = filePath + '\\command_line\\espeak'
        base.textToSpeechPath = filePath
        ClientSettings.TextToSpeechPath.set(filePath)
        self.request('Audio')
        if not self.inBook:
            self.reparentTo(aspect2d, 8000)
            base.transitions.fadeScreen(0.5)

    ''' Display Settings Functions '''

    def __doDisplaySettings(self):
        if self.displaySettings is None:
            self.displaySettings = DisplaySettingsDialog.DisplaySettingsDialog()
            self.displaySettings.load()
            self.accept(self.displaySettings.doneEvent, self.__doneDisplaySettings)
        self.displaySettings.enter(True, False, self.inBook)
        if ClientSettings.GUIAnimations.get():
            startPos = self.videoOptions[2].getPos(aspect2d)

            Parallel(
                    self.displaySettings.posInterval(0.2, Point3(0, 0, 0.1), startPos, blendType = 'easeOut'),
                    self.displaySettings.scaleInterval(0.2, Point3(1.0), Point3(0.01), blendType = 'easeOut'),
                    self.displaySettings.colorScaleInterval(0.2, VBase4(1.0), VBase4(1.0, 1.0, 1.0, 0.0))
            ).start()
        # Move the settings screen and close button behind the fade screen to prevent interaction
        if not self.inBook:
            self.reparentTo(aspect2d)
            # a2d is behind the fadeScreen
            self.bookCloseButton.reparentTo(base.a2dBottomRight)
        return

    def __doneDisplaySettings(self, anyChanged, apiChanged):
        if not self.inBook:
            self.reparentTo(aspect2d, 8000)
            # a2dp is in front of the fadeScreen
            self.bookCloseButton.reparentTo(base.a2dpBottomRight)
            base.transitions.fadeScreen(0.5)
        if anyChanged:
            properties = base.win.getProperties()
            self.displaySettingsChanged = 1
            self.displaySettingsSize = (properties.getXSize(), properties.getYSize())
            self.displaySettingsFullscreen = properties.getFullscreen()
            self.displaySettingsMode = self.displaySettings.displayMode
            self.displaySettingsApi = base.pipe.getInterfaceName()
            self.displaySettingsApiChanged = apiChanged
            self.writeDisplaySettings()

    def writeDisplaySettings(self, task = None):
        if not self.displaySettingsChanged:
            return
        self.notify.info(
                'writing new display settings %s, fullscreen %s, %s to SettingsFile.' % (self.displaySettingsSize,
                                                                                         self.displaySettingsFullscreen,
                                                                                         self.displaySettingsApi))
        ClientSettings.Resolution.set(self.displaySettingsSize)
        ClientSettings.DisplayMode.set(self.displaySettingsMode)
        self.displaySettingsChanged = 0

    ''' Keymap Functions '''

    def __doKeymapSettings(self, mario = False):
        if self.controlSettings is None:
            self.controlSettings = ControlSettingsDialog.ControlSettingsDialog()
            self.controlSettings.load()

        self.accept(self.controlSettings.doneEvent, self.__doneKeymapSettings)
        self.controlSettings.enter(inBook=self.inBook, mario=mario)

        # Move the settings screen and close button behind the fade screen to prevent interaction
        if not self.inBook:
            self.reparentTo(aspect2d)
            # a2d is behind the fadeScreen
            self.bookCloseButton.reparentTo(base.a2dBottomRight)
        if ClientSettings.GUIAnimations.get():
            startPos = self.gameOptions[7].getPos(aspect2d)

            Parallel(
                    self.controlSettings.posInterval(0.2, Point3(0, 0, 0.1), startPos, blendType = 'easeOut'),
                    self.controlSettings.scaleInterval(0.2, Point3(1.0), Point3(0.01), blendType = 'easeOut'),
                    self.controlSettings.colorScaleInterval(0.2, VBase4(1.0), VBase4(1.0, 1.0, 1.0, 0.0))
            ).start()

    def __doneKeymapSettings(self):
        if not self.inBook:
            self.reparentTo(aspect2d, 8000)
            # a2dp is in front of the fadeScreen
            self.bookCloseButton.reparentTo(base.a2dpBottomRight)
            base.transitions.fadeScreen(0.5)

    ''' Teleport Greeting Setting Functions '''

    def updateTeleportGreeting(self, teleportGreeting):
        base.localAvatar.b_setTeleportGreeting(teleportGreeting)

    def __handleExitShowWithConfirm(self):
        self.confirm = TTDialog.TTGlobalDialog(doneEvent = 'confirmDone', message = TTLocalizer.OptionsPageExitConfirm,
                                               style = TTDialog.TwoChoice)
        self.confirm.show()
        self.accept('confirmDone', self.__handleConfirm)
        self.book.doneStatus = {'mode': 'exit',
                                'exitTo': 'closeShard'
                                }

    def __handleConfirm(self):
        status = self.confirm.doneStatus
        self.ignore('confirmDone')
        self.confirm.cleanup()
        del self.confirm
        if status == 'ok':
            base.cr._userLoggingOut = True
            messenger.send(self.book.doneEvent)
