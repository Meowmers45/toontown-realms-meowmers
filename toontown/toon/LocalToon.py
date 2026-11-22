import platform
import time
from direct.gui import DirectGuiGlobals
from direct.showbase import ShowBaseGlobal
from direct.task import Task

from direct.distributed.ClockDelta import *
from direct.gui.DirectGui import *
from direct.interval.IntervalGlobal import *
from direct.showbase.PythonUtil import *
from panda3d.toontown import *

from otp.avatar import LocalAvatar
from otp.avatar import PositionExaminer
from otp.camera.CameraGlobals import CameraMode
from otp.camera.CameraOrbital import CameraOrbital
from otp.otpbase import OTPGlobals
from otp.otpbase.PythonUtil import deprecated
from otp.otpgui import OTPGUIUtils
from toontown.battle import Fanfare
from toontown.battle.BattleSounds import *
from toontown.catalog import CatalogNotifyDialog
from toontown.chat import TTTalkAssistant
from toontown.chat import ToontownChatManager
from toontown.effects.FilterManager import FilterManager
from toontown.estate import GardenGlobals
from toontown.hood import ZoneUtil
from toontown.parties import PartyGlobals
from toontown.quest import QuestParser
from toontown.shtiker import DisguisePage, CustomizeToonPage
from toontown.shtiker import EventsPage
from toontown.shtiker import FishPage
from toontown.shtiker import GardenPage
from toontown.shtiker import GolfPage
from toontown.shtiker import InventoryPage
from toontown.shtiker import KartPage
from toontown.shtiker import MapPage
from toontown.shtiker import NPCFriendPage
from toontown.shtiker import NewsPage
from toontown.shtiker import OptionsPage
from toontown.shtiker import PhotoAlbumPage
from toontown.shtiker import QuestPage
from toontown.shtiker import RoguesGallery
from toontown.shtiker import ServerPage
from toontown.shtiker import ShtikerBook
from toontown.shtiker import SuitPage
from toontown.shtiker import TIPPage
from toontown.shtiker import TrackPage
from toontown.shtiker import WordPage
from toontown.social import SocialMenu
from toontown.toon import ElevatorNotifier
from toontown.toonbase import HotkeySettings
from toontown.toonbase import ToontownGlobals, ClientSettings
from toontown.toonbase.ToontownGlobals import *
from toontown.toontowngui import CameraMenu, MagicMenu, NotificationGUI
from toontown.toontowngui import NewsPageButtonManager
from toontown.toontowngui.AnimatedButton import AnimatedButton
from . import DistributedToon
from . import LaffMeter
from . import Toon

WantNewsPage = False
AdjustmentForNewsButton = -0.275
ClaraBaseXPos = 0.116667
if (__debug__):
    import pdb
    import os
    if platform.system() == 'Windows' and os.environ['COMPUTERNAME'] == 'DESKTOP-6NC6GHJ':
        import clipboard


class LocalToon(DistributedToon.DistributedToon, LocalAvatar.LocalAvatar):
    neverDisable = 1
    piePowerSpeed = base.config.GetDouble('pie-power-speed', 0.2)
    piePowerExponent = base.config.GetDouble('pie-power-exponent', 0.75)
    piePositions = {
      # parented to base.a2dTopCenter
      # PIE BUTTON, PIE METER
      ToontownGlobals.PIE_BTN_POS_NORMAL: [(0, 0.1, -0.1), (0, 1, -0.2)],
      ToontownGlobals.PIE_BTN_POS_INSTANCE: [(0, 0.1, -0.225), (0, 1, -0.325)]
    }

    def __init__(self, cr):
        try:
            self.LocalToon_initialized
        except:
            self.LocalToon_initialized = 1
            self.marioMode = None
            self.numFlowers = 0
            self.maxFlowerBasket = 0
            DistributedToon.DistributedToon.__init__(self, cr)
            chatMgr = ToontownChatManager.ToontownChatManager(cr, self)
            talkAssistant = TTTalkAssistant.TTTalkAssistant()
            LocalAvatar.LocalAvatar.__init__(self, cr, chatMgr, talkAssistant)

            retroMode = ClientSettings.ClassicSFX.get()
            if retroMode:
                self.soundRun = base.loader.loadSfx('phase_3.5/audio/sfx/AV_footstep_runloop.ogg')
            else:
                self.soundRun = base.loader.loadSfx('phase_3.5/audio/sfx/AV_footstep_runloop_new.ogg')

            self.soundWalk = base.loader.loadSfx('phase_3.5/audio/sfx/AV_footstep_walkloop.ogg')
            self.useWaterSound = False
            self.soundWhisper = base.loader.loadSfx('phase_3.5/audio/sfx/GUI_whisper_3.ogg')
            self.soundPhoneRing = base.loader.loadSfx('phase_3.5/audio/sfx/telephone_ring.ogg')

            if retroMode:
                self.soundSystemMessage = base.loader.loadSfx('phase_3.5/audio/sfx/GUI_whisper_3.ogg')
            else:
                self.soundSystemMessage = base.loader.loadSfx('phase_3/audio/sfx/clock03.ogg')

            self.positionExaminer = PositionExaminer.PositionExaminer()
            newScale = oldScale = 0.8
            if WantNewsPage:
                newScale = oldScale * ToontownGlobals.NewsPageScaleAdjust

            actionBarMdl = loader.loadModel('phase_3.5/models/gui/ttoff_m_gui_hud_actionBar')
            self.bSocialMenu = AnimatedButton(
                    image=(actionBarMdl.find('**/actionbar_social_normal'),
                           actionBarMdl.find('**/actionbar_social_hover')),
                    relief=None, pos=(0.08, 0.0, 0.0),
                    parent=hidden,
                    scale=0.08,
                    text=('', '', TTLocalizer.FriendsListLabel, ''),
                    text_align = TextNode.ACenter,
                    text_scale = 0.6,
                    text_fg = (1.0, 1.0, 1.0, 1.0),
                    text_shadow = (0, 0, 0, 0.7),
                    text_pos = (0, 1),
                    text_font=ToontownGlobals.getInterfaceFont(),
                    command=self.sendSocialMenuEvent)
            actionBarMdl.removeNode()
            self.friendsListButtonActive = 0
            self.friendsListButtonObscured = 0
            self.moveFurnitureButtonObscured = 0
            self.clarabelleButtonObscured = 0
            self.__furnitureGui = None
            self.__clarabelleButton = None
            self.__clarabelleFlash = None
            self.furnitureManager = None
            self.furnitureDirector = None
            self.gotCatalogNotify = 0
            self.__catalogNotifyDialog = None
            self.accept('phaseComplete-5.5', self.loadPhase55Stuff)
            Toon.loadDialog()
            self.isIt = 0
            self.tunnelX = 0.0
            self.estate = None
            self.piePosType = ToontownGlobals.PIE_BTN_POS_NORMAL
            self.allowPies = 0
            self.__pieButton = None
            self.__piePowerMeter = None
            self.__piePowerMeterSequence = None
            self.__pieButtonType = None
            self.__pieButtonCount = None
            self.tossPieStart = None
            self.__presentingPie = 0
            self.__pieSequence = 0
            self.__featherBubble = None
            self.featherTrack = None
            self.wantBattles = base.config.GetBool('want-battles', 1)
            self.seeGhosts = base.config.GetBool('see-ghosts', 0)
            wantNameTagAvIds = base.config.GetBool('want-nametag-avids', 0)
            if wantNameTagAvIds:
                messenger.send('nameTagShowAvId', [])
                base.idTags = 1
            self.glitchX = 0
            self.glitchY = 0
            self.glitchZ = 0
            self.glitchCount = 0
            self.ticker = 0
            self.glitchOkay = 1
            self.tempGreySpacing = 0
            self.wantStatePrint = base.config.GetBool('want-statePrint', 0)
            self.__gardeningGui = None
            self.__gardeningGuiFake = None
            self.__shovelButton = None
            self.shovelRelatedDoId = 0
            self.shovelAbility = ''
            self.plantToWater = 0
            self.shovelButtonActiveCount = 0
            self.wateringCanButtonActiveCount = 0
            self.showingWateringCan = 0
            self.showingShovel = 0
            self.touchingPlantList = []
            self.inGardenAction = None
            self.guiConflict = 0
            self.lastElevatorLeft = 0
            self.elevatorNotifier = ElevatorNotifier.ElevatorNotifier()
            self.accept(OTPGlobals.AvatarFriendAddEvent, self.sbFriendAdd)
            self.accept(OTPGlobals.AvatarFriendUpdateEvent, self.sbFriendUpdate)
            self.accept(OTPGlobals.AvatarFriendRemoveEvent, self.sbFriendRemove)
            self.accept('playerBanned', self.handlePlayerBanned)
            self._zoneId = None
            self.systemMsgAckGuiDoneEvent = 'systemMsgAckGuiDoneEvent'
            self.accept(self.systemMsgAckGuiDoneEvent, self.hideSystemMsgAckGui)
            self.systemMsgAckGui = None
            self.createSystemMsgAckGui()
            if not hasattr(base.cr, 'lastLoggedIn'):
                base.cr.lastLoggedIn = self.cr.toontownTimeManager.convertStrToToontownTime('')
            self.setLastTimeReadNews(base.cr.lastLoggedIn)
            self.acceptingNewFriends = ClientSettings.AcceptingNewFriends.get() and base.config.GetBool('accepting-new-friends-default', True)
            self.acceptingNonFriendWhispers = ClientSettings.AcceptingNonFriendWhispers.get() and base.config.GetBool('accepting-non-friend-whispers-default', True)
            self.physControls.event.addAgainPattern('again%in')
            self.oldPos = None
            self.questMap = None
            self.prevToonIdx = 0
            self.laffMeter = None
            self.laffMeterTextColor = (0, 0, 0)
            self.debugLabel = None
            self.taskDebugLabel = None
            self.pythonVersion = '.'.join([str(id) for id in sys.version_info[:3]])
            self.teleporting = False
            self.waitLabel = None
            self.waitSequence = None
            self.newsButtonMgr = None
            self.actionBar = None
            self.notificationIval = None
            self.activeNotification = None
            self.lastActiveNotificationTime = 0.0
            self.lastExpiredActiveNotificationTime = 0.0
            self.notificationsQueue = []
            self.accept(HotkeySettings.ToggleDebugOverlay.getPressed(), self.thinkPos)
            self.accept(HotkeySettings.ToggleTaskMgrOverlay.getPressed(), self.thinkTask)
            self.accept(HotkeySettings.ToggleIvalOverlay.getPressed(), self.thinkIval)

            if __debug__ and platform.system() == 'Windows' and os.environ['COMPUTERNAME'] == 'DESKTOP-6NC6GHJ':
                self.accept('control-c', self.copyPosHpr)

            taskMgr.doMethodLater(10, self.__autoTimeSync, self.uniqueName('autoTimeSync'))

    def cleanupWaitLabel(self):
        if self.waitLabel:
            self.waitLabel.destroy()
        if self.waitSequence:
            self.waitSequence.pause()

        self.waitLabel = None
        self.waitSequence = None
        taskMgr.remove('waitLabel-task')

    def setLastExpiredActiveNotificationTime(self):
        self.lastExpiredActiveNotificationTime = time.time()

    def playNotificationIval(self, notification):

        def setBarVal(value):
            notification.timeActiveBar['value'] = value

        wantSfx = False
        if int(time.time()) - self.lastExpiredActiveNotificationTime >= 2.0:
            wantSfx = True

        notification.reparentTo(self.actionBar)
        notification.setPos(-.8, 0.0, 0.08)
        notification.setBin('gui-popup', 0)
        self.activeNotification = notification
        self.notificationIval = Sequence(Func(notification.show))
        if ClientSettings.GUIAnimations.get():
            if wantSfx:
                self.notificationIval.append(
                    Parallel(
                        Sequence(Wait(0.3), Func(base.playSfx, self.soundSystemMessage)),
                        OTPGUIUtils.Animations.slideUp(notification, finalZ = 0.08, startZ = -0.2, intensity = 0.4)
                    )
                )
            else:
                self.notificationIval.append(OTPGUIUtils.Animations.slideUp(notification, finalZ = 0.08, startZ = -0.2, intensity = 0.4))
        else:
            if wantSfx:
                self.notificationIval.append(Func(base.playSfx, self.soundSystemMessage))
        self.notificationIval.append(LerpFunctionInterval(setBarVal, fromData = 100, toData = 0, duration = 5.0))
        if ClientSettings.GUIAnimations.get():
            self.notificationIval.append(Parallel(
                    notification.posInterval(0.5, pos = (-.8, 0.0, -0.2), blendType = 'easeIn'),
                    LerpColorScaleInterval(notification, 0.5, Vec4(1, 1, 1, 0), Vec4(1)))
            )
        self.notificationIval.append(Wait(0.3))
        self.notificationIval.append(Func(self.notifications.addNotificationToScrolledFrame, notification))
        self.notificationIval.append(Func(self.setLastExpiredActiveNotificationTime))
        self.notificationIval.append(Func(self.processQueuedNotifications))
        self.notificationIval.start()
        self.lastActiveNotificationTime = time.time()

    def handleNotificationDismiss(self, notification):
        if notification == self.activeNotification:
            self.notificationIval.pause()
            self.notificationIval = None
            self.activeNotification = None
            self.setLastExpiredActiveNotificationTime()

    def processQueuedNotifications(self):
        if not hasattr(self, 'activeNotification') or self.activeNotification or self.actionBar.isHidden() or not self.tutorialAck:
            return

        if self.notificationsQueue:
            nextNotification = self.notificationsQueue[0]
            self.notificationsQueue.pop(0)
            if not self.notifications.isActive():
                self.playNotificationIval(nextNotification)
            else:
                self.notifications.addNotificationToScrolledFrame(nextNotification)
                self.processQueuedNotifications()

    def sendNotification(self, title, body, icon, id, subId = '', allowDuplicateIds = True, persistent = True, dismissButton2Text = TTLocalizer.NotificationDismiss, dismissButton2Action = None,
                         button2Text = None, button2Action = None):
        if persistent:
            notification = self.notifications.createNotification(
                title,
                body,
                icon,
                id,
                subId,
                allowDuplicateIds,
                dismissButton2Text,
                dismissButton2Action,
                button2Text,
                button2Action)
            if not self.tutorialAck or self.actionBar.isHidden() or self.notificationIval and self.notificationIval.isPlaying():
                notification.hide()
                self.notificationsQueue.append(notification)
            elif self.notifications.isActive():
                self.notifications.addNotificationToScrolledFrame(notification)
            else:
                self.playNotificationIval(notification)

    def wantLegacyLifter(self):
        return True

    def startGlitchKiller(self):
        taskMgr.remove(self.uniqueName('glitchKiller'))
        taskMgr.add(self.glitchKiller, self.uniqueName('glitchKiller'))
        self.glitchOkay = 1

    def pauseGlitchKiller(self):
        self.tempGreySpacing = 1

    def unpauseGlitchKiller(self):
        self.tempGreySpacing = 0

    def stopGlitchKiller(self):
        taskMgr.remove(self.uniqueName('glitchKiller'))
        self.glitchOkay = 1

    def glitchKiller(self, taskFooler = 0):
        if base.greySpacing or self.tempGreySpacing:
            return Task.cont
        self.ticker += 1
        if not self.physControls.lifter.hasContact() and not self.glitchOkay:
            self.glitchCount += 1
        else:
            self.glitchX = self.getX()
            self.glitchY = self.getY()
            self.glitchZ = self.getZ()
            self.glitchCount = 0
            if self.physControls.lifter.hasContact():
                self.glitchOkay = 0
        if hasattr(self, 'physControls'):
            if self.ticker >= 10:
                self.ticker = 0
        if self.glitchCount >= 7:
            self.notify.warning('Invalid position! Resetting position!')
            self.setX(self.glitchX - 1 * (self.getX() - self.glitchX))
            self.setY(self.glitchY - 1 * (self.getY() - self.glitchY))
            self.glitchCount = 0
        return Task.cont

    def announceGenerate(self):
        self.startLookAround()
        if base.wantNametags:
            self.nametag.manage(base.marginManager)
        DistributedToon.DistributedToon.announceGenerate(self)

    def toggleMarioMode(self):
        if self.marioMode is not None:
            self.stopMarioMode()
            return 'Mario mode off.'

        from toontown.mario.MarioMode import MarioMode, MarioUnavailable
        try:
            self.marioMode = MarioMode(self)
        except MarioUnavailable as exc:
            return str(exc)
        return 'Mario mode on. Change your keys in Settings > Game > Mario Controls.'

    def stopMarioMode(self):
        if self.marioMode is not None:
            mode, self.marioMode = self.marioMode, None
            mode.close()

    def disable(self):
        self.stopMarioMode()
        self.laffMeter.destroy()
        del self.laffMeter
        self.questMap.destroy()
        self.questMap = None
        self.newsButtonMgr.request('Off')
        self.book.unload()
        del self.optionsPage
        del self.serverPage
        del self.mapPage
        del self.invPage
        del self.questPage
        del self.suitPage
        del self.roguesPage
        del self.sosPage
        del self.disguisePage
        del self.fishPage
        del self.gardenPage
        del self.trackPage
        if hasattr(self, 'wordPage') and self.wordPage:
            del self.wordPage
        if hasattr(self, 'customizeToonPage') and self.customizeToonPage:
            del self.customizeToonPage
        del self.book
        if self.systemMsgAckGui:
            self.systemMsgAckGui.cleanup()
            self.systemMsgAckGui = None
        if base.wantKarts:
            if hasattr(self, 'kartPage'):
                del self.kartPage
        if base.wantNametags:
            self.nametag.unmanage(base.marginManager)
        taskMgr.removeTasksMatching('*ioorrd234*')

        # Unload the Camera Menu
        if self.cameraMenu:
            self.cameraMenu.unload()
            self.cameraMenu = None
        # Unload the Magic Menu
        if self.magicMenu:
            self.magicMenu.unload()
            self.magicMenu = None
        # Destroy the Notifications GUI
        if self.notifications:
            self.notifications.destroy()
            self.notifications = None
        del self.activeNotification
        del self.notificationsQueue

        self.ignoreAll()
        taskMgr.remove(self.uniqueName('autoTimeSync'))
        self.stopDebug()
        self.stopTaskDebug()
        DistributedToon.DistributedToon.disable(self)

    def disableBodyCollisions(self):
        pass

    def delete(self):
        try:
            self.LocalToon_deleted
        except:
            self.LocalToon_deleted = 1
            self.stopMarioMode()
            Toon.unloadDialog()
            QuestParser.clear()
            DistributedToon.DistributedToon.delete(self)
            LocalAvatar.LocalAvatar.delete(self)
            self.bSocialMenu.destroy()
            del self.bSocialMenu
            if self.__pieButton:
                self.__pieButton.destroy()
                self.__pieButton = None
            if self.__piePowerMeter:
                self.__piePowerMeter.destroy()
                self.__piePowerMeter = None
            taskMgr.remove('unlockGardenButtons')
            taskMgr.remove('lerpFurnitureButton')
            if self.__furnitureGui:
                self.__furnitureGui.destroy()
            del self.__furnitureGui
            if self.__gardeningGui:
                self.__gardeningGui.destroy()
            del self.__gardeningGui
            if self.__gardeningGuiFake:
                self.__gardeningGuiFake.destroy()
            del self.__gardeningGuiFake
            if self.__clarabelleButton:
                self.__clarabelleButton.destroy()
            del self.__clarabelleButton
            if self.__clarabelleFlash:
                self.__clarabelleFlash.finish()
            del self.__clarabelleFlash
            if self.__catalogNotifyDialog:
                self.__catalogNotifyDialog.cleanup()
            del self.__catalogNotifyDialog

        return

    def initInterface(self):
        self.newsButtonMgr = NewsPageButtonManager.NewsPageButtonManager()
        self.newsButtonMgr.request('Hidden')

        self.book = ShtikerBook.ShtikerBook('bookDone')
        self.book.load()
        self.book.hideButton()

        self.optionsPage = OptionsPage.OptionsPage()
        self.optionsPage.load()
        self.book.addPage(self.optionsPage, pageName=TTLocalizer.OptionsPageTitle)

        self.serverPage = ServerPage.ServerPage()
        self.serverPage.load()
        self.book.addPage(self.serverPage, pageName=TTLocalizer.ServerPageTitle)

        self.mapPage = MapPage.MapPage()
        self.mapPage.load()
        self.book.addPage(self.mapPage, pageName=TTLocalizer.MapPageTitle)

        self.invPage = InventoryPage.InventoryPage()
        self.invPage.load()
        self.book.addPage(self.invPage, pageName=TTLocalizer.InventoryPageTitle)

        self.questPage = QuestPage.QuestPage()
        self.questPage.load()
        self.book.addPage(self.questPage, pageName=TTLocalizer.QuestPageToonTasks)
        self.questPage.updatePage()  # For the street maps

        self.trackPage = TrackPage.TrackPage()
        self.trackPage.load()
        self.book.addPage(self.trackPage, pageName=TTLocalizer.TrackPageShortTitle)

        self.suitPage = SuitPage.SuitPage()
        self.suitPage.load()
        self.book.addPage(self.suitPage, pageName=TTLocalizer.SuitPageTitle)

        self.fishPage = FishPage.FishPage()
        self.fishPage.setAvatar(self)
        self.fishPage.load()
        self.book.addPage(self.fishPage, pageName=TTLocalizer.FishPageTitle)

        if base.wantKarts:
            self.addKartPage()

        if self.disguisePageFlag:
            self.loadDisguisePages()

        if self.sosPageFlag:
            self.loadSosPages()

        if self.gardenStarted:
            self.loadGardenPages()

        self.addGolfPage()

        self.addEventsPage()

        if ClientSettings.PhotoAlbumPage.get():
            self.photoAlbumPage = PhotoAlbumPage.PhotoAlbumPage()
            self.photoAlbumPage.load()
            self.book.addPage(self.photoAlbumPage, pageName=TTLocalizer.PhotoPageTitle)

        #self.addNewsPage()

        if not base.cr.legitMode:
            self.wordPage = WordPage.WordPage()
            self.wordPage.load()
            self.book.addPage(self.wordPage, pageName=TTLocalizer.SpellbookPageTitle)

            self.customizeToonPage = CustomizeToonPage.CustomizeToonPage()
            self.customizeToonPage.load()
            self.book.addPage(self.customizeToonPage, pageName = TTLocalizer.CustomizeToonPageTitle)

        self.book.setPage(self.mapPage, enterPage=False)

        self.laffMeter = LaffMeter.LaffMeter(self.style, self.hp, self.maxHp)
        self.laffMeter.setAvatar(self)
        self.laffMeter.setScale(0.075)
        self.laffMeter.reparentTo(base.a2dBottomLeft)
        if self.style.getAnimal() == 'monkey':
            self.laffMeter.setPos(0.153, 0.0, 0.13)
        else:
            self.laffMeter.setPos(0.133, 0.0, 0.13)
        self.laffMeter.stop()

        from toontown.quest import QuestMap
        self.questMap = QuestMap.QuestMap(self)
        self.questMap.stop()

        self.accept(HotkeySettings.Action.getPressed(), self.__beginTossPie)
        self.accept(HotkeySettings.Action.getReleased(), self.__endTossPie)
        self.accept('pieHit', self.__pieHit)
        self.accept('interrupt-pie', self.interruptPie)
        self.accept('featherTouch', self.__featherTouch)
        self.accept('InputState-jump', self.__toonMoved)
        self.accept('InputState-forward', self.__toonMoved)
        self.accept('InputState-reverse', self.__toonMoved)
        self.accept('InputState-turnLeft', self.__toonMoved)
        self.accept('InputState-turnRight', self.__toonMoved)
        self.accept('InputState-slide', self.__toonMoved)
        QuestParser.init()

        # The "Camera Menu", and interface you can open up to change your camera.
        self.cameraMenu = CameraMenu.CameraMenu()
        self.cameraMenu.load()

        # The "Magic Menu", an interface you can open up to do various things with
        self.magicMenu = MagicMenu.MagicMenu()
        self.magicMenu.load()

        self.notifications = NotificationGUI.NotificationGUI()

        actionBarMdl = loader.loadModel('phase_3.5/models/gui/ttoff_m_gui_hud_actionBar')
        self.actionBar = base.a2dBottomRight.attachNewNode('actionbar')
        bg = actionBarMdl.find('**/actionbar_bg')
        bg.setScale(0.82, 1, 0.1)
        bg.setAlphaScale(0.9)
        bg.reparentTo(self.actionBar)
        self.actionBar.setPos(-0.41, 0, 0.05)
        self.actionBar.hide()

        self.bSocialMenu.reparentTo(self.actionBar)

        self.magicMenuButton = AnimatedButton(
                image = (actionBarMdl.find('**/actionbar_magic_normal'),
                         actionBarMdl.find('**/actionbar_magic_hover'),
                         actionBarMdl.find('**/actionbar_magic_hover'),
                         actionBarMdl.find('**/actionbar_magic_disabled'),
                         ),
                scale = 0.08, command = self.toggleMagicMenu, parent = self.actionBar,
                pos = (-0.16, 0, 0.0),
                text=('', '', TTLocalizer.ActionBarMagicMenu, ''),
                text_align = TextNode.ACenter,
                text_scale = 0.6,
                text_fg = (1.0, 1.0, 1.0, 1.0),
                text_shadow = (0, 0, 0, 0.7),
                text_pos = (0, 1),
                textMayChange = 0
                )

        self.partyButton = AnimatedButton(
                image = (actionBarMdl.find('**/actionbar_party_normal'),
                         actionBarMdl.find('**/actionbar_party_hover')),
                scale = 0.08, command = self.magicMenu.handleButton,
                extraArgs = [ToontownGlobals.MagicMenuBossParty],
                parent = self.actionBar,
                pos = (-0.08, 0, 0.0),
                text=('', '', TTLocalizer.ActionBarParty, ''),
                text_align = TextNode.ACenter,
                text_scale = 0.6,
                text_fg = (1.0, 1.0, 1.0, 1.0),
                text_shadow = (0, 0, 0, 0.7),
                text_pos = (0, 1),
                textMayChange = 0)

        self.notificationsButton = AnimatedButton(
                image = (actionBarMdl.find('**/actionbar_notifications_normal'),
                         actionBarMdl.find('**/actionbar_notifications_hover')),
                scale = 0.08, command = self.toggleNotifications, parent = self.actionBar,
                pos = (0.0, 0, 0.0),
                text=('', '', TTLocalizer.ActionBarNotifications, ''),
                text_align = TextNode.ACenter,
                text_scale = 0.6,
                text_fg = (1.0, 1.0, 1.0, 1.0),
                text_shadow = (0, 0, 0, 0.7),
                text_pos = (0, 1),
                textMayChange = 0)

        self.mapButton = AnimatedButton(
                image = (actionBarMdl.find('**/actionbar_map_normal'),
                         actionBarMdl.find('**/actionbar_map_hover'),
                         actionBarMdl.find('**/actionbar_map_hover'),
                         actionBarMdl.find('**/actionbar_map_disabled')
                         ),
                scale = 0.08, parent = self.actionBar,
                pos = (-0.24, 0, 0.0),
                text=('', '', TTLocalizer.ActionBarMap, ''),
                text_align = TextNode.ACenter,
                text_scale = 0.6,
                text_fg = (1.0, 1.0, 1.0, 1.0),
                text_shadow = (0, 0, 0, 0.7),
                text_pos = (0, 1),
                textMayChange = 0,
                command = self.questMap.show,
                state = DirectGuiGlobals.DISABLED
        )

        self.cameraButton = AnimatedButton(
                image = (actionBarMdl.find('**/actionbar_camera_normal'),
                         actionBarMdl.find('**/actionbar_camera_hover')),
                scale = 0.08, command = self.toggleCameraMenu, parent = self.actionBar,
                pos = (-0.33, 0, 0.0),
                text=('', '', TTLocalizer.ActionBarCamera, ''),
                text_align = TextNode.ACenter,
                text_scale = 0.6,
                text_fg = (1.0, 1.0, 1.0, 1.0),
                text_shadow = (0, 0, 0, 0.7),
                text_pos = (0, 1))

        actionBarMdl.removeNode()

        self.cameraMenu.reparentTo(self.actionBar)
        self.cameraMenu.setPos(-0.33, 0.0, 0.0)

        self.magicMenu.reparentTo(self.actionBar)
        self.magicMenu.setPos(-0.16, 0.0, 0.0)

        self.notifications.reparentTo(self.actionBar)
        self.notifications.setPos(0.0, 0.0, 0.0)

    def sendSocialMenuEvent(self):
        if not self.tutorialAck:
            return
        super().sendSocialMenuEvent()
        sm = SocialMenu.getGlobalSocialMenu()
        sm.setX(0.065)
        if sm:
            sm.reparentTo(self.actionBar)
            OTPGUIUtils.Animations.slideUp(sm, finalZ = 0.7, startZ = 0).start()

    def showActionBar(self):
        if self.actionBar:
            self.actionBar.show()

            self.book.bookOpenButton.wrtReparentTo(self.actionBar)

            self.processQueuedNotifications()

    def hideActionBar(self):
        if self.actionBar:
            self.actionBar.hide()

            if self.activeNotification and int(time.time() - self.lastActiveNotificationTime) <= 0.5:
                if self.notificationIval.isPlaying():
                    self.notificationIval.pause()
                    self.notificationIval = None
                self.activeNotification.hide()
                self.notificationsQueue.insert(0, self.activeNotification)
                self.activeNotification = None

    def __bookHoverOn(self, e):
        self.removeTask('hideBookHover')
        if not base.cr.legitMode:
            Sequence(
                    Func(self.magicMenuButton.reparentTo, base.a2dBottomRight),
                    LerpPosInterval(self.magicMenuButton, 0.25, Point3(-0.1, 0, 0.4),
                                    blendType = 'easeOut'),
                    name="magicMenuButtonAnim"
            ).start()

    def __bookHoverOffEvent(self, e):
        self.doMethodLater(2, self.__bookHoverOff, 'hideBookHover')

    def __bookHoverOff(self, task = None):
        if not base.cr.legitMode:
            Sequence(
                    LerpPosInterval(self.magicMenuButton, 0.25, Point3(0.2, 0, 0.4),
                                    blendType = 'easeIn'),
                    Func(self.magicMenuButton.reparentTo, base.a2dBottomRight),
                    name="magicMenuButtonAnim"
            ).start()

    def changeButtonTextures(self):
        # todo: implement classic mode UI stuff
        return
        friendsTexture = ('phase_3.5/maps/gamegui_palette_4alla_4.png')
        self.book.resetButtonTextures()
        if ZoneUtil.isBetaPlaygroundZone(self.zoneId) and ClientSettings.BetaPlaygroundInterface.get():
            self.book.changeButtonTextures()
            friendsTexture = ('phase_3.5/maps/gamegui_palette_4alla_7.png')

        friendsGui = loader.loadModel('phase_3.5/models/gui/friendslist_gui')
        texture = loader.loadTexture(friendsTexture)
        newImageTextures = []
        for index, nodeName in enumerate(['Closed', 'Rollover']):
            imageNode = friendsGui.find('**/FriendsBox_' + nodeName)
            imageNode.setTexture(texture, 1)
            newImageTextures.append(imageNode)
        self.bSocialMenu['image'] = newImageTextures
        del friendsGui
        del texture

    def acceptOnscreenHooks(self):
        # Magic Menu
        if not base.cr.legitMode:
            self.accept(HotkeySettings.ToggleMagicMenu.getPressed(), self.toggleMagicMenu)
            if not self.kart:
                self.magicMenu.exitDisabledMode()

    def ignoreOnscreenHooks(self):
        # Magic Menu
        if not self.kart and not base.cr.legitMode:
            self.ignore(HotkeySettings.ToggleMagicMenu.getPressed())
            self.magicMenu.enterDisabledMode()

    def startupKart(self):
        self.kartActive = not self.kartActive
        self.d_requestKart(self.kartActive)

    def d_requestKart(self, active):
        self.sendUpdate('requestKart', [active])

    if base.wantKarts:

        def addKartPage(self):
            if self.hasKart():
                if hasattr(self, 'kartPage') and self.kartPage != None:
                    return
                if not launcher.getPhaseComplete(6):
                    self.acceptOnce('phaseComplete-6', self.addKartPage)
                    return
                self.kartPage = KartPage.KartPage()
                self.kartPage.setAvatar(self)
                self.kartPage.load()
                self.book.addPage(self.kartPage, pageName=TTLocalizer.KartPageTitle)
            return

    def toggleCameraMenu(self):
        # What was that? Sorry, I dozed off there for a second. I'm awake now.
        messenger.send('wakeup')
        if not self.tutorialAck:
            return
        if self.magicMenu.isEntered:
            self.magicMenu.exit()
        if self.cameraMenu.isEntered:
            self.cameraMenu.exit()
        # TODO: Should we remove the dumb "GetTransitioning" thing later? I only added this because I didn't know how FSMs worked back then...
        elif self.getTransitioning():
            return
        elif hasattr(base.cr, 'episodeManager') and base.cr.episodeManager.getEpisode():
            return
        else:
            self.sendHideSocialMenuEvent()
            self.notifications.exit()
            self.cameraMenu.enter()

    def toggleMagicMenu(self):
        # What was that? Sorry, I dozed off there for a second. I'm awake now.
        messenger.send('wakeup')
        if not self.tutorialAck:
            return
        if self.cameraMenu.isEntered:
            self.cameraMenu.exit()
        if self.magicMenu.isEntered:
            self.magicMenu.exit()
        elif self.kart:
            self.magicMenu.handleActionButton()
        # TODO: Should we remove the dumb "GetTransitioning" thing later? I only added this because I didn't know how FSMs worked back then...
        elif self.getTransitioning():
            return
        elif self.magicMenu.isDisabledMode():
            return
        elif self.getLocked():
            self.displayMessage(TTLocalizer.TeleportGUIRejectLocked)
        elif base.cr.legitMode:
            return
        elif hasattr(base.cr, 'episodeManager') and base.cr.episodeManager.getEpisode():
            return
        else:
            self.sendHideSocialMenuEvent()
            self.notifications.exit()
            self.magicMenu.enter()

    def toggleNotifications(self):
        messenger.send('wakeup')

        if not self.tutorialAck:
            pass
        elif not self.notifications.isActive():
            if self.activeNotification:
                if self.notificationIval:
                    self.notificationIval.pause()
                    self.notificationIval = None
                self.notifications.addNotificationToScrolledFrame(self.activeNotification)
            self.sendHideSocialMenuEvent()
            self.magicMenu.exit()
            self.cameraMenu.exit()
            self.notifications.enter()
            self.processQueuedNotifications()
        else:
            self.notifications.exit()

    def openTeleportGUI(self):
        # What was that? Sorry, I dozed off there for a second. I'm awake now.
        messenger.send('wakeup')

        # Grab the teleport interface from the Magic Menu. If it doesn't exist, we can't do anything.
        teleportInterface = self.magicMenu.getTeleportInterface()
        if not teleportInterface:
            return

        if teleportInterface.isEntered == 1:
            return
        elif self.magicMenu.isDisabledMode():
            return
        elif not self.magicMenu.isInvalidMode():
            return
        # TODO: Should we remove the dumb "GetTransitioning" thing later? I only added this because I didn't know how FSMs worked back then...
        elif self.getTransitioning():
            return
        elif self.getLocked():
            self.displayMessage(TTLocalizer.TeleportGUIRejectLocked)
        elif self.getAccessLevel() == OTPGlobals.AccessLevelName2Int['NO_ACCESS']:
            self.displayMessage(TTLocalizer.TeleportGUIRejectAccess)
        elif base.cr.legitMode:
            return
        elif hasattr(base.cr, 'tutorialManager') and base.cr.tutorialManager.getActive():
            return
        elif hasattr(base.cr, 'episodeManager') and base.cr.episodeManager.getEpisode():
            return
        else:
            teleportInterface.enter(ToontownGlobals.TeleportInterfaceModeNormal)

    def openSavedDNAGUI(self, dna, deleteMode = 0):
        # What was that? Sorry, I dozed off there for a second. I'm awake now.
        messenger.send('wakeup')

        # Grab the saved DNA interface from the Magic Menu. If it doesn't exist, we can't do anything.
        savedDNAInterface = self.magicMenu.getSavedDNAInterface()
        if not savedDNAInterface:
            return

        if savedDNAInterface.isEntered == 1:
            return
        # TODO: Should we remove the dumb "GetTransitioning" thing later? I only added this because I didn't know how FSMs worked back then...
        elif self.getTransitioning():
            return
        elif self.magicMenu.isDisabledMode():
            return
        elif not self.magicMenu.isInvalidMode():
            return
        elif self.getLocked():
            self.displayMessage(TTLocalizer.SavedDNAGUIRejectLocked)
        elif self.getAccessLevel() == OTPGlobals.AccessLevelName2Int['NO_ACCESS']:
            self.displayMessage(TTLocalizer.SavedDNAGUIRejectAccess)
        elif base.cr.legitMode:
            return
        elif hasattr(base.cr, 'tutorialManager') and base.cr.tutorialManager.getActive():
            return
        elif hasattr(base.cr, 'episodeManager') and base.cr.episodeManager.getEpisode():
            return
        else:
            savedDNAInterface.setDeleteMode(deleteMode)
            savedDNAInterface.enter(dna)

    def generateToonColor(self):
        DistributedToon.DistributedToon.generateToonColor(self)
        if self.laffMeter:
            self.laffMeter.adjustToonColor(self.style)

    def setWantBattles(self, wantBattles):
        self.wantBattles = wantBattles

    def loadDisguisePages(self):
        if self.disguisePage != None:
            return
        if not launcher.getPhaseComplete(9):
            self.acceptOnce('phaseComplete-9', self.loadDisguisePages)
            return
        self.disguisePage = DisguisePage.DisguisePage()
        self.disguisePage.load()
        self.book.addPage(self.disguisePage, pageName=TTLocalizer.DisguisePageTitle)
        self.loadSosPages()
        return

    def loadSosPages(self):
        if self.sosPage != None:
            return
        self.sosPage = NPCFriendPage.NPCFriendPage()
        self.sosPage.load()
        self.book.addPage(self.sosPage, pageName=TTLocalizer.NPCFriendPageTitle)
        return

    def addRoguesPage(self):
        if self.roguesPage != None:
            return
        if not launcher.getPhaseComplete(5):
            self.acceptOnce('phaseComplete-5', self.addRoguesPage)
            return
        self.roguesPage = RoguesGallery.RoguesGallery()
        self.roguesPage.load()
        self.book.addPage(self.roguesPage, pageName=TTLocalizer.RoguesPageTitle)
        return

    def loadGardenPages(self):
        if self.gardenPage != None:
            return
        if not launcher.getPhaseComplete(5.5):
            self.acceptOnce('phaseComplete-5.5', self.loadPhase55Stuff)
            return
        self.gardenPage = GardenPage.GardenPage()
        self.gardenPage.load()
        self.book.addPage(self.gardenPage, pageName=TTLocalizer.GardenPageTitle)
        return

    def loadPhase55Stuff(self):
        if self.gardenPage == None:
            self.gardenPage = GardenPage.GardenPage()
            self.gardenPage.load()
            self.book.addPage(self.gardenPage, pageName=TTLocalizer.GardenPageTitle)
        elif not launcher.getPhaseComplete(5.5):
            self.acceptOnce('phaseComplete-5.5', self.loadPhase55Stuff)
        self.refreshOnscreenButtons()
        return

    def setAsGM(self, state):
        self.notify.debug('Setting GM State: %s in LocalToon' % state)
        DistributedToon.DistributedToon.setAsGM(self, state)
        if self.gmState:
            if base.config.GetString('gm-nametag-string', '') != '':
                self.gmNameTagString = base.config.GetString('gm-nametag-string')
            if base.config.GetString('gm-nametag-color', '') != '':
                self.gmNameTagColor = base.config.GetString('gm-nametag-color')
            if base.config.GetInt('gm-nametag-enabled', 0):
                self.gmNameTagEnabled = 1
            self.d_updateGMNameTag()

    def displayTalkWhisper(self, fromId, avatarName, chatString):
        sfx = self.soundWhisper
        chatString = avatarName + ': ' + chatString
        whisper = WhisperPopup(chatString, OTPGlobals.getInterfaceFont(), WhisperPopup.WTNormal)
        whisper.setClickable(avatarName, fromId)
        whisper.manage(base.marginManager)
        base.playSfx(sfx)

    def displayTalkAccount(self, fromId, senderName, rawString, mods):
        sender = None
        playerInfo = None
        sfx = self.soundWhisper
        playerInfo = base.cr.playerFriendsManager.playerId2Info.get(fromId, None)
        if playerInfo == None:
            return
        senderAvId = base.cr.playerFriendsManager.findAvIdFromPlayerId(fromId)
        if not senderName and base.cr.playerFriendsManager.playerId2Info.get(fromId):
            senderName = base.cr.playerFriendsManager.playerId2Info.get(fromId).playerName
        senderAvatar = base.cr.identifyAvatar(senderAvId)
        if sender:
            chatString, scrubbed = senderAvatar.scrubTalk(rawString, mods)
        else:
            chatString, scrubbed = self.scrubTalk(rawString, mods)
        chatString = senderName + ': ' + chatString
        whisper = WhisperPopup(chatString, OTPGlobals.getInterfaceFont(), WhisperPopup.WTNormal)
        if playerInfo != None:
            whisper.setClickable(senderName, fromId, 1)
        whisper.manage(base.marginManager)
        base.playSfx(sfx)
        return

    def isLocal(self):
        return 1

    def isTemp(self):
        # Technically, this sould belong to DistributedTemporaryToon,
        # but LocalToon only overrides DistributedToon
        return self.doId >= OTPGlobals.TempAvIdBegin and self.doId <= OTPGlobals.TempAvIdEnd

    def canChat(self):
        return 1

    def startChat(self):
        if self.tutorialAck:
            self.notify.info('calling LocalAvatar.startchat')
            LocalAvatar.LocalAvatar.startChat(self)
            self.accept('chatUpdateSCToontask', self.b_setSCToontask)
            self.accept('chatUpdateSCResistance', self.d_reqSCResistance)
            self.accept('chatUpdateSCSinging', self.b_setSCSinging)
            self.accept('whisperUpdateSCToontask', base.cr.chatManager.sendWhisperSCToontask)
            self.accept('chatUpdateQT', self.b_setQT)
        else:
            self.notify.info('NOT calling LocalAvatar.startchat, in tutorial')

    def stopChat(self):
        LocalAvatar.LocalAvatar.stopChat(self)
        self.ignore('chatUpdateSCToontask')
        self.ignore('chatUpdateSCResistance')
        self.ignore('chatUpdateSCSinging')
        self.ignore('whisperUpdateSCToontask')

    def tunnelIn(self, tunnelOrigin):
        self.b_setTunnelIn(self.tunnelX * 0.8, tunnelOrigin)

    def tunnelOut(self, tunnelOrigin):
        self.tunnelX = self.getX(tunnelOrigin)
        tunnelY = self.getY(tunnelOrigin)
        self.b_setTunnelOut(self.tunnelX * 0.95, tunnelY, tunnelOrigin)

    def handleTunnelIn(self, startTime, endX, x, y, z, h):
        self.notify.debug('LocalToon.handleTunnelIn')

        # This stuff is for both Beta and Non-Beta Intervals
        tunnelOrigin = render.attachNewNode('tunnelOrigin')
        tunnelOrigin.setPosHpr(x, y, z, h, 0, 0)
        self.b_setAnimState('run', self.animMultiplier)
        self.runSound()
        self.reparentTo(render)
        camera.reparentTo(render)
        camera.setPosHpr(tunnelOrigin, 0, 20, 12, 180, -20, 0)

        def cleanup(self = self, tunnelOrigin = tunnelOrigin):
            self.stopSound()
            tunnelOrigin.removeNode()
            messenger.send('tunnelInMovieDone')

        beta = ZoneUtil.isBetaPlaygroundZone(self.zoneId)
        if beta:
            # Beta Inverval
            self.setPosHpr(tunnelOrigin, 0, -16, 0.1, 0, 0, 0)
            toonTrack = Sequence(Func(base.transitions.irisIn, 0.4),
                                 LerpPosHprInterval(nodePath=self, pos=(0, 5, 0.1), hpr=(0, 0, 0), duration=2, other=tunnelOrigin))
        else:
            # Non-Beta Interval
            self.stopLookAround()
            base.transitions.irisIn(0.4)
            toonTrack = self.getTunnelInToonTrack(endX, tunnelOrigin)

            if self.cameraFSM.activeCameraMode == CameraMode.ORBITAL:
                toonTrack.append(Func(self.b_setAnimState, 'neutral', self.animMultiplier))
                toonTrack.append(Func(self.stopSound))
                toonTrack.append(Func(camera.wrtReparentTo,
                                      self.cameraFSM.orbitCamera._CameraOrbital__cameraAttachPoint))
                toonTrack.append(
                        camera.posHprInterval(
                            0.6, (CameraOrbital.CameraOffset.x,
                                  CameraOrbital.CameraOffset.y * (self.getClampedAvatarHeight() * 1./3.),
                                  0),
                                (0, 0, 0), blendType = 'easeInOut'
                        )
                )

        self.tunnelTrack = Sequence(toonTrack, Func(cleanup))
        self.tunnelTrack.start(globalClock.getFrameTime() - startTime)

    def handleTunnelOut(self, startTime, startX, startY, x, y, z, h):
        self.notify.debug('LocalToon.handleTunnelOut')

        # This stuff is for both Beta and Non-Beta Intervals
        tunnelOrigin = render.attachNewNode('tunnelOrigin')
        tunnelOrigin.setPosHpr(x, y, z, h, 0, 0)
        self.b_setAnimState('run', self.animMultiplier)
        self.runSound()
        camera.wrtReparentTo(render)
        startPos = camera.getPos(tunnelOrigin)
        startHpr = camera.getHpr(tunnelOrigin)
        irisDur = 0.4

        def cleanup(self = self, tunnelOrigin = tunnelOrigin):
            self.stopSound()
            self.detachNode()
            tunnelOrigin.removeNode()
            messenger.send('tunnelOutMovieDone')

        beta = ZoneUtil.isBetaPlaygroundZone(self.zoneId)
        if beta:
            # Beta Interval
            reducedCamH = fitDestAngle2Src(startHpr[0], 180)
            reducedAvH = fitDestAngle2Src(self.getH(tunnelOrigin), 180)
            LerpPosHprInterval(nodePath=camera, pos=(0, 20, 12), hpr=(reducedCamH, -20, 0), duration=1, other=tunnelOrigin, blendType='easeInOut').start()
            tracks = Sequence(LerpPosHprInterval(nodePath=self, pos=(0, -16, 0.1), hpr=(reducedAvH, 0, 0), duration=2, other=tunnelOrigin),
                              Func(base.transitions.irisOut, irisDur), Wait(0.5))
        else:
            # Non-Beta Interval
            self.stopLookAround()
            tracks = Parallel()
            camLerpDur = 1.0
            reducedCamH = fitDestAngle2Src(startHpr[0], 180)
            tracks.append(LerpPosHprInterval(camera, camLerpDur, pos=Point3(0, 20, 12), hpr=Point3(reducedCamH, -20, 0), startPos=startPos, startHpr=startHpr, other=tunnelOrigin, blendType='easeInOut', name='tunnelOutLerpCamPos'))
            toonTrack = self.getTunnelOutToonTrack(startX, startY, tunnelOrigin)
            tracks.append(toonTrack)
            tracks.append(Sequence(Wait(toonTrack.getDuration() - (irisDur + 0.1)), Func(base.transitions.irisOut, irisDur)))

        self.tunnelTrack = Sequence(tracks, Func(cleanup))
        self.tunnelTrack.start(globalClock.getFrameTime() - startTime)

    def getPieBubble(self):
        if self.pieType == 9:
            cx = -0.1
            cy = -0.05
            radius = 0.12
        else:
            cx = 0
            cy = 0
            radius = 1
        bubble = CollisionSphere(cx, cy, 0, radius)
        node = CollisionNode('pieBubble')
        node.addSolid(bubble)
        node.setFromCollideMask(ToontownGlobals.PieBitmask | ToontownGlobals.CameraBitmask | ToontownGlobals.FloorBitmask)
        node.setIntoCollideMask(BitMask32.allOff())
        pieBubble = NodePath(node)
        self.pieHandler = CollisionHandlerEvent()
        self.pieHandler.addInPattern('pieHit')
        self.pieHandler.addInPattern('pieHit-%in')
        return pieBubble

    def __beginTossPieMouse(self, mouseParam):
        self.__beginTossPie()

    def __endTossPieMouse(self, mouseParam):
        self.__endTossPie()

    def __beginTossPie(self):
        time = globalClock.getLongTime()
        feather = 10
        messenger.send('wakeup')
        if self.tossPieStart != None:
            return
        if not self.allowPies:
            return
        if self.numPies == 0:
            messenger.send('outOfPies')
            return
        if self.__pieInHand():
            return

        if self.pieType == feather:
            self.localUseFeather()
        else:
            self.localPresentPie(time)
            taskName = self.uniqueName('updatePiePower')
            taskMgr.add(self.__updatePiePower, taskName)
        return

    def __endTossPie(self):
        time = globalClock.getLongTime()
        if self.tossPieStart == None:
            return
        taskName = self.uniqueName('updatePiePower')
        taskMgr.remove(taskName)
        messenger.send('wakeup')
        power = self.__getPiePower(time)
        self.tossPieStart = None
        self.localTossPie(power)

    def localPresentPie(self, time):
        from otp.avatar import Emote
        self.__stopPresentPie()
        if self.tossTrack:
            tossTrack = self.tossTrack
            self.tossTrack = None
            tossTrack.finish()
        self.interruptPie()
        self.tossPieStart = time
        self.__pieSequence = self.__pieSequence + 1 & 255
        sequence = self.__pieSequence
        self.__presentingPie = 1
        pos = self.getPos()
        hpr = self.getHpr()
        timestamp32 = globalClockDelta.getFrameNetworkTime(bits=32)
        self.sendUpdate('presentPie', [pos[0],
         pos[1],
         pos[2],
         hpr[0] % 360.0,
         hpr[1],
         hpr[2],
         timestamp32])
        Emote.globalEmote.disableBody(self)
        messenger.send('begin-pie')
        ival = self.getPresentPieInterval(pos[0], pos[1], pos[2], hpr[0], hpr[1], hpr[2])
        ival = Sequence(ival, name=self.uniqueName('localPresentPie'))
        self.tossTrack = ival
        ival.start()
        self.makePiePowerMeter()
        self.__piePowerMeter.show()
        self.__piePowerMeterSequence = sequence
        self.__piePowerMeter['value'] = 0
        return

    def __stopPresentPie(self):
        if self.__presentingPie:
            from otp.avatar import Emote
            Emote.globalEmote.releaseBody(self)
            messenger.send('end-pie')
            self.__presentingPie = 0
        taskName = self.uniqueName('updatePiePower')
        taskMgr.remove(taskName)

    def __getPiePower(self, time):
        elapsed = max(time - self.tossPieStart, 0.0)
        t = elapsed / self.piePowerSpeed
        t = math.pow(t, self.piePowerExponent)
        power = int(t * 100) % 200
        if power > 100:
            power = 200 - power
        return power

    def __updatePiePower(self, task):
        if not self.__piePowerMeter:
            return Task.done
        self.__piePowerMeter['value'] = self.__getPiePower(globalClock.getLongTime())
        return Task.cont

    def interruptPie(self):
        self.cleanupPieInHand()
        self.__stopPresentPie()
        if self.__piePowerMeter:
            self.__piePowerMeter.hide()
        pie = self.pieTracks.get(self.__pieSequence)
        if pie and pie.getT() < 3 / 24.0:
            del self.pieTracks[self.__pieSequence]
            pie.pause()

    def __pieInHand(self):
        pie = self.pieTracks.get(self.__pieSequence)
        return pie and pie.getT() < 4 / 24.0

    def getFeatherBubble(self):
        if self.__featherBubble == None:
            bubble = CollisionSphere(0, 0, 0, 1)
            node = CollisionNode('featherBubble')
            node.addSolid(bubble)
            node.setFromCollideMask(ToontownGlobals.PieBitmask | ToontownGlobals.CameraBitmask | ToontownGlobals.FloorBitmask)
            node.setIntoCollideMask(BitMask32.allOff())
            self.__featherBubble = NodePath(node)
            self.featherHandler = CollisionHandlerEvent()
            self.featherHandler.addInPattern('featherTouch')
            self.featherHandler.addInPattern('featherTouch-%in')
        return self.__featherBubble

    def localUseFeather(self):
        from otp.avatar import Emote
        if self.featherTrack:
            self.featherTrack.finish()
            self.featherTrack = None

        featherModel = self.getFeatherModel()
        featherBubble = self.getFeatherBubble().instanceTo(NodePath())
        featherBubble.reparentTo(featherModel)

        pos = self.getPos()
        hpr = self.getHpr()
        timestamp32 = globalClockDelta.getFrameNetworkTime(bits=32)

        def featherComesOut(self = self, pos = pos, hpr = hpr, timestamp32 = timestamp32, featherBubble = featherBubble):
            self.sendUpdate('useFeather', [pos[0],
             pos[1],
             pos[2],
             hpr[0] % 360.0,
             hpr[1],
             hpr[2],
             timestamp32])
            if self.numPies != ToontownGlobals.FullPies:
                self.setNumPies(self.numPies - 1)
            # TODO: maybe activate this in the middle of the interval?
            base.cTrav.addCollider(featherBubble, self.featherHandler)

        Emote.globalEmote.disableBody(self)
        ival = self.getFeatherInterval(featherBeginIval = Func(featherComesOut),
                                       callback = self.__featherIvalCallback)
        self.featherTrack = ival
        ival.start()

    def __featherIvalCallback(self):
        messenger.send('localFeatherIvalDone')

    def __toonMoved(self, isSet):
        if isSet and not ClientSettings.SmoothThrowing.get():
            self.interruptPie()

    def localTossPie(self, power):
        if not self.__presentingPie:
            return
        self.__presentingPie = 0
        pos = self.getPos()
        hpr = self.getHpr()
        timestamp32 = globalClockDelta.getFrameNetworkTime(bits=32)
        sequence = self.__pieSequence
        if self.tossTrack:
            tossTrack = self.tossTrack
            self.tossTrack = None
            tossTrack.finish()
        if sequence in self.pieTracks:
            pieTrack = self.pieTracks[sequence]
            del self.pieTracks[sequence]
            pieTrack.finish()
        if sequence in self.splatTracks:
            splatTrack = self.splatTracks[sequence]
            del self.splatTracks[sequence]
            splatTrack.finish()
        self.makePiePowerMeter()
        self.__piePowerMeter['value'] = power
        self.__piePowerMeter.show()
        self.__piePowerMeterSequence = sequence
        pieBubble = self.getPieBubble().instanceTo(NodePath())

        def pieFlies(self = self, pos = pos, hpr = hpr, sequence = sequence, power = power, timestamp32 = timestamp32, pieBubble = pieBubble):
            self.sendUpdate('tossPie', [pos[0],
             pos[1],
             pos[2],
             hpr[0] % 360.0,
             hpr[1],
             hpr[2],
             sequence,
             power,
             timestamp32])
            if self.numPies != ToontownGlobals.FullPies:
                self.setNumPies(self.numPies - 1)
            base.cTrav.addCollider(pieBubble, self.pieHandler)

        toss, pie, flyPie = self.getTossPieInterval(pos[0], pos[1], pos[2], hpr[0], hpr[1], hpr[2], power, beginFlyIval=Func(pieFlies))
        pieBubble.reparentTo(flyPie)
        flyPie.setTag('pieSequence', str(sequence))
        toss = Sequence(toss)
        self.tossTrack = toss
        toss.start()
        pie = Sequence(pie, Func(base.cTrav.removeCollider, pieBubble), Func(self.pieFinishedFlying, sequence))
        self.pieTracks[sequence] = pie
        pie.start()
        return

    @property
    def isPresentingPie(self):
        return self.__presentingPie

    def pieFinishedFlying(self, sequence):
        DistributedToon.DistributedToon.pieFinishedFlying(self, sequence)
        if self.__piePowerMeterSequence == sequence:
            self.__piePowerMeter.hide()

    def __finishPieTrack(self, sequence):
        if sequence in self.pieTracks:
            pieTrack = self.pieTracks[sequence]
            del self.pieTracks[sequence]
            pieTrack.finish()

    def __pieHit(self, entry):
        if not entry.hasSurfacePoint() or not entry.hasInto():
            return
        if not entry.getInto().isTangible():
            return
        sequence = int(entry.getFromNodePath().getNetTag('pieSequence'))
        self.__finishPieTrack(sequence)
        if sequence in self.splatTracks:
            splatTrack = self.splatTracks[sequence]
            del self.splatTracks[sequence]
            splatTrack.finish()
        pieCode = 0
        pieCodeStr = entry.getIntoNodePath().getNetTag('pieCode')
        if pieCodeStr:
            pieCode = int(pieCodeStr)
        pos = entry.getSurfacePoint(render)
        timestamp32 = globalClockDelta.getFrameNetworkTime(bits=32)
        self.sendUpdate('pieSplat', [pos[0], pos[1], pos[2], sequence, pieCode, timestamp32])
        splat = self.getPieSplatInterval(pos[0], pos[1], pos[2], pieCode)
        splat = Sequence(splat, Func(self.pieFinishedSplatting, sequence))
        self.splatTracks[sequence] = splat
        splat.start()
        messenger.send('pieSplat', [self, pieCode])
        messenger.send('localPieSplat', [pieCode, entry, timestamp32])

        if pieCode != ToontownGlobals.PieCodeToon:
            return
        avatarDoId = entry.getIntoNodePath().getNetTag('avatarDoId')
        if avatarDoId == '':
            self.notify.warning('Toon %s has no avatarDoId tag.' % repr(entry.getIntoNodePath()))
            return
        doId = int(avatarDoId)
        if doId != localAvatar.doId:
            self.sendUpdate('hitToon', [doId])

    def __featherTouch(self, entry):
        if not entry.hasSurfacePoint() or not entry.hasInto():
            return
        if not entry.getInto().isTangible():
            return
        messenger.send('localFeatherTouch', [entry])

    def setPiePosType(self, piePosType):
        self.piePosType = piePosType

    def beginAllowPies(self):
        self.allowPies = 1
        self.updatePieButton()

    def endAllowPies(self):
        self.allowPies = 0
        self.updatePieButton()

    def makePiePowerMeter(self):
        from direct.gui.DirectGui import DirectWaitBar, DGG
        if self.__piePowerMeter == None:
            self.__piePowerMeter = DirectWaitBar(parent = base.a2dTopCenter,
                                                 relief = DGG.SUNKEN,
                                                 frameSize = (-0.2, 0.2, -0.03, 0.03),
                                                 borderWidth = (0.005, 0.005),
                                                 barColor = (0.4, 0.6, 1.0, 1),
                                                 pos = self.piePositions[self.piePosType][1])
            self.__piePowerMeter.hide()

    def updatePieButton(self):
        from toontown.toonbase import ToontownBattleGlobals
        from direct.gui.DirectGui import DirectButton, DGG
        wantButton = 0
        if self.allowPies and self.numPies > 0:
            wantButton = 1
        if not launcher.getPhaseComplete(5):
            wantButton = 0
        haveButton = self.__pieButton != None
        if not haveButton and not wantButton:
            return
        if haveButton and not wantButton:
            self.__pieButton.destroy()
            self.__pieButton = None
            self.__pieButtonType = None
            self.__pieButtonCount = None
            return
        if self.__pieButtonType != self.pieType:
            if self.__pieButton:
                self.__pieButton.destroy()
                self.__pieButton = None
        if self.__pieButton == None:
            inv = self.inventory
            evidence = 7
            snowball = 8
            pinkSlip = 9
            feather = 10
            if self.pieType == evidence:
                gui = loader.loadModel('phase_3.5/models/gui/stickerbook_gui')
                pieGui = gui.find('**/summons')
                pieScale = 0.1
            elif self.pieType == snowball:
                gui = None
                texture = loader.loadTexture('phase_14.5/maps/snowball.png')
                pieGui = OnscreenImage(image=texture)
                pieGui.setTransparency(TransparencyAttrib.MAlpha)
                pieScale = 0.05
            elif self.pieType == pinkSlip:
                gui = loader.loadModel('phase_3.5/models/gui/ttoff_m_gui_sbk_inventoryPage')
                pieGui = gui.find('**/inv_pinkSlip')
                pieScale = 0.12
            elif self.pieType == feather:
                gui = None
                pieGui = (inv.invModels[ToontownBattleGlobals.HEAL_TRACK][0],)
                pieScale = 0.85
            else:
                gui = None
                pieGui = (inv.invModels[ToontownBattleGlobals.THROW_TRACK][self.pieType],)
                pieScale = 0.85
            self.__pieButton = DirectButton(parent = base.a2dTopCenter,
                                            relief = None,
                                            image = (inv.upButton, inv.downButton, inv.rolloverButton),
                                            geom = pieGui,
                                            text = '50',
                                            text_scale = 0.04,
                                            text_align = TextNode.ARight,
                                            geom_scale = pieScale,
                                            geom_pos = (-0.01, 0, 0),
                                            text_fg = Vec4(1, 1, 1, 1),
                                            text_pos = (0.07, -0.04),
                                            image_color = (0, 0.6, 1, 1),
                                            pos = self.piePositions[self.piePosType][0])
            self.__pieButton.bind(DGG.B1PRESS, self.__beginTossPieMouse)
            self.__pieButton.bind(DGG.B1RELEASE, self.__endTossPieMouse)
            self.__pieButtonType = self.pieType
            self.__pieButtonCount = None
            if gui:
                gui.removeNode()
                del gui
            if self.pieType == snowball:
                pieGui.destroy()
                del pieGui
        if self.__pieButtonCount != self.numPies:
            if self.numPies == ToontownGlobals.FullPies:
                self.__pieButton['text'] = ''
            else:
                self.__pieButton['text'] = str(self.numPies)
            self.__pieButtonCount = self.numPies

    def displayWhisper(self, fromId, chatString, whisperType):
        episode = base.cr.episodeManager.getEpisode()
        if episode:
            return
        sender = None
        if not hasattr(self, 'soundWhisper') or not self.soundWhisper:
            return
        sfx = self.soundWhisper
        if fromId == TTLocalizer.Clarabelle:
            chatString = TTLocalizer.Clarabelle + ': ' + chatString
            sfx = self.soundPhoneRing
        elif fromId != 0:
            sender = base.cr.identifyAvatar(fromId)
        if whisperType == WhisperPopup.WTNormal or whisperType == WhisperPopup.WTQuickTalker:
            color = Vec4(1, 1, 1, 1)
            if sender == None:
                return
            chatString = sender.getName() + ': ' + chatString
        elif whisperType == WhisperPopup.WTSystem:
            color = Vec4(0.8, 0.3, 0.6, 1.0)
            sfx = self.soundSystemMessage
        else:
            color = Vec4(0.8, 0.3, 0.6, 1.0)
        whisper = WhisperPopup(chatString, OTPGlobals.getInterfaceFont(), whisperType)
        if sender != None:
            whisper.setClickable(sender.getName(), fromId)
        whisper.manage(base.marginManager)
        base.playSfx(sfx)
        if whisperType != WhisperPopup.WTGlobal:
            messenger.send('addToLog', ['', fromId, None, None, color, chatString, whisperType])

    def displaySystemClickableWhisper(self, fromId, chatString, whisperType):
        sender = None
        sfx = self.soundWhisper
        if fromId == TTLocalizer.Clarabelle:
            chatString = TTLocalizer.Clarabelle + ': ' + chatString
            sfx = self.soundPhoneRing
        elif fromId != 0:
            sender = base.cr.identifyAvatar(fromId)
        if whisperType == WhisperPopup.WTNormal or whisperType == WhisperPopup.WTQuickTalker:
            if sender == None:
                return
            chatString = sender.getName() + ': ' + chatString
        elif whisperType == WhisperPopup.WTSystem:
            sfx = self.soundSystemMessage
        whisper = WhisperPopup(chatString, OTPGlobals.getInterfaceFont(), whisperType)
        whisper.setClickable('', fromId)
        whisper.manage(base.marginManager)
        base.playSfx(sfx)
        messenger.send('addToLog', ['', fromId, None, None, Vec4(0.8, 0.3, 0.6, 1.0), chatString, whisperType])

    def clickedWhisper(self, doId, isPlayer = None):
        if doId > 0:
            LocalAvatar.LocalAvatar.clickedWhisper(self, doId, isPlayer)
        else:
            foundCanStart = False
            for partyInfo in self.hostedParties:
                if partyInfo.status == PartyGlobals.PartyStatus.CanStart:
                    foundCanStart = True
                    break

            if base.cr and base.cr.playGame and base.cr.playGame.getPlace() and base.cr.playGame.getPlace().fsm:
                fsm = base.cr.playGame.getPlace().fsm
                curState = fsm.getCurrentState().getName()
                if curState in ['walk', 'stickerBook']:
                    if hasattr(self, 'eventsPage'):
                        desiredMode = -1
                        if doId == -1:
                            desiredMode = EventsPage.EventsPage_Invited
                        elif foundCanStart:
                            desiredMode = EventsPage.EventsPage_Host
                        if desiredMode >= 0:
                            self.book.setPage(self.eventsPage)
                            self.eventsPage.setMode(desiredMode)
                            if curState == 'walk':
                                fsm.request('stickerBook')

    def loadFurnitureGui(self):
        if self.__furnitureGui:
            return
        guiModels = loader.loadModel('phase_5.5/models/gui/house_design_gui')
        self.__furnitureGui = DirectFrame(relief=None, parent=base.a2dTopLeft, pos=(0.143333, 0, -0.67), scale=0.04,
                                          image=guiModels.find('**/attic'))
        DirectLabel(parent=self.__furnitureGui, relief=None, image=guiModels.find('**/rooftile'))
        bMoveStartUp = guiModels.find('**/bu_attic/bu_attic_up')
        bMoveStartDown = guiModels.find('**/bu_attic/bu_attic_down')
        bMoveStartRollover = guiModels.find('**/bu_attic/bu_attic_rollover')
        DirectButton(parent=self.__furnitureGui, relief=None, image=[bMoveStartUp,
         bMoveStartDown,
         bMoveStartRollover,
         bMoveStartUp], text=['', TTLocalizer.HDMoveFurnitureButton, TTLocalizer.HDMoveFurnitureButton], text_fg=(1, 1, 1, 1), text_shadow=(0, 0, 0, 1), text_font=ToontownGlobals.getInterfaceFont(), pos=(-0.3, 0, 9.4), command=self.__startMoveFurniture)
        self.__furnitureGui.hide()
        guiModels.removeNode()
        return

    def showFurnitureGui(self):
        self.loadFurnitureGui()
        self.__furnitureGui.show()

    def hideFurnitureGui(self):
        if self.__furnitureGui:
            self.__furnitureGui.hide()

    def clarabelleNewsPageCollision(self, show = True):
        if self.__clarabelleButton == None:
            return
        claraXPos = ClaraBaseXPos
        notifyXPos = CatalogNotifyDialog.CatalogNotifyBaseXPos
        if show and WantNewsPage:
            claraXPos += AdjustmentForNewsButton
            notifyXPos += AdjustmentForNewsButton
        if WantNewsPage:
            newPos = (claraXPos - 0.1, 1.0, -0.55)
        else:
            newPos = (claraXPos, 1.0, -0.63)
        self.__clarabelleButton.setPos(newPos)
        if self.__catalogNotifyDialog == None or self.__catalogNotifyDialog.frame == None:
            return
        notifyPos = self.__catalogNotifyDialog.frame.getPos()
        notifyPos[0] = notifyXPos
        self.__catalogNotifyDialog.frame.setPos(notifyPos)
        return

    def loadClarabelleGui(self):
        if self.__clarabelleButton:
            return
        guiItems = loader.loadModel('phase_5.5/models/gui/catalog_gui')
        circle = guiItems.find('**/cover/blue_circle')
        icon = guiItems.find('**/cover/clarabelle')
        icon.reparentTo(circle)
        rgba = VBase4(0.71589, 0.784547, 0.974, 1.0)
        white = VBase4(1.0, 1.0, 1.0, 1.0)
        icon.setColor(white)
        claraXPos = ClaraBaseXPos
        newScale = oldScale = 0.5
        newPos = (claraXPos, 1.0, -0.63)
        if WantNewsPage:
            claraXPos += AdjustmentForNewsButton
            oldPos = ((claraXPos, 1.0, -0.63),)
            newScale = oldScale * ToontownGlobals.NewsPageScaleAdjust
            newPos = (claraXPos - 0.1, 1.0, -0.55)
        self.__clarabelleButton = DirectButton(relief=None, image=circle, text='', text_fg=(1, 1, 1, 1), text_shadow=(0, 0, 0, 1), text_scale=0.1, text_pos=(-1.06, 1.06), text_font=ToontownGlobals.getInterfaceFont(), pos=newPos, scale=newScale, command=self.__handleClarabelleButton)
        self.__clarabelleButton.reparentTo(base.a2dTopRight, DGG.BACKGROUND_SORT_INDEX - 1)
        button = self.__clarabelleButton.stateNodePath[0]
        self.__clarabelleFlash = Sequence(LerpColorInterval(button, 2, white, blendType='easeInOut'), LerpColorInterval(button, 2, rgba, blendType='easeInOut'))
        self.__clarabelleFlash.loop()
        self.__clarabelleFlash.pause()
        return

    def showClarabelleGui(self, mailboxItems):
        return
        self.loadClarabelleGui()
        if mailboxItems:
            self.__clarabelleButton['text'] = ['', TTLocalizer.CatalogNewDeliveryButton, TTLocalizer.CatalogNewDeliveryButton]
        else:
            self.__clarabelleButton['text'] = ['', TTLocalizer.CatalogNewCatalogButton, TTLocalizer.CatalogNewCatalogButton]
        if not self.mailboxNotify and not self.awardNotify and self.catalogNotify == ToontownGlobals.OldItems and (self.simpleMailNotify != ToontownGlobals.NoItems or self.inviteMailNotify != ToontownGlobals.NoItems):
            self.__clarabelleButton['text'] = ['', TTLocalizer.MailNewMailButton, TTLocalizer.MailNewMailButton]
        if self.newsButtonMgr.isNewIssueButtonShown():
            self.clarabelleNewsPageCollision(True)
        self.__clarabelleButton.show()
        self.__clarabelleFlash.resume()

    def hideClarabelleGui(self):
        if self.__clarabelleButton:
            self.__clarabelleButton.hide()
            self.__clarabelleFlash.pause()

    def __handleClarabelleButton(self):
        self.stopMoveFurniture()
        place = base.cr.playGame.getPlace()
        if place == None:
            self.notify.warning('Tried to go home, but place is None.')
            return
        if self.__catalogNotifyDialog:
            self.__catalogNotifyDialog.cleanup()
            self.__catalogNotifyDialog = None
        if base.config.GetBool('want-qa-regression', 0):
            self.notify.info('QA-REGRESSION: VISITESTATE: Visit estate')
        if base.cr.playGame.getPlaceId() != ToontownGlobals.MyEstate:
            place.goHomeNow(self.lastHood)

    def __startMoveFurniture(self):
        self.oldPos = self.getPos()
        if base.config.GetBool('want-qa-regression', 0):
            self.notify.info('QA-REGRESSION: ESTATE:  Furniture Placement')
        if self.cr.furnitureManager != None:
            self.cr.furnitureManager.d_suggestDirector(self.doId)
        elif self.furnitureManager != None:
            self.furnitureManager.d_suggestDirector(self.doId)
        return

    def stopMoveFurniture(self):
        if self.oldPos:
            self.setPos(self.oldPos)
            self.oldPos = None
        if self.furnitureManager != None:
            self.furnitureManager.d_suggestDirector(0)
        return

    def setFurnitureDirector(self, avId, furnitureManager):
        if avId == 0:
            if self.furnitureManager == furnitureManager:
                messenger.send('exitFurnitureMode', [furnitureManager])
                self.furnitureManager = None
                self.furnitureDirector = None
        elif avId != self.doId:
            if self.furnitureManager == None or self.furnitureDirector != avId:
                self.furnitureManager = furnitureManager
                self.furnitureDirector = avId
                messenger.send('enterFurnitureMode', [furnitureManager, 0])
        else:
            if self.furnitureManager != None:
                messenger.send('exitFurnitureMode', [self.furnitureManager])
                self.furnitureManager = None
            self.furnitureManager = furnitureManager
            self.furnitureDirector = avId
            messenger.send('enterFurnitureMode', [furnitureManager, 1])
        self.refreshOnscreenButtons()
        return

    def hideNewsGui(self):
        if self.newsButtonMgr:
            self.newsButtonMgr.request('Hidden')

    def getAvPosStr(self):
        pos = self.getPos()
        hpr = self.getHpr()
        serverVersion = base.cr.getServerVersion()
        districtName = base.cr.getShardName()
        if hasattr(base.cr.playGame.hood, 'loader') and hasattr(base.cr.playGame.hood.loader, 'place') and base.cr.playGame.getPlace() != None:
            zoneId = base.cr.playGame.getPlace().getZoneId()
        else:
            zoneId = '?'
        strPosCoordText = 'X: %.3f' % pos[0] + ', Y: %.3f' % pos[1] + '\nZ: %.3f' % pos[2] + ', H: %.3f' % hpr[0] + '\nZone: %s' % str(zoneId) + ', Ver: %s, ' % serverVersion + 'District: %s' % districtName
        return strPosCoordText
        self.refreshOnscreenButtons()
        return

    def getPlaceZone(self):
        try:
            return base.cr.playGame.getPlace().getZoneId()
        except:
            return 0

    def getDebugInfo(self):
        pos = self.getPos()
        renderPos = self.getPos(render)
        parent = self.getParent()
        hpr = self.getHpr()
        renderHpr = self.getHpr(render)
        camPos = base.cam.getPos(render)
        camHpr = base.cam.getHpr(render)
        avId = base.localAvatar.getDoId()
        districtName = base.cr.getShardName()
        zoneId = self.getPlaceZone()

        mouse = base.win.getPointer(0)
        mouseX = max(0, min(mouse.getX() / base.win.getXSize(), 1))
        mouseY = max(0, min(mouse.getY() / base.win.getYSize(), 1))

        sysver = f'{platform.system()} {platform.release()} ({platform.version()} {platform.machine()})'

        if FilterManager.activeFilter:
            activeFilter = FilterManager.activeFilter.identifier
        else:
            activeFilter = "None"

        try:
            latency = base.cr.timeManager.getElapsedTime() * 1000.0
            sync = globalClockDelta.getUncertainty() * 1000.0
        except:
            latency = 0
            sync = 0

        toonPosStr = f'({renderPos[0]:.2f}, {renderPos[1]:.2f}, {renderPos[2]:.2f}) (render)'
        toonHprStr = f'({renderHpr[0] % 360:.2f}, {renderHpr[1] % 360:.2f}, {renderHpr[2] % 360:.2f}) (render)'
        if parent != render:
            # This space is here to line it up with the one above
            toonPosStr += f'\n              ' \
                          f'({pos[0]:.2f}, {pos[1]:.2f}, {pos[2]:.2f}) ({NodePath.getName(parent)})'

            toonHprStr += f'\n              ' \
                          f'({hpr[0] % 360:.2f}, {hpr[1] % 360:.2f}, {hpr[2] % 360:.2f}) ({NodePath.getName(parent)})'
        di = base.pipe.getDisplayInformation()
        panda = f"{ShowBaseGlobal.pandaSystem.getVersionString()} ({ShowBaseGlobal.pandaSystem.getBuildDate()}) Python {self.pythonVersion}"

        info = 'FPS: {0:.1f} ({1:.2f} ms)\n\n'\
               'Mouse Pos: ({2:.2f}, {3:.2f})\n\n' \
               'Toon Pos: {4}\n' \
               'Toon Hpr: {5}\n\n' \
               'Camera Pos: ({6:.2f}, {7:.2f}, {8:.2f})\n'\
               'Camera Hpr: ({9:.2f}, {10:.2f}, {11:.2f})\n' \
               'Camera Mode: {12}\n\n' \
               'Realm Name: {13}\n' \
               'Server Address: {14}\n' \
               'Avatar ID: {15}\n' \
               'Zone ID: {16}\n\n' \
               'Latency: {17:.2f} ms\n' \
               'Sync: \xb1{18:.2f} ms\n\n' \
               'OS: {19}\n' \
               'Engine: {20}\n\n' \
               'CPU: {21}\n' \
               'GPU: {22}\n' \
               'GPU Drivers: {23}\n\n' \
               'Active Filter: {24}'.format(globalClock.getAverageFrameRate(), (1.0/globalClock.getAverageFrameRate())*1000,
                                            mouseX, mouseY, toonPosStr, toonHprStr,
                                            camPos[0], camPos[1], camPos[2], camHpr[0], camHpr[1], camHpr[2],
                                            self.cameraFSM.state, districtName,
                                            bboard.get('game-server'), avId, zoneId, latency, sync, sysver, panda,
                                            f'{di.getNumCpuCores()}x {di.getCpuBrandString()} ',
                                            base.win.gsg.getDriverRenderer(), base.win.gsg.getDriverVersion(),
                                            activeFilter)
        # FIXME: Ignore string errors?
        # info = info.decode(errors='ignore')
        return info

    def __updateDebugLabel(self, task):
        try:
            debug = self.getDebugInfo()

            if self.debugLabel['text'] != debug:
                self.debugLabel['text'] = debug
        except:
            pass

        return task.again

    def __updateTaskDebugLabel(self, task):
        debug = str(taskMgr)

        if self.taskDebugLabel['text'] != debug:
            self.taskDebugLabel['text'] = debug

        return task.again

    def __updateIvalDebugLabel(self, task):
        debug = str(ivalMgr)

        if self.taskDebugLabel['text'] != debug:
            self.taskDebugLabel['text'] = debug

        return task.again

    def stopDebug(self):
        if self.debugLabel:
            self.debugLabel.destroy()
        self.debugLabel = None

        for cell in base.leftCells:
            base.setCellsAvailable([cell], 1)

        taskMgr.remove(self.uniqueName('updateDebugLabel'))

    def stopTaskDebug(self):
        if self.taskDebugLabel:
            self.taskDebugLabel.destroy()

        self.taskDebugLabel = None
        taskMgr.remove(self.uniqueName('updateTaskDebugLabel'))

    def createTaskLabel(self, text):
        if self.taskDebugLabel:
            self.stopTaskDebug()
            return False

        self.taskDebugLabel = DirectLabel(base.a2dTopLeft, relief=None, text=text,
                                          text_font=ToontownGlobals.getDebugFont(), text_scale=0.036,
                                          text_align=TextNode.ALeft, text_fg=(1, 1, 1, 1), text_shadow=(0, 0, 0, 1),
                                          pos=(0.03, 0, -0.05))
        self.taskDebugLabel.setBin('gui-popup', 0)
        self.taskDebugLabel.show()
        return True

    def thinkTask(self):
        if self.createTaskLabel(str(taskMgr)):
            taskMgr.doMethodLater(0.2, self.__updateTaskDebugLabel, self.uniqueName('updateTaskDebugLabel'))

    def thinkIval(self):
        if self.createTaskLabel(str(ivalMgr)):
            taskMgr.doMethodLater(0.2, self.__updateIvalDebugLabel, self.uniqueName('updateTaskDebugLabel'))

    def thinkPos(self):
        if self.debugLabel:
            self.stopDebug()
            return

        self.debugLabel = DirectLabel(base.a2dBottomLeft, relief=None, text=self.getDebugInfo(),
                                      text_font=ToontownGlobals.getDebugFont(), text_scale=0.035,
                                      text_align=TextNode.ALeft, text_fg=(1, 1, 1, 1), text_shadow=(0, 0, 0, 1),
                                      pos=(0.03, 0, 1.28))
        self.debugLabel.setBin('gui-popup', 0)
        # We don't want overlay filters to effect this
        self.debugLabel.setShaderOff()
        self.debugLabel.show()

        for cell in base.leftCells:
            base.setCellsAvailable([cell], 0)

        taskMgr.doMethodLater(0.04, self.__updateDebugLabel, self.uniqueName('updateDebugLabel'))

    def __autoTimeSync(self, task):
        if base.cr.timeManager:
            base.cr.timeManager.synchronize('auto time sync')

        return task.again

    def __placeMarker(self):
        pos = self.getPos()
        hpr = self.getHpr()
        chest = loader.loadModel('phase_4/models/props/coffin')
        chest.reparentTo(render)
        chest.setColor(1, 0, 0, 1)
        chest.setPosHpr(pos, hpr)
        chest.setScale(0.5)

    def setFriendsListButtonActive(self, active):
        self.friendsListButtonActive = active
        self.refreshOnscreenButtons()

    @deprecated("Remove with new Action bar")
    def obscureFriendsListButton(self, increment):
        return
        self.friendsListButtonObscured += increment
        self.refreshOnscreenButtons()

    def obscureMoveFurnitureButton(self, increment):
        self.moveFurnitureButtonObscured += increment
        self.refreshOnscreenButtons()

    def obscureClarabelleButton(self, increment):
        self.clarabelleButtonObscured += increment
        self.refreshOnscreenButtons()

    def refreshOnscreenButtons(self):
        from toontown.quest import Quests
        self.bSocialMenu.hide()
        self.hideFurnitureGui()
        self.hideClarabelleGui()
        self.hideNewsGui()
        clarabelleHidden = 1
        newsHidden = 1
        hotkey = HotkeySettings.ToggleSocialMenu.getPressed()
        self.ignore(hotkey)
        if self.friendsListButtonActive and self.friendsListButtonObscured <= 0:
            self.bSocialMenu.show()
            self.accept(hotkey, self.sendSocialMenuEvent)
            if self.clarabelleButtonObscured <= 0 and self.isTeleportAllowed():
                if self.catalogNotify == ToontownGlobals.NewItems or self.mailboxNotify == ToontownGlobals.NewItems or self.simpleMailNotify == ToontownGlobals.NewItems or self.inviteMailNotify == ToontownGlobals.NewItems or self.awardNotify == ToontownGlobals.NewItems:
                    showClarabelle = (not launcher or launcher.getPhaseComplete(5.5))

                    if ZoneUtil.isBetaPlaygroundZone(self.zoneId) and ClientSettings.BetaPlaygroundInterface.get():
                        showClarabelle = 0

                    newsHidden = 0
                    for quest in self.quests:
                        if quest[0] in Quests.PreClarabelleQuestIds and self.mailboxNotify != ToontownGlobals.NewItems and self.awardNotify != ToontownGlobals.NewItems:
                            showClarabelle = 0

                    if base.cr.playGame.getPlace().getState() == 'stickerBook':
                        showClarabelle = 0
                        newsHidden = 1
                    if showClarabelle:
                        newItemsInMailbox = self.mailboxNotify == ToontownGlobals.NewItems or self.awardNotify == ToontownGlobals.NewItems
                        self.showClarabelleGui(newItemsInMailbox)
                        clarabelleHidden = 0
        if clarabelleHidden:
            if self.__catalogNotifyDialog:
                self.__catalogNotifyDialog.cleanup()
                self.__catalogNotifyDialog = None
        else:
            self.newCatalogNotify()
        if not newsHidden:
            self.newsButtonMgr.request('NormalWalk')
        if self.moveFurnitureButtonObscured <= 0:
            if self.furnitureManager != None and self.furnitureDirector == self.doId:
                self.loadFurnitureGui()
                self.__furnitureGui.setPos(0.173333, 1, -1.03)
                self.__furnitureGui.setScale(0.06)
            elif self.cr.furnitureManager != None:
                self.showFurnitureGui()
                taskMgr.remove('lerpFurnitureButton')
                self.__furnitureGui.posHprScaleInterval(pos=Point3(0.143333, 0, -0.67), hpr=Vec3(0.0, 0.0, 0.0),
                                                        scale=Vec3(0.04, 0.04, 0.04), duration=1.0,
                                                        blendType='easeInOut', name='lerpFurnitureButton').start()
        if hasattr(self, 'inEstate') and self.inEstate:
            self.loadGardeningGui()
            self.hideGardeningGui()
        else:
            self.hideGardeningGui()
        if hasattr(self, 'book'):
            # This sometimes gets called before the book is defined.
            self.changeButtonTextures()
        return

    def setGhostMode(self, flag):
        if flag == 2:
            self.seeGhosts = 1
        DistributedToon.DistributedToon.setGhostMode(self, flag)
        if flag in (0, 2):
            self.reconsiderSleep()

    def newCatalogNotify(self):
        if not self.gotCatalogNotify:
            return
        hasPhase = not launcher or launcher.getPhaseComplete(5.5)
        if not hasPhase:
            return
        if not self.friendsListButtonActive or self.friendsListButtonObscured > 0:
            return
        self.gotCatalogNotify = 0
        currentWeek = self.catalogScheduleCurrentWeek - 1
        if currentWeek < 57:
            seriesNumber = currentWeek / ToontownGlobals.CatalogNumWeeksPerSeries + 1
            weekNumber = currentWeek % ToontownGlobals.CatalogNumWeeksPerSeries + 1
        elif currentWeek < 65:
            seriesNumber = 6
            weekNumber = currentWeek - 56
        else:
            seriesNumber = currentWeek / ToontownGlobals.CatalogNumWeeksPerSeries + 2
            weekNumber = currentWeek % ToontownGlobals.CatalogNumWeeksPerSeries + 1
        message = None
        if self.mailboxNotify == ToontownGlobals.NoItems:
            if self.catalogNotify == ToontownGlobals.NewItems:
                if self.catalogScheduleCurrentWeek == 1:
                    message = (TTLocalizer.CatalogNotifyFirstCatalog,)
                else:
                    message = (TTLocalizer.CatalogNotifyNewCatalog % weekNumber,)
                id = ("catalog_notif",)
        elif self.mailboxNotify == ToontownGlobals.NewItems:
            if self.catalogNotify == ToontownGlobals.NewItems:
                message = (TTLocalizer.CatalogNotifyNewCatalog % weekNumber, TTLocalizer.CatalogNotifyNewDelivery)
                id = ("catalog_notif", "catalog_mail")
            else:
                message = (TTLocalizer.CatalogNotifyNewDelivery,)
                id = ("catalog_mail",)
        elif self.mailboxNotify == ToontownGlobals.OldItems:
            if self.catalogNotify == ToontownGlobals.NewItems:
                message = (TTLocalizer.CatalogNotifyNewCatalog % weekNumber, TTLocalizer.CatalogNotifyOldDelivery)
                id = ("catalog_notif", "catalog_mail")
            else:
                message = (TTLocalizer.CatalogNotifyOldDelivery,)
                id = ("catalog_mail",)
        if self.awardNotify == ToontownGlobals.NoItems:
            pass
        elif self.awardNotify == ToontownGlobals.NewItems:
            oldStr = ''
            if message:
                oldStr = message[0] + ' '
            oldStr += TTLocalizer.AwardNotifyNewItems
            message = (oldStr,)
            id = ("catalog_mail",)
        elif self.awardNotify == ToontownGlobals.OldItems:
            oldStr = ''
            if message:
                oldStr = message[0] + ' '
            oldStr += TTLocalizer.AwardNotifyOldItems
            message = (oldStr,)
            id = ("catalog_mail",)
        if self.simpleMailNotify == ToontownGlobals.NewItems or self.inviteMailNotify == ToontownGlobals.NewItems:
            oldStr = ''
            if message:
                oldStr = message[0] + ' '
            oldStr += TTLocalizer.MailNotifyNewItems
            message = (oldStr,)
            id = ("catalog_mail",)
        if message == None:
            return
        if self.__catalogNotifyDialog:
            self.__catalogNotifyDialog.cleanup()
        #self.__catalogNotifyDialog = CatalogNotifyDialog.CatalogNotifyDialog(message)
        guiItems = loader.loadModel('phase_5.5/models/gui/catalog_gui')
        for i in range(len(message)):
            icon = guiItems.find('**/cover/clarabelle').copyTo(hidden)
            m = message[i]
            id = id[i]
            self.sendNotification(title = TTLocalizer.NotificationTitleCattlelog, body = m, icon = icon, id = id,
                                  button2Text = TTLocalizer.NotificationCatalogGoHome, button2Action = self.__handleClarabelleButton)
        guiItems.removeNode()

    def allowHardLand(self):
        retval = LocalAvatar.LocalAvatar.allowHardLand(self)
        # Don't play this anim in beta playgrounds
        return retval and not ZoneUtil.isBetaPlaygroundZone(self.zoneId)

    def setSpeed(self, forwardSpeed, rotateSpeed, slideSpeed = 0):
        action = DistributedToon.DistributedToon.setSpeed(self, forwardSpeed, rotateSpeed, slideSpeed)
        retroMode = ClientSettings.ClassicSFX.get()
        if self.standWalkRunReverse is not None and not retroMode:
            replay = 0
            showWake, wakeWaterHeight = ZoneUtil.getWakeInfo()
            if (showWake and self.getZ(render) < wakeWaterHeight) and not self.useWaterSound:
                if self.soundRun.status() == self.soundRun.PLAYING:
                    replay = 1
                    self.soundRun.stop()
                base.loader.unloadSfx(self.soundRun)
                if self.soundWalk.status() == self.soundWalk.PLAYING:
                    replay = 2
                    self.soundWalk.stop()
                base.loader.unloadSfx(self.soundWalk)
                self.soundRun = base.loader.loadSfx('phase_4/audio/sfx/AV_footstep_runloop_new_water.ogg')
                self.soundRun.setVolume(2)
                self.soundWalk = base.loader.loadSfx('phase_4/audio/sfx/AV_footstep_walkloop_water.ogg')
                self.useWaterSound = True
            elif not (showWake and self.getZ(render) < wakeWaterHeight) and self.useWaterSound:
                replay = self.updateFootstepSounds()
                self.useWaterSound = False
            if replay == 1:
                self.runSound()
            elif replay == 2:
                self.walkSound()
        return action

    def updateFootstepSounds(self):
        # this is really here for when we update this setting
        retroMode = ClientSettings.ClassicSFX.get()

        replay = 0
        if hasattr(self, 'soundRun'):
            if self.soundRun.status() == self.soundRun.PLAYING:
                replay = 1
                self.soundRun.stop()
                base.loader.unloadSfx(self.soundRun)
            if self.soundWalk.status() == self.soundWalk.PLAYING:
                replay = 2
                self.soundWalk.stop()
                base.loader.unloadSfx(self.soundWalk)

        currentTransformation = self.getActiveTransformationIndex()
        # this is really here for when we update this setting
        if retroMode:
            self.soundRun = base.loader.loadSfx('phase_3.5/audio/sfx/AV_footstep_runloop.ogg')
            self.soundWalk = base.loader.loadSfx('phase_3.5/audio/sfx/AV_footstep_walkloop.ogg')
        elif currentTransformation == ToontownGlobals.TransformationCog:
            ext = 'sm'
            if self.suit.getHeight() >= 6.4:
                ext = 'lg'
            footstepSound = 'phase_5/audio/sfx/ENC_cog' + self.suit.getBodyType().lower() + 'fs' + ext + '.ogg'
            self.soundRun = base.loader.loadSfx(footstepSound)
            self.soundRun.setVolume(0.25)
            self.soundWalk = base.loader.loadSfx(footstepSound)
            self.soundWalk.setVolume(0.25)
        else:
            self.soundRun = base.loader.loadSfx('phase_3.5/audio/sfx/AV_footstep_runloop_new.ogg')
            self.soundWalk = base.loader.loadSfx('phase_3.5/audio/sfx/AV_footstep_walkloop.ogg')

        return replay

    def setShovelGuiLevel(self, level = 0):
        pass

    def setWateringCanGuiLevel(self, level = 0):
        pass

    def loadGardeningGui(self):
        if self.__gardeningGui:
            return
        gardenGuiCard = loader.loadModel('phase_5.5/models/gui/planting_gui')
        self.__gardeningGui = DirectFrame(relief=None, parent=base.a2dTopLeft, geom=gardenGuiCard,
                                          geom_color=GlobalDialogColor, geom_scale=(0.17, 1.0, 0.3),
                                          pos=(0.133333, 0, -0.5), scale=1.0)
        self.__gardeningGui.setName('gardeningFrame')
        self.__gardeningGuiFake = DirectFrame(relief=None, parent=base.a2dTopLeft, geom=None,
                                              geom_color=GlobalDialogColor, geom_scale=(0.17, 1.0, 0.3),
                                              pos=(0.133333, 0, -0.5), scale=1.0)
        self.__gardeningGuiFake.setName('gardeningFrameFake')
        iconScale = 1
        iconColorWhite = Vec4(1.0, 1.0, 1.0, 1.0)
        iconColorGrey = Vec4(0.7, 0.7, 0.7, 1.0)
        iconColorBrown = Vec4(0.7, 0.4, 0.3, 1.0)
        iconColorBlue = Vec4(0.2, 0.3, 1.0, 1.0)
        shovelCardP = loader.loadModel('phase_5.5/models/gui/planting_but_shovel_P')
        shovelCardY = loader.loadModel('phase_5.5/models/gui/planting_but_shovel_Y')
        wateringCanCardP = loader.loadModel('phase_5.5/models/gui/planting_but_can_P')
        wateringCanCardY = loader.loadModel('phase_5.5/models/gui/planting_but_can_Y')
        backCard = loader.loadModel('phase_5.5/models/gui/planting_gui')
        iconImage = None
        iconModels = loader.loadModel('phase_3.5/models/gui/sos_textures')
        iconGeom = iconModels.find('**/fish')
        buttonText = TTLocalizer.GardeningPlant
        self.shovelText = ('',
         '',
         buttonText,
         '')
        self.__shovelButtonFake = DirectLabel(parent=self.__gardeningGuiFake, relief=None, text=self.shovelText, text_align=TextNode.ALeft, text_pos=(0.0, -0.0), text_scale=0.07, text_fg=(1, 1, 1, 1), text_shadow=(0, 0, 0, 1), image_scale=(0.18, 1.0, 0.36), geom=None, geom_scale=iconScale, geom_color=iconColorWhite, pos=(0.15, 0, 0.2), scale=0.775)
        self.shovelButtonFake = self.__shovelButtonFake
        self.shovelText = ('',
         '',
         buttonText,
         '')
        self.__shovelButton = DirectButton(parent=self.__gardeningGui, relief=None, text=self.shovelText, text_align=TextNode.ACenter, text_pos=(0.0, -0.0), text_scale=0.1, text_fg=(1, 1, 1, 1), text_shadow=(0, 0, 0, 1), image=(shovelCardP,
         shovelCardY,
         shovelCardY,
         shovelCardY), image_scale=(0.18, 1.0, 0.36), geom=None, geom_scale=iconScale, geom_color=iconColorWhite, pos=(0, 0, 0.2), scale=0.775, command=self.__shovelButtonClicked)
        self.shovelButton = self.__shovelButton
        iconGeom = iconModels.find('**/teleportIcon')
        buttonText = TTLocalizer.GardeningWater
        self.waterText = (buttonText,
         buttonText,
         buttonText,
         '')
        self.__wateringCanButtonFake = DirectLabel(parent=self.__gardeningGuiFake, relief=None, text=self.waterText, text_align=TextNode.ALeft, text_pos=(0.0, -0.0), text_scale=0.07, text_fg=(1, 1, 1, 1), text_shadow=(0, 0, 0, 1), image_scale=(0.18, 1.0, 0.36), geom=None, geom_scale=iconScale, geom_color=iconColorWhite, pos=(0.15, 0, 0.01), scale=0.775)
        self.wateringCanButtonFake = self.__wateringCanButtonFake
        self.__wateringCanButton = DirectButton(parent=self.__gardeningGui, relief=None, text=self.waterText, text_align=TextNode.ACenter, text_pos=(0.0, -0.0), text_scale=0.1, text_fg=(1, 1, 1, 1), text_shadow=(0, 0, 0, 1), image=(wateringCanCardP,
         wateringCanCardY,
         wateringCanCardY,
         wateringCanCardY), image_scale=(0.18, 1.0, 0.36), geom=None, geom_scale=iconScale, geom_color=iconColorWhite, pos=(0, 0, 0.01), scale=0.775, command=self.__wateringCanButtonClicked)
        self.wateringCanButton = self.__wateringCanButton
        self.basketText = '%s / %s' % (self.numFlowers, self.maxFlowerBasket)
        self.basketButton = DirectLabel(parent=self.__gardeningGui, relief=None, text=self.basketText, text_align=TextNode.ALeft, text_pos=(0.82, -1.4), text_scale=0.2, text_fg=(1, 1, 1, 1), text_shadow=(0, 0, 0, 1), image=None, image_scale=iconScale, geom=None, geom_scale=iconScale, geom_color=iconColorWhite, pos=(-0.34, 0, 0.16), scale=0.3, textMayChange=1)
        if hasattr(self, 'shovel'):
            self.setShovelGuiLevel(self.shovel)
        if hasattr(self, 'wateringCan'):
            self.setWateringCanGuiLevel(self.wateringCan)
        self.__shovelButton.hide()
        self.__wateringCanButton.hide()
        self.__shovelButtonFake.hide()
        self.__wateringCanButtonFake.hide()
        return

    def changeButtonText(self, button, text):
        button['text'] = text

    def resetWaterText(self):
        self.wateringCanButton['text'] = self.waterText

    def resetShovelText(self):
        self.shovelButton['text'] = self.holdShovelText

    def showGardeningGui(self):
        self.loadGardeningGui()
        self.__gardeningGui.show()
        base.setCellsAvailable([base.leftCells[2]], 0)

    def hideGardeningGui(self):
        if self.__gardeningGui:
            self.__gardeningGui.hide()
            base.setCellsAvailable([base.leftCells[2]], 1)

    def showShovelButton(self, add = 0):
        if add:
            self.shovelButtonActiveCount += add
        else:
            self.showingShovel = 1
        self.notify.debug('showing shovel %s' % self.shovelButtonActiveCount)
        self.__gardeningGui.show()
        self.__shovelButton.show()

    def hideShovelButton(self, deduct = 0):
        self.shovelButtonActiveCount -= deduct
        if deduct == 0:
            self.showingShovel = 0
        if self.shovelButtonActiveCount < 1:
            self.shovelButtonActiveCount = 0
            if self.showingShovel == 0:
                self.__shovelButton.hide()
            self.handleAllGardeningButtonsHidden()
        self.notify.debug('hiding shovel %s' % self.shovelButtonActiveCount)

    def showWateringCanButton(self, add = 0):
        if add:
            self.wateringCanButtonActiveCount += add
        else:
            self.showingWateringCan = 1
        self.__gardeningGui.show()
        self.__wateringCanButton.show()
        self.basketButton.show()

    def hideWateringCanButton(self, deduct = 0):
        self.wateringCanButtonActiveCount -= deduct
        if deduct == 0:
            self.showingWateringCan = 0
        if self.wateringCanButtonActiveCount < 1:
            wateringCanButtonActiveCount = 0
            if self.showingWateringCan == 0:
                self.__wateringCanButton.hide()
            self.handleAllGardeningButtonsHidden()

    def showWateringCanButtonFake(self, add = 0):
        self.__wateringCanButtonFake.show()

    def hideWateringCanButtonFake(self, deduct = 0):
        self.__wateringCanButtonFake.hide()

    def showShovelButtonFake(self, add = 0):
        self.__shovelButtonFake.show()

    def hideShovelButtonFake(self, deduct = 0):
        self.__shovelButtonFake.hide()

    def levelWater(self, change = 1):
        if change < 0:
            return
        self.showWateringCanButtonFake(1)
        if change < 1:
            changeString = TTLocalizer.GardeningNoSkill
        else:
            changeString = '+%s %s' % (change, TTLocalizer.GardeningWaterSkill)
        self.waterTrack = Sequence(Wait(0.0), Func(self.changeButtonText, self.wateringCanButtonFake, changeString), SoundInterval(globalBattleSoundCache.getSound('GUI_balloon_popup.ogg'), node=self), Wait(1.0), Func(self.hideWateringCanButtonFake, 1))
        self.waterTrack.start()

    def levelShovel(self, change = 1):
        if change < 1:
            return
        self.showShovelButtonFake(1)
        if change < 1:
            changeString = TTLocalizer.GardeningNoSkill
        else:
            changeString = '+%s %s' % (change, TTLocalizer.GardeningShovelSkill)
        plant = base.cr.doId2do.get(self.shovelRelatedDoId)
        if plant:
            self.holdShovelText = plant.getShovelAction()
        self.shovelTrack = Sequence(Wait(0.0), Func(self.changeButtonText, self.shovelButtonFake, changeString), SoundInterval(globalBattleSoundCache.getSound('GUI_balloon_popup.ogg'), node=self), Wait(1.0), Func(self.hideShovelButtonFake, 1))
        self.shovelTrack.start()

    def setGuiConflict(self, con):
        self.guiConflict = con

    def getGuiConflict(self, con):
        return self.guiConflict

    def verboseState(self):
        self.lastPlaceState = 'None'
        taskMgr.add(self.__expressState, 'expressState', extraArgs=[])

    def __expressState(self, task = None):
        place = base.cr.playGame.getPlace()
        if place:
            state = place.fsm.getCurrentState()
            if state.getName() != self.lastPlaceState:
                print('Place State Change From %s to %s' % (self.lastPlaceState, state.getName()))
                self.lastPlaceState = state.getName()
        return Task.cont

    def addShovelRelatedDoId(self, doId):
        if hasattr(base.cr.playGame.getPlace(), 'detectedGardenPlotDone'):
            place = base.cr.playGame.getPlace()
            state = place.fsm.getCurrentState()
            if state.getName() == 'stopped':
                return
        self.touchingPlantList.append(doId)
        self.autoSetActivePlot()

    def removeShovelRelatedDoId(self, doId):
        if doId in self.touchingPlantList:
            self.touchingPlantList.remove(doId)
        self.autoSetActivePlot()

    def autoSetActivePlot(self):
        if self.guiConflict:
            return
        if len(self.touchingPlantList) > 0:
            minDist = 10000
            minDistPlot = 0
            for plot in self.touchingPlantList:
                plant = base.cr.doId2do.get(plot)
                if plant:
                    if self.getDistance(plant) < minDist:
                        minDist = self.getDistance(plant)
                        minDistPlot = plot
                else:
                    self.touchingPlantList.remove(plot)

            if len(self.touchingPlantList) == 0:
                self.setActivePlot(None)
            else:
                self.setActivePlot(minDistPlot)
        else:
            self.setActivePlot(None)
        return

    def setActivePlot(self, doId):
        if not self.gardenStarted:
            return
        self.shovelRelatedDoId = doId
        plant = base.cr.doId2do.get(doId)
        if plant:
            self.startStareAt(plant, Point3(0, 0, 1))
            self.__shovelButton['state'] = DGG.NORMAL
            if not plant.canBePicked():
                self.hideShovelButton()
            else:
                self.showShovelButton()
                self.setShovelAbility(TTLocalizer.GardeningPlant)
                if plant.getShovelAction():
                    self.setShovelAbility(plant.getShovelAction())
                    if plant.getShovelAction() == TTLocalizer.GardeningPick:
                        if not plant.unlockPick():
                            self.__shovelButton['state'] = DGG.DISABLED
                            self.setShovelAbility(TTLocalizer.GardeningFull)
                self.notify.debug('self.shovelRelatedDoId = %d' % self.shovelRelatedDoId)
                if plant.getShovelCommand():
                    self.extraShovelCommand = plant.getShovelCommand()
                    self.__shovelButton['command'] = self.__shovelButtonClicked
            if plant.canBeWatered():
                self.showWateringCanButton()
            else:
                self.hideWateringCanButton()
        else:
            self.stopStareAt()
            self.shovelRelatedDoId = 0
            if self.__shovelButton:
                self.__shovelButton['command'] = None
                self.hideShovelButton()
                self.hideWateringCanButton()
                self.handleAllGardeningButtonsHidden()
                if not self.inGardenAction:
                    if hasattr(base.cr.playGame.getPlace(), 'detectedGardenPlotDone'):
                        place = base.cr.playGame.getPlace()
                        if place:
                            place.detectedGardenPlotDone()
        return

    def setPlantToWater(self, plantId):
        import pdb
        pdb.set_trace()
        if self.plantToWater == None:
            self.plantToWater = plantId
            self.notify.debug('setting plant to water %s' % plantId)
        return

    def clearPlantToWater(self, plantId):
        if not hasattr(self, 'secondaryPlant'):
            self.secondaryWaterPlant = None
        if self.plantToWater == plantId:
            self.plantToWater = None
            self.hideWateringCanButton()
        return

    def hasPlant(self):
        if self.plantToWater != None:
            return 1
        else:
            return 0
        return

    def handleAllGardeningButtonsHidden(self):
        somethingVisible = False
        if not self.__shovelButton.isHidden():
            somethingVisible = True
        if not self.__wateringCanButton.isHidden():
            somethingVisible = True
        if not somethingVisible:
            self.hideGardeningGui()

    def setShovelAbility(self, ability):
        self.shovelAbility = ability
        if self.__shovelButton:
            self.__shovelButton['text'] = ability

    def setFlowerBasket(self, speciesList, varietyList):
        DistributedToon.DistributedToon.setFlowerBasket(self, speciesList, varietyList)
        self.numFlowers = len(self.flowerBasket.flowerList)
        self.maxFlowerBasket
        if hasattr(self, 'basketButton'):
            self.basketText = '%s / %s' % (self.numFlowers, self.maxFlowerBasket)
            self.basketButton['text'] = self.basketText

    def setShovelSkill(self, skillLevel):
        if hasattr(self, 'shovelSkill') and hasattr(self, 'shovelButton'):
            if self.shovelSkill != None:
                self.levelShovel(skillLevel - self.shovelSkill)
        oldShovelSkill = self.shovelSkill
        DistributedToon.DistributedToon.setShovelSkill(self, skillLevel)
        if hasattr(self, 'shovel'):
            oldShovelPower = GardenGlobals.getShovelPower(self.shovel, oldShovelSkill)
            newShovelPower = GardenGlobals.getShovelPower(self.shovel, self.shovelSkill)
            almostMaxedSkill = GardenGlobals.ShovelAttributes[GardenGlobals.MAX_SHOVELS - 1]['skillPts'] - 2
            if skillLevel >= GardenGlobals.ShovelAttributes[self.shovel]['skillPts']:
                self.promoteShovel()
            elif oldShovelSkill and oldShovelPower < newShovelPower:
                self.promoteShovelSkill(self.shovel, self.shovelSkill)
            elif oldShovelSkill == almostMaxedSkill and newShovelPower == GardenGlobals.getNumberOfShovelBoxes():
                self.promoteShovelSkill(self.shovel, self.shovelSkill)
        return

    def setWateringCanSkill(self, skillLevel):
        skillDelta = skillLevel - self.wateringCanSkill
        if skillDelta or 1:
            if hasattr(self, 'wateringCanSkill') and hasattr(self, 'wateringCanButton'):
                if self.wateringCanSkill != None:
                    self.levelWater(skillDelta)
            DistributedToon.DistributedToon.setWateringCanSkill(self, skillLevel)
            if hasattr(self, 'wateringCan'):
                if skillLevel >= GardenGlobals.WateringCanAttributes[self.wateringCan]['skillPts']:
                    self.promoteWateringCan()
        return

    def unlockGardeningButtons(self, task = None):
        if hasattr(self, '_LocalToon__shovelButton'):
            try:
                self.__shovelButton['state'] = DGG.NORMAL
            except TypeError:
                self.notify.warning('Could not unlock the shovel button- Type Error')

        if hasattr(self, '_LocalToon__wateringCanButton'):
            try:
                self.__wateringCanButton['state'] = DGG.NORMAL
            except TypeError:
                self.notify.warning('Could not unlock the watering can button - Type Error')

        taskMgr.remove('unlockGardenButtons')
        return None

    def lockGardeningButtons(self, task = None):
        if hasattr(self, '_LocalToon__shovelButton'):
            try:
                self.__shovelButton['state'] = DGG.DISABLED
            except TypeError:
                self.notify.warning('Could not lock the shovel button- Type Error')

        if hasattr(self, '_LocalToon__wateringCanButton'):
            try:
                self.__wateringCanButton['state'] = DGG.DISABLED
            except TypeError:
                self.notify.warning('Could not lock the watering can button - Type Error')

        self.accept('endPlantInteraction', self.__handleEndPlantInteraction)
        return None

    def reactivateShovel(self, task = None):
        if hasattr(self, '_LocalToon__shovelButton'):
            self.__shovelButton['state'] = DGG.NORMAL
        taskMgr.remove('reactShovel')
        return None

    def reactivateWater(self, task = None):
        if hasattr(self, '_LocalToon__wateringCanButton'):
            self.__wateringCanButton['state'] = DGG.NORMAL
        taskMgr.remove('reactWater')
        return None

    def handleEndPlantInteraction(self, object = None, replacement = 0):
        if not replacement:
            self.setInGardenAction(None, object)
            self.autoSetActivePlot()
        return

    def __handleEndPlantInteraction(self, task = None):
        self.setInGardenAction(None)
        self.autoSetActivePlot()
        return

    def promoteShovelSkill(self, shovelLevel, shovelSkill):
        shovelName = GardenGlobals.ShovelAttributes[shovelLevel]['name']
        shovelBeans = GardenGlobals.getShovelPower(shovelLevel, shovelSkill)
        oldShovelBeans = GardenGlobals.getShovelPower(shovelLevel, shovelSkill - 1)
        doPartyBall = False
        message = TTLocalizer.GardenShovelSkillLevelUp % {'shovel': shovelName,
         'oldbeans': oldShovelBeans,
         'newbeans': shovelBeans}
        if shovelBeans == GardenGlobals.getNumberOfShovelBoxes():
            if shovelSkill == GardenGlobals.ShovelAttributes[shovelLevel]['skillPts'] - 1:
                doPartyBall = True
                message = TTLocalizer.GardenShovelSkillMaxed % {'shovel': shovelName,
                 'oldbeans': oldShovelBeans,
                 'newbeans': shovelBeans}
        messagePos = Vec2(0, 0.2)
        messageScale = 0.07
        image = loader.loadModel('phase_5.5/models/gui/planting_but_shovel_P')
        imagePos = Vec3(0, 0, -0.13)
        imageScale = Vec3(0.28, 0, 0.56)
        if doPartyBall:
            go = Fanfare.makeFanfareWithMessageImage(0, base.localAvatar, 1, message, Vec2(0, 0.2), 0.08, image, Vec3(0, 0, -0.1), Vec3(0.35, 0, 0.7), wordwrap=23)
            Sequence(go[0], Func(go[1].show), LerpColorScaleInterval(go[1], duration=0.5, startColorScale=Vec4(1, 1, 1, 0), colorScale=Vec4(1, 1, 1, 1)), Wait(10), LerpColorScaleInterval(go[1], duration=0.5, startColorScale=Vec4(1, 1, 1, 1), colorScale=Vec4(1, 1, 1, 0)), Func(go[1].remove)).start()
        else:
            go = Fanfare.makePanel(base.localAvatar, 1)
            Fanfare.makeMessageBox(go, message, messagePos, messageScale, wordwrap=24)
            Fanfare.makeImageBox(go.itemFrame, image, imagePos, imageScale)
            Sequence(Func(go.show), LerpColorScaleInterval(go, duration=0.5, startColorScale=Vec4(1, 1, 1, 0), colorScale=Vec4(1, 1, 1, 1)), Wait(10), LerpColorScaleInterval(go, duration=0.5, startColorScale=Vec4(1, 1, 1, 1), colorScale=Vec4(1, 1, 1, 0)), Func(go.remove)).start()

    def promoteShovel(self, shovelLevel = 0):
        shovelName = GardenGlobals.ShovelAttributes[shovelLevel]['name']
        shovelBeans = GardenGlobals.getShovelPower(shovelLevel, 0)
        message = TTLocalizer.GardenShovelLevelUp % {'shovel': shovelName,
         'oldbeans': shovelBeans - 1,
         'newbeans': shovelBeans}
        messagePos = Vec2(0, 0.2)
        messageScale = 0.07
        image = loader.loadModel('phase_5.5/models/gui/planting_but_shovel_P')
        imagePos = Vec3(0, 0, -0.13)
        imageScale = Vec3(0.28, 0, 0.56)
        go = Fanfare.makePanel(base.localAvatar, 1)
        Fanfare.makeMessageBox(go, message, messagePos, messageScale, wordwrap=24)
        Fanfare.makeImageBox(go.itemFrame, image, imagePos, imageScale)
        Sequence(Func(go.show), LerpColorScaleInterval(go, duration=0.5, startColorScale=Vec4(1, 1, 1, 0), colorScale=Vec4(1, 1, 1, 1)), Wait(10), LerpColorScaleInterval(go, duration=0.5, startColorScale=Vec4(1, 1, 1, 1), colorScale=Vec4(1, 1, 1, 0)), Func(go.remove)).start()

    def promoteWateringCan(self, wateringCanlevel = 0):
        message = TTLocalizer.GardenWateringCanLevelUp + ' \n' + GardenGlobals.WateringCanAttributes[wateringCanlevel]['name']
        messagePos = Vec2(0, 0.2)
        messageScale = 0.08
        image = loader.loadModel('phase_5.5/models/gui/planting_but_can_P')
        imagePos = Vec3(0, 0, -0.1)
        imageScale = Vec3(0.35, 0, 0.7)
        if wateringCanlevel >= GardenGlobals.MAX_WATERING_CANS - 1:
            go = Fanfare.makeFanfareWithMessageImage(0, base.localAvatar, 1, message, Vec2(0, 0.2), 0.08, image, Vec3(0, 0, -0.1), Vec3(0.35, 0, 0.7))
            Sequence(go[0], Func(go[1].show), LerpColorScaleInterval(go[1], duration=0.5, startColorScale=Vec4(1, 1, 1, 0), colorScale=Vec4(1, 1, 1, 1)), Wait(5), LerpColorScaleInterval(go[1], duration=0.5, startColorScale=Vec4(1, 1, 1, 1), colorScale=Vec4(1, 1, 1, 0)), Func(go[1].remove)).start()
        else:
            go = Fanfare.makePanel(base.localAvatar, 1)
            Fanfare.makeMessageBox(go, message, messagePos, messageScale)
            Fanfare.makeImageBox(go.itemFrame, image, imagePos, imageScale)
            Sequence(Func(go.show), LerpColorScaleInterval(go, duration=0.5, startColorScale=Vec4(1, 1, 1, 0), colorScale=Vec4(1, 1, 1, 1)), Wait(5), LerpColorScaleInterval(go, duration=0.5, startColorScale=Vec4(1, 1, 1, 1), colorScale=Vec4(1, 1, 1, 0)), Func(go.remove)).start()

    def setInGardenAction(self, actionObject, fromObject = None):
        if actionObject:
            self.lockGardeningButtons()
        elif fromObject:
            self.unlockGardeningButtons()
        else:
            self.unlockGardeningButtons()
        self.inGardenAction = actionObject

    def __wateringCanButtonClicked(self):
        self.notify.debug('wateringCanButtonClicked')
        if self.inGardenAction:
            return
        plant = base.cr.doId2do.get(self.shovelRelatedDoId)
        if plant:
            if hasattr(plant, 'handleWatering'):
                plant.handleWatering()
        messenger.send('wakeup')

    def __shovelButtonClicked(self):
        if self.inGardenAction:
            return
        self.notify.debug('shovelButtonClicked')
        messenger.send('wakeup')
        thingId = self.shovelRelatedDoId
        thing = base.cr.doId2do.get(thingId)
        if hasattr(self, 'extraShovelCommand'):
            self.extraShovelCommand()
            self.setActivePlot(thingId)

    def setShovel(self, shovelId):
        DistributedToon.DistributedToon.setShovel(self, shovelId)
        if self.__gardeningGui:
            self.setShovelGuiLevel(shovelId)

    def setWateringCan(self, wateringCanId):
        DistributedToon.DistributedToon.setWateringCan(self, wateringCanId)
        if self.__gardeningGui:
            self.setWateringCanGuiLevel(wateringCanId)

    def setGardenStarted(self, bStarted):
        self.gardenStarted = bStarted
        if self.gardenStarted and not self.gardenPage and hasattr(self, 'book'):
            self.loadGardenPages()

    def b_setAnimState(self, animName, animMultiplier = 1.0, callback = None, extraArgs = []):
        if self.wantStatePrint:
            print('Local Toon Anim State %s' % animName)
        DistributedToon.DistributedToon.b_setAnimState(self, animName, animMultiplier, callback, extraArgs)

    def swimTimeoutAction(self):
        self.ignore('wakeup')
        self.takeOffTransformation()
        base.cr.playGame.getPlace().fsm.request('final')
        self.b_setAnimState('TeleportOut', 1, self.__handleSwimExitTeleport, [0])
        return Task.done

    def __handleSwimExitTeleport(self, requestStatus):
        self.notify.info('closing shard...')
        base.cr.gameFSM.request('closeShard', ['afkTimeout'])

    def sbFriendAdd(self, id, info):
        print('sbFriendAdd')

    def sbFriendUpdate(self, id, info):
        print('sbFriendUpdate')

    def sbFriendRemove(self, id):
        print('sbFriendRemove')

    def addGolfPage(self):
        if self.hasPlayedGolf():
            if hasattr(self, 'golfPage') and self.golfPage != None:
                return
            if not launcher.getPhaseComplete(6):
                self.acceptOnce('phaseComplete-6', self.addGolfPage)
                return
            self.golfPage = GolfPage.GolfPage()
            self.golfPage.setAvatar(self)
            self.golfPage.load()
            self.book.addPage(self.golfPage, pageName=TTLocalizer.GolfPageTitle)
        return

    def addEventsPage(self):
        if hasattr(self, 'eventsPage') and self.eventsPage != None:
            return
        if not launcher.getPhaseComplete(4):
            self.acceptOnce('phaseComplete-4', self.addEventsPage)
            return
        self.eventsPage = EventsPage.EventsPage()
        self.eventsPage.load()
        self.book.addPage(self.eventsPage, pageName=TTLocalizer.EventsPageName)
        return

    def addNewsPage(self):
        self.newsPage = NewsPage.NewsPage()
        self.newsPage.load()
        self.book.addPage(self.newsPage, pageName=TTLocalizer.NewsPageName)

    def addTIPPage(self):
        self.tipPage = TIPPage.TIPPage()
        self.tipPage.load()
        self.book.addPage(self.tipPage, pageName=TTLocalizer.TIPPageTitle)

    def setPinkSlips(self, pinkSlips):
        DistributedToon.DistributedToon.setPinkSlips(self, pinkSlips)
        self.inventory.updateTotalPropsText()

    def getAccountDays(self):
        days = 0
        defaultDays = base.cr.config.GetInt('account-days', -1)
        if defaultDays >= 0:
            days = defaultDays
        elif hasattr(base.cr, 'accountDays'):
            days = base.cr.accountDays
        return days

    def hasActiveBoardingGroup(self):
        if hasattr(localAvatar, 'boardingParty') and localAvatar.boardingParty:
            return localAvatar.boardingParty.hasActiveGroup(localAvatar.doId)
        else:
            return False

    def getZoneId(self):
        return self._zoneId

    def setZoneId(self, value):
        if value == -1:
            self.notify.error('zoneId should not be set to -1, tell Redmond')
        self._zoneId = value

    zoneId = property(getZoneId, setZoneId)

    def systemWarning(self, warningText = 'Acknowledge this system message.'):
        self.createSystemMsgAckGui()
        self.systemMsgAckGui['text'] = warningText
        self.systemMsgAckGui.show()

    def createSystemMsgAckGui(self):
        if self.systemMsgAckGui == None or self.systemMsgAckGui.isEmpty():
            message = 'o' * 100
            self.systemMsgAckGui = TTDialog.TTGlobalDialog(doneEvent=self.systemMsgAckGuiDoneEvent, message=message, style=TTDialog.Acknowledge)
            self.systemMsgAckGui.hide()
        return

    def hideSystemMsgAckGui(self):
        if self.systemMsgAckGui != None and not self.systemMsgAckGui.isEmpty():
            self.systemMsgAckGui.hide()
        return

    def setSleepAutoReply(self, fromId):
        avatar = base.cr.identifyAvatar(fromId)
        if avatar:
            base.localAvatar.setSystemMessage(0, TTLocalizer.SleepAutoReply % avatar.getName(), WhisperPopup.WTToontownBoardingGroup)

    def setLastTimeReadNews(self, newTime):
        self.lastTimeReadNews = newTime

    def getLastTimeReadNews(self):
        return self.lastTimeReadNews

    def cheatCogdoMazeGame(self, kindOfCheat = 0):
        if base.config.GetBool('allow-cogdo-maze-suit-hit-cheat'):
            maze = base.cr.doFind('DistCogdoMazeGame')
            if maze:
                if kindOfCheat == 0:
                    for suitNum in list(maze.game.suitsById.keys()):
                        suit = maze.game.suitsById[suitNum]
                        maze.sendUpdate('requestSuitHitByGag', [suit.type, suitNum])

                elif kindOfCheat == 1:
                    for joke in maze.game.pickups:
                        maze.sendUpdate('requestPickUp', [joke.serialNum])

        else:
            self.sendUpdate('logSuspiciousEvent', ['cheatCogdoMazeGame'])

    def isReadingNews(self):
        result = False
        if base.cr and base.cr.playGame and base.cr.playGame.getPlace() and hasattr(base.cr.playGame.getPlace(), 'fsm') and base.cr.playGame.getPlace().fsm:
            fsm = base.cr.playGame.getPlace().fsm
            curState = fsm.getCurrentState().getName()
            if curState == 'stickerBook' and WantNewsPage:
                if hasattr(self, 'newsPage'):
                    if self.book.isOnPage(self.newsPage):
                        result = True
        return result

    def startQuestMap(self):
        if self.questMap:
            self.questMap.start()

    def stopQuestMap(self):
        if self.questMap:
            self.questMap.stop()

    def _startZombieCheck(self):
        pass

    def _stopZombieCheck(self):
        pass

    def returnToWalk(self, task):
        # Fixes that old bug
        # where the fall impact animation
        # froze the toon in place
        if hasattr(self, 'animFSM') and self.animFSM.getCurrentState().getName() in ('CloseBook', 'TeleportOut', 'jump'):
            return task.done
        return LocalAvatar.LocalAvatar.returnToWalk(self, task)

    def enableAvatarControls(self):
        LocalAvatar.LocalAvatar.enableAvatarControls(self)
        self.controlManager.setStrafing(self.firstPerson)

    def collisionsOff(self):
        self.pauseGlitchKiller()
        LocalAvatar.LocalAvatar.collisionsOff(self)

    def collisionsOn(self):
        self.unpauseGlitchKiller()
        LocalAvatar.LocalAvatar.collisionsOn(self)

    if __debug__ and platform.system() == 'Windows' and os.environ.get('COMPUTERNAME') == 'DESKTOP-6NC6GHJ':
        def copyPosHpr(self):
            renderPos = self.getPos(render)
            renderHpr = self.getHpr(render)
            toonPosStr = f'Point3({renderPos[0]:.2f}, {renderPos[1]:.2f}, {renderPos[2]:.2f})'
            toonHprStr = f'Point3({renderHpr[0] % 360:.2f}, {renderHpr[1] % 360:.2f}, {renderHpr[2] % 360:.2f})'
            clipboard.copy(f'{toonPosStr}, {toonHprStr}')

    def handlePlayerBanned(self, avId):
        chatBar = loader.loadModel('phase_3.5/models/gui/ttoff_m_gui_chatPanel')
        unitesIcon = chatBar.find('**/chatbar_unites_normal')
        self.sendNotification(title = TTLocalizer.NotificationTitleBanned, body = TTLocalizer.NotificationBodyBanned, icon = unitesIcon, id = "player_banned")
        chatBar.removeNode()
