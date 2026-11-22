##################################################
# The Toontown Realms Magic Word Manager
##################################################
# Author: Benjamin Frisby
# Copyright: Copyright 2021, Toontown Realms
# Credits: Benjamin Frisby, John Cote, William Lord, Frank, Nick, Little Cat, Ooowoo
# License: MIT
# Version: 1.0.0
# Email: belloqzafarian@gmail.com
##################################################

import collections
import datetime
from typing import List, Optional, Union, Tuple

from direct.interval.IntervalGlobal import *
from direct.showbase.DirectObject import DirectObject

from panda3d.toontown import NametagGroup, WhisperPopup

from .MagicWordGlobals import *
from ..datapack.DataPackManager import DataPackManager
from ..sandbox import PropGlobals
from otp.otpbase import OTPLocalizer, OTPGlobals

from toontown.coghq import CogDisguiseGlobals
from toontown.effects.FilterManager import FilterManager
from toontown.estate import GardenGlobals
from toontown.fishing import FishGlobals
from toontown.golf import GolfGlobals
from toontown.hood import ZoneUtil
from toontown.makeatoon import NameGenerator
from toontown.minigame import MinigameGlobals
from toontown.parties import PartyGlobals
from toontown.racing.KartDNA import *
from toontown.racing import RaceGlobals
from toontown.safezone import DistributedSZTreasure
from toontown.shtiker import CogPageGlobals
from toontown.suit import SuitDNA
from toontown.toon import NPCToons, Experience, ToonDNA, DropPropGlobals
from toontown.toonbase import ToontownBattleGlobals, ToontownGlobals, TTLocalizer, ToontownTimer, ServerSettings, ClientSettings

from . import MagicWordConfig
from functools import partial
import time
import random
import re
import json
import os
import base64

from ..sandbox.BuildLotGlobals import BuildLotThemes
from ..toonbase.TTLocalizerEnglish import HolidayNamesInCalendar
from ..toonbase.ToontownTypes import CogAppearanceIndex

if game.process == 'client':
    from ..sandbox.DistributedPropGenerator import DistributedPropGenerator

magicWordIndex = collections.OrderedDict()

DUMP_WORDS = False

class MagicWord(DirectObject):
    notify = DirectNotifyGlobal.directNotify.newCategory('MagicWord')

    # Whether this Magic word should be considered "hidden". This impacts if it is shown on the Magic Word page.
    hidden = False

    # Whether this Magic Word is an administrative command or not.
    # Administrative commands will be allowed on "Legit" servers.
    # Only these commands can be used on caged Toons.
    administrative = False

    # List of names that will also invoke this word - a setHP magic word might have "hp", for example.
    # A Magic Word will always be callable with its class name, so you don't have to put that in the aliases.
    aliases = None

    # Description of the Magic Word for use in the Shtikerbook.
    desc = MagicWordConfig.MAGIC_WORD_DEFAULT_DESC

    # Advanced description that gives the user a lot more information than normal.
    advancedDesc = MagicWordConfig.MAGIC_WORD_DEFAULT_ADV_DESC

    # Default example with for commands with no arguments set.
    example = ""

    # A cooldown before you're allowed to use the Magic Word again.
    # Does not apply to those with MODERATOR Access Level and above.
    cooldown = None

    # The minimum access level required to use this Magic Word. By default, USER.
    accessLevel = 'USER'

    # A restriction on the Magic Word which sets what kind or set of Distributed Objects it can be used on. By
    # default, AFFECT_EVERYONE.
    affectRange = [MagicWordConfig.AFFECT_SELF, MagicWordConfig.AFFECT_OTHER, MagicWordConfig.AFFECT_BOTH]

    # Whether you are allowed to target any Toon with this Magic Word. By default, False.
    anyTarget = False

    # Where the magic word will be executed -- EXEC_LOC_CLIENT or EXEC_LOC_SERVER.
    execLocation = MagicWordConfig.EXEC_LOC_INVALID

    # List of all arguments for this word, with the format [(type, isRequired), (type, isRequired)...]
    # If the parameter is not required, you must provide a default argument: (type, False, default).
    arguments = None

    def __init__(self):
        if self.__class__.__name__ != "MagicWord":  # If not the base class,
            self.air = None
            self.cr = None
            self.invokerId = None
            self.targets = None
            self.args = None

            self.aliases = self.aliases if self.aliases is not None else []  # if we use [] by default, it might get
            # overwritten
            self.aliases.insert(0, self.__class__.__name__)  # add the class name to the alias list,
            self.aliases = [x.lower() for x in self.aliases]  # make all the aliases lowercase,
            self.arguments = self.arguments if self.arguments is not None else []

            if len(self.arguments) > 0 and not self.example:
                for arg in self.arguments:
                    argInfo = ""
                    if not arg[MagicWordConfig.ARGUMENT_REQUIRED]:
                        argInfo += "(default: {0})".format(arg[MagicWordConfig.ARGUMENT_DEFAULT])
                    self.example += "[{0}{1}] ".format(arg[MagicWordConfig.ARGUMENT_NAME], argInfo)
            if DUMP_WORDS:
                with open('words.md', 'a') as wordsTxt:
                    argsL = []
                    argsOpts = []

                    if len(self.arguments) > 0:
                        for arg in self.arguments:

                            emptStr = '""'
                            if len(arg) == 4:
                                argsL.append(f'`[{arg[0]}: {arg[1].__name__} = {arg[3] if arg[3] != "" else emptStr}]`')
                            else:
                                argsL.append(f'`{arg[0]}: {arg[1].__name__}`')

                            #if self.getValidValuesForArg(self.arguments.index(arg)) is not None:
                            #    argsOpts.append()

                    wordsTxt.write(f'### {self.__class__.__name__} ({", ".join(argsL)})\n'
                                   f'*Aliases: {self.aliases}*\n'
                                   f'> {self.desc}\n' +
                                   (f'\n{self.advancedDesc}\n\n\n---\n' if self.advancedDesc != MagicWordConfig.MAGIC_WORD_DEFAULT_ADV_DESC else "\n\n---\n"))

            self.__register()  # and register the magic word.

    def __register(self):
        for wordName in self.aliases:
            if wordName in magicWordIndex:
                self.notify.error('Duplicate Magic Word name or alias detected! Invalid name: {}'.format(wordName))
            magicWordIndex[wordName] = {'class': self,
                                        'classname': self.__class__.__name__,
                                        'hidden': self.hidden,
                                        'administrative': self.administrative,
                                        'aliases': self.aliases,
                                        'desc': self.desc,
                                        'advancedDesc': self.advancedDesc,
                                        'example': self.example,
                                        'execLocation': self.execLocation,
                                        'cooldown': self.cooldown,
                                        'access': self.accessLevel,
                                        'affectRange': self.affectRange,
                                        'anyTarget': self.anyTarget,
                                        'args': self.arguments
                                        }

    def loadWord(self, air = None, cr = None, invokerId = None, targets = None, args = None):
        self.air = air
        self.cr = cr
        self.invokerId = invokerId
        self.targets = targets
        self.args = args

    def executeWord(self):
        executedWord = None
        validTargets = len(self.targets)
        for avId in self.targets:
            invoker = None
            toon = None
            if self.air:
                invoker = self.air.doId2do.get(self.invokerId)
                toon = self.air.doId2do.get(avId)
            elif self.cr:
                invoker = self.cr.doId2do.get(self.invokerId)
                toon = self.cr.doId2do.get(avId)
            if hasattr(toon, "getName"):
                name = toon.getName()
            else:
                name = avId

            if not self.validateTarget(toon):
                if len(self.targets) > 1:
                    validTargets -= 1
                    continue
                return "{} is not a valid target!".format(name)

            if toon.getLocked() and not self.administrative:
                if len(self.targets) > 1:
                    validTargets -= 1
                    continue
                return "{} is currently locked. You can only use administrative commands on them.".format(name)

            # Hacky way for referencing anyTarget for spellbook.json changes
            # TODO: Change how it works
            anyTarget = magicWordIndex[self.__class__.__name__.lower()]['anyTarget']

            if (invoker.getAccessLevel() <= toon.getAccessLevel()) and (toon != invoker) and (not anyTarget):
                if len(self.targets) > 1:
                    validTargets -= 1
                    continue
                targetAccess = toon.getAccessLevel()
                invokerAccess = invoker.getAccessLevel()
                return "You don't have enough Access to target {}!\nThem: {}.\nYou: {}.".format(name, targetAccess,
                                                                                                invokerAccess)

            if self.execLocation == MagicWordConfig.EXEC_LOC_CLIENT:
                self.args = json.loads(self.args)

            executedWord = self.handleWord(invoker, avId, toon, *self.args)

        # If you're only using the Magic Word on one person and there is a response, return that response
        if executedWord and len(self.targets) == 1:
            return executedWord

        # If the amount of targets is higher than one...
        elif validTargets > 0:

            # And it's only 1, and that's yourself, return None
            if validTargets == 1 and self.invokerId in self.targets:
                return None

            # Otherwise, state how many targets you executed it on
            return "Magic Word successfully executed on %s target(s)." % validTargets

        else:
            return "Magic Word unable to execute on any targets."

    def validateTarget(self, target):
        if self.air:
            from toontown.toon.DistributedToonAI import DistributedToonAI
            return isinstance(target, DistributedToonAI)
        elif self.cr:
            from toontown.toon.DistributedToon import DistributedToon
            return isinstance(target, DistributedToon)
        return False

    def handleWord(self, invoker, avId: int, toon, *args):
        raise NotImplementedError('Must be overridden by subclass.')

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        return None

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        valid = True
        argType = self.arguments[arg][1]

        ## If it's optional, don't flag it as red if its blank
        #if not self.arguments[arg][2] and len(entry) == 0:
        #    return True

        if argType == int:
            # Validate integers
            try:
                int(entry)
                valid = True
            except ValueError:
                valid = False

        elif argType == float:
            # Validate floats
            try:
                float(entry)
                valid = True
            except ValueError:
                valid = False

        elif argType == str:
            valid = True

        # If we got the right, type, let's see if its actually a valid value
        if valid:
            if self.getValidValuesForArg(arg):
                valid = entry in (x[0] for x in self.getValidValuesForArg(arg))
        return valid


# When creating new Magic Words, please try to use a consistent naming etiquette. Here are some rules we should follow:

# Restock - If a word gives you an item that you can consistently obtain and use (for example, a cog summon),
# but you cannot specify the amount you recieve, we give this command the prefix of "Restock"
# Unlock - If a word gives you an item that you can only ever obtain once (for example, pet trick phrases or emotes),
# we give this command the prefix of "Unlock"
# Set - If a word gives you an item that you can consistently obtain and use, or if it is a value on your toon (for
# example, a pinkslip, unite, or laff point value), and you can specify the amount you recieve, we give this command
# the prefix of "Set"
# Transform - If a word transforms you into something, we give this command the prefix of "Transform"
# Toggle - If a word toggles something on or off, we give this command the prefix of "Toggle"

# TODO: validation on local avatar, nearby target if exists
class SetHP(MagicWord):
    aliases = ["hp", "setlaff", "laff"]
    desc = "Sets the target's current laff."
    advancedDesc = "This Magic Word will change the current amount of laff points the target has to whichever " \
                   "value you specify. You are only allowed to specify a value between -1 and the target's maximum " \
                   "laff points. If you specify a value less than 1, the target will instantly go sad unless they " \
                   "are in Immortal Mode."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("hp", int, True)]

    def handleWord(self, invoker, avId, toon, *args):
        hp = args[0]

        boss = toon.findBoss()
        if boss and boss.hardcore:
            return "You cannot cheat in this Boss Battle!"

        if not -1 <= hp <= toon.getMaxHp():
            return "Can't set {0}'s laff to {1}! Specify a value between -1 and {0}'s max laff ({2}).".format(
                    toon.getName(), hp, toon.getMaxHp())

        if hp <= 0 and (toon.getImmortalMode() or toon.getTempImmortalMode()):
            return "Can't set {0}'s laff to {1} because they are in Immortal Mode!".format(toon.getName(), hp)

        toon.b_setHp(hp)
        return "{}'s laff has been set to {}.".format(toon.getName(), hp)

# TODO: validation on local avatar, nearby target if exists
class SetMaxHP(MagicWord):
    aliases = ["maxhp", "setmaxlaff", "maxlaff"]
    desc = "Sets the target's max laff."
    advancedDesc = "This Magic Word will change the maximum amount of laff points the target has to whichever value " \
                   "you specify. You are only allowed to specify a value between 15 and 137 laff points."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("maxhp", int, True)]

    def handleWord(self, invoker, avId, toon, *args):
        maxhp = args[0]

        boss = toon.findBoss()
        if boss and boss.hardcore:
            return "You cannot cheat in this Boss Battle!"

        if not 15 <= maxhp <= 137:
            return "Can't set {}'s max laff to {}! Specify a value between 15 and 137.".format(toon.getName(), maxhp)

        toon.b_setMaxHp(maxhp)
        toon.toonUp(maxhp)
        return "{}'s max laff has been set to {}.".format(toon.getName(), maxhp)


class ToggleOobe(MagicWord):
    aliases = ["oobe"]
    desc = "Toggles the out of body experience mode, which lets you move the camera freely."
    advancedDesc = "This Magic Word will toggle what is known as 'Out Of Body Experience' Mode, hence the name " \
                   "'Oobe'. When this mode is active, you are able to move the camera around with your mouse- " \
                   "though your camera will still follow your Toon. You can also toggle this mode by pressing the " \
                   "'F4' key, or whichever other keybind you have set."
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT

    def handleWord(self, invoker, avId, toon, *args):
        if hasattr(self.cr, 'hideAndSeekGame') and self.cr.hideAndSeekGame.isActive():
            return "Oobe toggling is disabled during Hide and Seek."
        base.oobe()
        return "Oobe mode has been toggled."


class SetRunMultiplier(MagicWord):
    aliases = ["run", "togglerun", "togglerunmultiplier", "togglerunmult", "setrun", "setrunmult"]
    desc = "Multiplies your running speed. Resets if you input your current run multiplier."
    advancedDesc = "This Magic Word will multiply your running speed. When this multiplier is active, the target can run around at a " \
                   "very fast speed. This multiplier stacks with other speed multipliers, such as the one given" \
                   "by the 'SetSpeed' Magic Word. Likewise, you can specify a multiplier in this Magic Word itself." \
                   "You will automatically toggle Run Mode by using the 'EnableGod' Magic Word."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("multiplier", float, False, 3.0)]

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg == 0:
            return (('1.0',  'Sets your running speed back to normal.'),
                    ('2.0',  'Multiples your running speed by 2.'),
                    ('3.0',  'Multiples your running speed by 3. This is the default multiplier.'),
                    ('4.0',  'Multiples your running speed by 4.'),
                    ('5.0',  'Multiples your running speed by 5.'),
                    ('6.0',  'Multiples your running speed by 6.'),
                    ('7.0',  'Multiples your running speed by 7.'),
                    ('8.0',  'Multiples your running speed by 8.'),
                    ('9.0',  'Multiples your running speed by 9.'),
                    ('10.0', 'Multiples your running speed by 10.'),
                    )

        return None

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 0:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                multiplier = float(entry)
                return 1.0 <= multiplier <= 3000.0
            return False
        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        microGameMgr = self.air.microGameMgr
        if microGameMgr:
            microGame, active = microGameMgr.getActiveMicroGame(toon.zoneId)
            if active:
                return f"Cannot change run multiplier during a {microGame.getName()}! Please wait until it is over."

        boss = toon.findBoss()
        if boss and boss.hardcore:
            return "You cannot cheat in this Boss Battle!"

        multiplier = args[0]

        if not 1.0 <= multiplier <= 3000.0:
            return f"Can't set run multiplier to {multiplier}! Specify a value between 1 and 3000."

        state, currentMultiplier = toon.getRun()

        if state:
            if multiplier == 1.0 or multiplier == currentMultiplier:
                toon.b_setRun(False, multiplier = 1.0)
                return "Run multiplier has been reset to 1.0"
            else:
                toon.b_setRun(True, multiplier = multiplier)
                return f"Run multiplier has been set to {multiplier}"
        else:
            if multiplier == currentMultiplier:
                return f"Your run multiplier is already set to {multiplier}"
            toon.b_setRun(True, multiplier = multiplier)
            return f"Run multiplier has been set to {multiplier}"

class GetRunMultiplier(MagicWord):
    aliases = ["getrunmult", "getrun"]
    desc = "Get the current run multiplier of the target."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    anyTarget = True

    def handleWord(self, invoker, avId, toon, *args):
        name = toon.getName()
        _, runMultiplier = toon.getRun()
        return f"{name:}'s run multiplier is {runMultiplier}"

class SetSpeed(MagicWord):
    aliases = ["speed"]
    desc = "Sets your running speed."
    advancedDesc = "This Magic Word will change the running speed of the target to whichever value you specify. You " \
                   "are only allowed to specify a value between 1 and 1,000. If you provide no value, the target " \
                   "will be set to the default speed of {}.".format(OTPGlobals.ToonForwardSpeed)
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT
    arguments = [("speed", float, False, OTPGlobals.ToonForwardSpeed)]

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 0:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                speed = float(entry)
                return 1.0 <= speed <= 1000.0
            return False
        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        if hasattr(self.cr, 'pieBlitzGame') and self.cr.pieBlitzGame.isActive():
            return "Cannot set speed during a Pie Blitz! Please wait until it is over."

        if hasattr(self.cr, 'hideAndSeekGame') and self.cr.hideAndSeekGame.isActive():
            return "Cannot set speed during Hide and Seek! Please wait until it is over."

        boss = toon.findBoss()
        if boss and boss.hardcore:
            return "You cannot cheat in this Boss Battle!"

        speed = args[0]

        if not 1.0 <= speed <= 1000.0:
            return "Can't set speed to {}! Specify a value between 1 and 1,000.".format(toon.getName())

        if speed == OTPGlobals.ToonForwardSpeed:
            base.localAvatar.currentSpeed = OTPGlobals.ToonForwardSpeed
            base.localAvatar.currentReverseSpeed = OTPGlobals.ToonReverseSpeed
            base.localAvatar.controlManager.setSpeeds(OTPGlobals.ToonForwardSpeed, OTPGlobals.ToonJumpForce,
                                                      OTPGlobals.ToonReverseSpeed, OTPGlobals.ToonRotateSpeed)
            return "Your speed has been set to the default ({}).".format(OTPGlobals.ToonForwardSpeed)
        else:
            reverseSpeed = speed / 3
            base.localAvatar.currentSpeed = speed
            base.localAvatar.currentReverseSpeed = reverseSpeed
            base.localAvatar.controlManager.setSpeeds(speed, OTPGlobals.ToonJumpForce, reverseSpeed,
                                                      OTPGlobals.ToonRotateSpeed)
            return "Your speed has been set to {}.".format(speed)


class MaxToon(MagicWord):
    aliases = ["idkfa"]
    desc = "Maxes out the target's stats. You can provide a gag track to exclude from the target's unlocked tracks."
    advancedDesc = "This Magic Word will max out all of the target's stats, and then some. This includes: Unlocking " \
                   "every gag, restocking said gags, granting a max gag pouch, granting a max jellybean jar, filling " \
                   "said jar and bank, maxing out laff points, granting global teleport access, maxing out all cog " \
                   "disguises, maxing out the Cog Gallery, completing the taskline up until Seek Out Scrooge, maxing " \
                   "out the Fish Gallery, completing all racing trohpies, granting the Roadster kart, granting max " \
                   "racing tickets, completing all golfing trophies, granting a garden, maxing out the Flower " \
                   "Gallery, maxing out the shovel and watering can, granting 16 of the best SOS cards, granting " \
                   "the maximum amount of unites in each category, granting summons for all Cogs in the Cog " \
                   "Gallery, and granting the maximum amount of pinkslips. You can also choose to specify a gag " \
                   "track to exclude from being granted, if you wish for the target to seem legitimate."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("missingTrack", str, False, '')]

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg == 0:
            return ('None', None), ('Toon-Up', None), ('Trap', None), ('Lure', None), ('Sound', None), ('Throw', None), ('Squirt', None), ('Drop', None)
        return None

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 0:
            missingTrack = str(entry).lower()
            if missingTrack.isdigit():
                index = int(missingTrack)
                return 0 <= index <= 6
            if missingTrack not in ['none', 'null', '']:
                return missingTrack in MissingTrack2Index
            return True

        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        missingTrack = args[0].lower()

        boss = toon.findBoss()
        if boss and boss.hardcore:
            return "You cannot cheat in this Boss Battle!"

        from toontown.quest import Quests

        # Set the target's gag tracks (they can specify if they wish to omit a track)
        gagTracks = [1, 1, 1, 1, 1, 1, 1]

        if missingTrack.isdigit():
            index = int(missingTrack)
            if index < 0 or index > 6:
                return 'Missing Gag track is invalid!'
            gagTracks[index] = 0
        elif missingTrack not in ['none', 'null', '']:
            if missingTrack in MissingTrack2Index:
                index = MissingTrack2Index[missingTrack]
                gagTracks[index] = 0
            else:
                return 'Missing Gag track is invalid!'
        toon.b_setTrackAccess(gagTracks)

        # Maxed out carry limit
        toon.b_setMaxCarry(ToontownGlobals.MaxCarryLimit)

        # Max out the experience in each of the gag tracks
        experience = Experience.Experience(toon.getExperience(), toon)
        for i, track in enumerate(toon.getTrackAccess()):
            if track:
                experience.experience[i] = (
                        Experience.MaxSkill - Experience.UberSkill)
        toon.b_setExperience(experience.makeNetString())

        # Restock their inventory
        toon.inventory.zeroInv()
        toon.inventory.maxOutInv(filterUberGags = 0, filterPaidGags = 0)
        toon.b_setInventory(toon.inventory.makeNetString())

        # Set their jar size and max our both jar and bank
        toon.b_setMaxMoney(Quests.RewardDict[707][1])
        toon.b_setMoney(toon.getMaxMoney())
        toon.b_setBankMoney(ToontownGlobals.DefaultMaxBankMoney)

        # Give them the max amount of emblems
        toon.b_setEmblems([ToontownGlobals.EmblemsMax, ToontownGlobals.EmblemsMax])

        # Set their max laff to 137 and toon them up
        toon.b_setMaxHp(ToontownGlobals.MaxHpLimit)
        laff = toon.getMaxHp() - toon.getHp()
        if laff < 15:
            laff = 15
        toon.toonUp(laff)

        # Unlock all zones for teleport
        toon.b_setHoodsVisited(ToontownGlobals.Hoods)
        toon.b_setTeleportAccess(ToontownGlobals.HoodsForTeleportAll)

        # Max out all Cog disguises
        toon.b_setCogParts([
            CogDisguiseGlobals.PartsPerSuitBitmasks[0],
            CogDisguiseGlobals.PartsPerSuitBitmasks[1],
            CogDisguiseGlobals.PartsPerSuitBitmasks[2],
            CogDisguiseGlobals.PartsPerSuitBitmasks[3],
        ])
        toon.b_setCogTypes([7] * 4)
        toon.b_setCogLevels([ToontownGlobals.MaxCogSuitLevel] * 4)

        # Complete the Cog Radar
        toon.b_setCogRadar([1] * 4)
        toon.b_setBuildingRadar([1] * 4)

        # Clear out all toontasks, give carry limit of 4 tasks, set them to SOS tier
        for questId in toon.getQuests():
            toon.removeQuest(questId)

        toon.b_setQuestCarryLimit(ToontownGlobals.MaxQuestCarryLimit)
        toon.b_setRewardHistory(Quests.COG_NATION_TIER, [])

        # Add all fish to their collection, set their rod to gold, and max out fishing trophies
        allFish = TTLocalizer.FishSpeciesNames
        fishLists = [[], [], []]
        for genus in list(allFish.keys()):
            for species in range(len(allFish[genus])):
                fishLists[0].append(genus)
                fishLists[1].append(species)
                fishLists[2].append(FishGlobals.getRandomWeight(genus, species))
        toon.b_setFishCollection(*fishLists)
        toon.b_setFishingRod(FishGlobals.MaxRodId)
        toon.b_setFishingTrophies(list(FishGlobals.TrophyDict.keys()))

        # Give them the most expensive kart, maxed out tickets, and complete racing trophies
        if not toon.hasKart() and simbase.wantKarts:
            toon.b_setKartBodyType(list(KartDict.keys())[1])
        toon.b_setTickets(RaceGlobals.MaxTickets)
        maxTrophies = RaceGlobals.NumTrophies + RaceGlobals.NumCups
        toon.b_setKartingTrophies(list(range(1, maxTrophies + 1)))
        toon.b_setTickets(99999)

        # Complete all the golfing trophies
        toon.b_setGolfHistory([600] * (GolfGlobals.MaxHistoryIndex * 2 + 2))

        # Give a garden if they don't already have one
        if not toon.getGardenStarted():
            estate = self.air.estateMgr.estate.get(toon.doId)
            if estate:
                estate.placeStarterGarden(toon.doId)

        # Max out shovel, watering can, grant all gardening trophies, and give all gardening specials
        toon.b_setShovel(3)
        toon.b_setWateringCan(3)
        toon.b_setShovelSkill(639)
        toon.b_setWateringCanSkill(999)
        varietyList = []
        speciesList = []
        flowerSpecies = GardenGlobals.getFlowerSpecies()
        for species in flowerSpecies:
            numVarieties = len(GardenGlobals.getFlowerVarieties(species))
            for variety in range(numVarieties):
                speciesList.append(species)
                varietyList.append(variety)
        toon.b_setFlowerCollection(speciesList, varietyList)
        toon.b_setGardenTrophies(list(GardenGlobals.TrophyDict.keys()))
        toon.gardenSpecials = []
        for x in (100, 101, 102, 103, 105, 106, 107, 108, 109, 130, 131, 135):
            toon.addGardenItem(x, 99)

        # Stock them up with the best SOS cards
        sosIds = [4125, 2003, 1116, 2311, 4119, 4219, 4115, 3112, 1323, 2308, 2011, 2001, 2132, 2121, 5124, 4230]
        for id in sosIds:
            toon.NPCFriendsDict[id] = 100
        toon.d_setNPCFriendsDict(toon.NPCFriendsDict)

        # Grant max of all unites
        toon.restockAllResistanceMessages(999)

        # Fill out the Cog Gallery with all summons
        cogCount = []
        for deptIndex in range(4):
            for cogIndex in range(8):
                cogCount.append(CogPageGlobals.COG_QUOTAS[1][cogIndex])
        toon.b_setCogCount(cogCount)
        toon.b_setCogStatus(([CogPageGlobals.COG_COMPLETE2] * 8) * 4)
        toon.restockAllCogSummons()

        # Finally, give them the maximum amount of pinkslips
        toon.b_setPinkSlips(255)

        return "Maxed out {}'s stats.".format(toon.getName())


class UnlockEmotes(MagicWord):
    aliases = ["emotes"]
    desc = "Unlock all of the target's emotes."
    advancedDesc = "This Magic Word will permanently unlock all of the obtainable Emotes for the target. This " \
                   "includes all of the purchaseable Emotes from the Catalog, and an unreleased Emote called 'Taunt'."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER

    def handleWord(self, invoker, avId, toon, *args):
        emoteAccess = list(toon.getEmoteAccess())

        # Old version of command made emote access list shorter. Let's fix that.
        if len(emoteAccess) < len(OTPLocalizer.EmoteFuncDict):
            emoteAccess = [0] * len(OTPLocalizer.EmoteFuncDict)

        for emoteId in list(OTPLocalizer.EmoteFuncDict.values()):
            if emoteId > 24 or emoteId in [16, 17, 18]:
                emoteAccess[emoteId] = 0
            else:
                emoteAccess[emoteId] = 1

        toon.b_setEmoteAccess(emoteAccess)
        return "Unlocked all of {}'s emotes.".format(toon.getName())


class UnlockGarden(MagicWord):
    aliases = ["garden"]
    desc = "Unlocks the target's garden."
    advancedDesc = "This Magic Word will permanently unlock the Garden in the target's Estate. This is an " \
                   "alternative to purchasing it in the Catalog."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER

    def handleWord(self, invoker, avId, toon, *args):
        if toon.getGardenStarted():
            return "{} already has a garden.".format(toon.getName())

        estate = self.air.estateMgr.estate.get(toon.doId)
        if not estate:
            return "{}'s estate is unavailable. They must be at their estate to use this Magic Word.".format(
                toon.getName())

        estate.placeStarterGarden(toon.doId)
        return "Unlocked {}'s garden.".format(toon.getName())

# TODO: validation on local avatar, nearby target if exists
class SetJarBeans(MagicWord):
    aliases = ["jarbeans", "setjarjellybeans", "jarjellybeans", "setjarmoney", "jarmoney", "jar", "setjar"]
    desc = "Sets the target's jellybean count in their jar."
    advancedDesc = "This Magic Word will change the amount of jellybeans in the target's jar. You are only allowed " \
                   "to specify a value between 0 and how many jellybeans the target's jar can hold."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("beans", int, True)]

    def handleWord(self, invoker, avId, toon, *args):
        beans = args[0]

        if not 0 <= beans <= toon.getMaxMoney():
            return "Can't set {0}'s jar jellybean count to {1}! Specify a value between 0 and {0}'s jellybean jar " \
                   "size ({2}).".format(
                    toon.getName(), beans, toon.getMaxMoney())

        toon.b_setMoney(beans)
        return "{}'s jar jellybean count has been set to {}.".format(toon.getName(), beans)

# TODO: validation on local avatar, nearby target if exists
class SetBankBeans(MagicWord):
    aliases = ["bankbeans", "bankjellybeans", "setbankmoney", "bankmoney", "bank", "setbank"]
    desc = "Sets the target's jellybean count in their bank."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("beans", int, True)]

    def handleWord(self, invoker, avId, toon, *args):
        beans = args[0]

        if not 0 <= beans <= toon.getMaxBankMoney():
            return "Can't set {0}'s bank jellybean count to {1}! Specify a value between 0 and {0}'s jellybean bank " \
                   "size ({2}).".format(
                    toon.getName(), beans, toon.getMaxBankMoney())

        toon.b_setBankMoney(beans)
        return "{}'s bank jellybean count has been set to {}.".format(toon.getName(), beans)

# TODO: validation on local avatar, nearby target if exists
class SetMaxJarBeans(MagicWord):
    aliases = ["maxjarbeans", "setmaxjarjellybeans", "maxjarjellybeans", "setmaxjarmoney", "maxjarmoney", "maxjar",
               "setmaxjar", "jarsize", "setjarsize"]
    desc = "Sets the target's jellybean jar size."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("maxBeans", int, True)]

    def handleWord(self, invoker, avId, toon, *args):
        maxBeans = args[0]

        if not 0 <= maxBeans <= ToontownGlobals.MaxJarMoney:
            return "Can't set {}'s jellybean jar size to {}! Specify a value between 0 and {}.".format(toon.getName(),
                                                                                                       maxBeans,
                                                                                                       ToontownGlobals.MaxJarMoney)

        toon.b_setMaxMoney(maxBeans)

        if toon.getMoney() > toon.getMaxMoney():
            toon.b_setMoney(toon.getMaxMoney())

        return "{}'s jellybean jar size has been set to {}.".format(toon.getName(), maxBeans)

# TODO: validation on local avatar, nearby target if exists
class SetMaxBankBeans(MagicWord):
    aliases = ["maxbankbeans", "maxbankjellybeans", "setmaxbankmoney", "maxbankmoney", "maxbank", "setmaxbank",
               "banksize", "setbanksizesize"]
    desc = "Sets the target's jellybean bank size."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("maxBeans", int, True)]

    def handleWord(self, invoker, avId, toon, *args):
        maxBeans = args[0]

        if not 0 <= maxBeans <= ToontownGlobals.DefaultMaxBankMoney:
            return "Can't set {}'s jellybean bank size to {}! Specify a value between 0 and {}.".format(toon.getName(),
                                                                                                        maxBeans,
                                                                                                        ToontownGlobals.DefaultMaxBankMoney)

        toon.b_setMaxBankMoney(maxBeans)

        if toon.getBankMoney() > toon.getMaxBankMoney():
            toon.b_setBankMoney(toon.getMaxBankMoney())

        return "{}'s jellybean bank size has been set to {}.".format(toon.getName(), maxBeans)


class SetEmblems(MagicWord):
    aliases = ["emblems"]
    desc = "Sets the target's amount of silver and gold emblems respectively."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("silver", int, False, 10000), ("gold", int, False, 10000)]

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg in [0, 1]:
            return ('0', 'None'), ('2500', None), ('5000', None), ('7500', None), ('10000', 'Maximum')
        return None

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 0:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                silver = int(entry)
                return 0 <= silver <= ToontownGlobals.EmblemsMax
            return False
        elif arg == 1:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                gold = int(entry)
                return 0 <= gold <= ToontownGlobals.EmblemsMax
            return False
        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        silver = args[0]
        gold = args[1]

        if not 0 <= silver <= ToontownGlobals.EmblemsMax:
            return "Can't set {}'s Silver Emblems to {}! Specify a value between 0 and {}.".format(toon.getName(),
                                                                                                   silver,
                                                                                                   ToontownGlobals.EmblemsMax)

        if not 0 <= gold <= ToontownGlobals.EmblemsMax:
            return "Can't set {}'s Gold Emblems to {}! Specify a value between 0 and {}.".format(toon.getName(), gold,
                                                                                                 ToontownGlobals.EmblemsMax)

        emblems = [silver, gold]
        toon.b_setEmblems(emblems)
        return "{}'s Silver Emblems has been set to {} and Gold Emblems to {}.".format(toon.getName(), *emblems)


class ToggleImmortal(MagicWord):
    aliases = ["immortal"]
    desc = "Toggles immortality for the target."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER

    def handleWord(self, invoker, avId, toon, *args):
        microGameMgr = self.air.microGameMgr
        if microGameMgr:
            microGame, active = microGameMgr.getActiveMicroGame(toon.zoneId)
            if active:
                return "Cannot toggle immortal during a %s! Please wait until it is over." % microGame.getName()

        boss = toon.findBoss()
        if boss and boss.hardcore:
            return "You cannot cheat in this Boss Battle!"

        toon.b_setImmortalMode(not toon.getImmortalMode())
        return "{} is {} immortal!".format(toon.getName(), "now" if toon.getImmortalMode() else "no longer")

class ToggleTreasureDamage(MagicWord):
    aliases = ["treasuredamage"]
    desc = "Toggles whether or not treasures deal damage to the target."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER

    def handleWord(self, invoker, avId, toon, *args):
        toon.setTreasureDamage(not toon.getTreasureDamage())
        return "{} {} takes damage from treasures!".format(toon.getName(), "now" if toon.getTreasureDamage() else "no longer")

class ToggleUnlimitedGags(MagicWord):
    aliases = ["unlimitedgags"]
    desc = "Toggles unlimited gags for the target."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER

    def handleWord(self, invoker, avId, toon, *args):
        boss = toon.findBoss()
        if boss and boss.hardcore:
            return "You cannot cheat in this Boss Battle!"

        inventory = toon.inventory
        inventory.NPCMaxOutInv(targetTrack = -1, maxLevelIndex = 6)
        invoker.b_setInventory(inventory.makeNetString())
        toon.b_setUnlimitedGags(not toon.getUnlimitedGags())
        return "{} {} has unlimited gags!".format(toon.getName(), "now" if toon.getUnlimitedGags() else "no longer")


class ToggleInstaKill(MagicWord):
    aliases = ["instakill"]
    desc = "Toggles the ability for the target to instantly kill Cogs with any amount of damage."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER

    def handleWord(self, invoker, avId, toon, *args):
        boss = toon.findBoss()
        if boss and boss.hardcore:
            return "You cannot cheat in this Boss Battle!"

        toon.b_setInstaKill(not toon.getInstaKill())
        return "{} can {} insta-kill Cogs!".format(toon.getName(), "now" if toon.getInstaKill() else "no longer")


class ToggleAutoJoin(MagicWord):
    aliases = ["autojoin", "togglecogalwaysjoin", "cogsalwaysjoin", "alwaysjoin", ]
    desc = "Toggles the ability for Cogs to always join your battle on the street."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER

    def handleWord(self, invoker, avId, toon, *args):
        toon.b_setAutoJoin(not toon.getAutoJoin())
        return "{} {} attracts Cogs to join their fight!".format(toon.getName(),
                                                                 "now" if toon.getAutoJoin() else "no longer")


class SkipMovie(MagicWord):
    aliases = ["skipround"]
    desc = "Skips the gag animations in the current cog battle round."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    affectRange = [MagicWordConfig.AFFECT_SELF]

    def handleWord(self, invoker, avId, toon, *args):
        battleId = toon.getBattleId()
        if not battleId:
            return "Could not skip the movie because {} is not currently in a Cog Battle.".format(toon.getName())
        battle = self.air.doId2do.get(battleId)
        if not battle:
            return "{} is not a valid battle! Please contact Toontown Realms support.".format(battleId)
        battleState = battle.fsm.getCurrentState().getName()
        if battleState not in ('PlayMovie', 'MakeMovie'):
            return "You can only skip the battle movie while it is playing."
        battle._DistributedBattleBaseAI__movieDone()
        return "Successfully skipped Battle movie!"

class SetMaxCogs(MagicWord):
    aliases = ["setmaxsuits", "maxsuits", "maxcogs"]
    desc = "Sets the maximum amount of Cogs allowed to join in the current cog battle round."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    affectRange = [MagicWordConfig.AFFECT_SELF]
    arguments = [("maxCogs", int, False, 4)]

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg == 0:
            return ('1', None), ('2', None), ('3', None), ('4', None), ('5', None), ('6', None), ('7', None), ('8', None)
        return None

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 0:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                maxCogs = int(entry)
                return 1 <= maxCogs <= 8
            return False
        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        battleId = toon.getBattleId()
        if not battleId:
            return f"Could not set max Cogs because {toon.getName()} is not currently in a Cog Battle."
        battle = self.air.doId2do.get(battleId)
        if not battle:
            return f"{battleId} is not a valid battle! Please contact Toontown Realms support."
        if not battle.streetBattle:
            return "This battle must be a street battle!"
        maxCogs = args[0]
        if maxCogs < 1 or maxCogs > 8:
            return "Only 1-8 Cogs are allowed to be set as the maximum amount able to join."

        battle.maxSuits = maxCogs
        return f"The max Cogs in this battle has been set to {maxCogs}."

class SetBattleTimer(MagicWord):
    aliases = ["battletimer"]
    desc = "Adjusts the battle timer in the current cog battle."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    affectRange = [MagicWordConfig.AFFECT_SELF]
    arguments = [("roundTime", int, False, 30)]

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg == 0:
            return ('5', 'Minimum'), ('10', None), ('15', None), ('20', None), ('25', None), ('30', None), ('35', None), ('40', None), ('45', None), ('50', None), ('55', None), ('60', 'Maximum')
        return None

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 0:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                roundTime = int(entry)
                return 5 <= roundTime <= 60
            return False
        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        battleId = toon.getBattleId()
        if not battleId:
            return f"Could not set the battle timer because {toon.getName()} is not currently in a Cog Battle."
        battle = self.air.doId2do.get(battleId)
        if not battle:
            return f"{battleId} is not a valid battle! Please contact Toontown Realms support."
        roundTime = args[0]
        if roundTime < 5 or roundTime > 60:
            return "Only 5-60 seconds are allowed to be set as the round time in this battle."

        battle.b_setRoundTime(roundTime)
        return f"The battle timer has been set to {roundTime} on next battle adjustment."

class ToggleGod(MagicWord):
    aliases = ['god', 'unlimitedpower']
    desc = "Enables running, immortality, unlimited gags, instakill, and instadelivery for the target."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER

    def handleWord(self, invoker, avId, toon, *args):
        boss = toon.findBoss()
        toggle = not toon.getImmortalMode()
        statusStr = f"{'Enabled' if toggle else 'Disabled'} god mode for {toon.getName()}."
        toonCheats = [
            partial(toon.b_setImmortalMode, toggle),
            partial(toon.b_setRun, toggle),
            partial(toon.b_setUnlimitedGags, toggle),
            partial(toon.b_setInstaKill, toggle)
        ]

        if boss and boss.hardcore:
            return "You cannot cheat in this Boss Battle!"

        # Set this true no matter what
        toon.instantDelivery = True
        for item in toon.onOrder:
            item.deliveryDate = int(time.time() / 60)

        microGameMgr = self.air.microGameMgr
        if microGameMgr: # Right now this is true 100% of the time
            microGame, active = microGameMgr.getActiveMicroGame(toon.zoneId)
            if not active:
                for x in range(4):
                    toonCheats[x]()
                return statusStr
            else:
                toon.b_setImmortalMode(False)
                toon.b_setRun(False, multiplier = 1.0)
                return f"Cannot toggle god mode during a {microGame.getName()}. Please wait until the game is over."
        else:
            for x in range(4):
                toonCheats[x]()
            return statusStr


class ToggleCollisionBounds(MagicWord):
    aliases = ['collisionsbound', 'colbound', 'collisionbound']
    desc = "Toggles the display of collision bounds surrounding the invoker."
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT

    def handleWord(self, invoker, avId, toon, *args):
        if not base.cr.collisionsToggled:
            base.cTrav.showCollisions(render)
            base.shadowTrav.showCollisions(render)
            base.cr.collisionsToggled = True
            return 'Displaying collision bounds.'
        else:
            base.cTrav.hideCollisions()
            base.shadowTrav.hideCollisions()
            base.cr.collisionsToggled = False
            return 'Collision bounds hidden.'


class UnlockGlobalTP(MagicWord):
    aliases = ["alltp", "globaltp"]
    desc = "Gives the target the ability to teleport anywhere."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER

    def handleWord(self, invoker, avId, toon, *args):
        hoodsVisited = [1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000, 11000, 12000, 13000]
        toon.b_setHoodsVisited(hoodsVisited)
        toon.b_setTeleportAccess(hoodsVisited)
        return "{} can now teleport anywhere!".format(toon.getName())


class Help(MagicWord):
    administrative = True
    desc = "Tells you to come here for more info... but you're already here!"
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT

    def handleWord(self, invoker, avId, toon, *args):

        # we're actually client; get the actual prefix, or '~' if invalid
        idx = ClientSettings.MagicWordActivator.get()
        idx = idx if 0 <= idx < len(MagicWordConfig.PREFIX_ALLOWED) else 0
        mw_prefix = MagicWordConfig.PREFIX_ALLOWED[idx]
        return "Refer to your Shticker Book for a list of all Magic Words!" \
               " Some may require a higher Access Level. Clicking a Toon's nametag" \
               " and then using 2 '{}' characters will run a command on them.".format(mw_prefix)


class ToggleSleeping(MagicWord):
    aliases = ["sleep", "sleeping"]
    desc = "Toggles sleeping for the current session."
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT

    def handleWord(self, invoker, avId, toon, *args):
        if not base.localAvatar.neverSleep:
            base.localAvatar.disableSleeping()
            return "Sleeping has been deactivated for the current session."
        else:
            base.localAvatar.enableSleeping()
            return "Sleeping has been activated for the current session."


class ForceSleeping(MagicWord):
    aliases = ['forcesleep', 'forcegotosleep']
    desc = "Forces your Toon to fall asleep."
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT

    def handleWord(self, invoker, avId, toons, *args):
        state = base.cr.playGame.getPlace().fsm.getCurrentState().getName()
        if base.localAvatar.neverSleep:
            return 'You cannot sleep while sleeping is deactivated.'
        if not state in ('walk', 'stickerBook'):
            return f'You cannot fall asleep while in the "{state}" state.'
        if base.localAvatar.getHp() <= 0:
            return "You cannot fall asleep while sad."
        if base.localAvatar.ghostMode == 2:
            return "You cannot fall asleep while in ghost mode."
        taskMgr.remove(base.localAvatar.uniqueName('sleepwatch'))
        if base.localAvatar.sleepCallback:
            base.localAvatar.sleepCallback()
        if state != 'stickerBook':
            base.localAvatar.forceGotoSleep()
        return 'You are now asleep.'


class ToggleRainbow(MagicWord):
    aliases = ["rainbow"]
    desc = "Toggles the target's client to cycle through rendering rainbow colors over all geometry."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER

    def handleWord(self, invoker, avId, toon, *args):
        toon.d_generateRainbow()
        return "Rainbows toggled for {0}.".format(toon.getName())


class Teleport(MagicWord):
    aliases = ["tp"]
    desc = "Teleports the target to the specified location."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("zoneId", str, False, '')]

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 0:
            zoneId = str(entry).lower()
            hoodsForTeleport = ToontownGlobals.hoodsForTeleport
            if zoneId not in hoodsForTeleport:
                return False
            return True
        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        zoneId = args[0].lower()

        if not zoneId:
            toon.d_doTeleport('gui')
            return "Teleport GUI opened!"

        hoodsForTeleport = ToontownGlobals.hoodsForTeleport
        if zoneId not in hoodsForTeleport:
            return "Invalid location specified!"

        hoodId = None
        zoneIds = list(ToontownGlobals.hood2Id.keys())
        hoods = list(ToontownGlobals.hood2Id.values())
        for hood in hoods:
            index = hoods.index(hood)
            for shorthand in hood:
                if zoneId == shorthand:
                    hoodId = zoneIds[index]

        if not hoodId:
            return "Invalid location specified"

        toon.d_doTeleport(zoneId)
        return "Teleporting {0} to {1}!".format(toon.getName(),
                                                ToontownGlobals.hoodNameMap[ZoneUtil.getHoodId(hoodId)][-1])


class SetScale(MagicWord):
    aliases = ["scale", "setsize", "size"]
    desc = "Sets how big the target is. Calling this with no arguments will set the target's scale to 1."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("scale", float, False, 1.0)]

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg == 0:
            return ('0.1', 'Minimum'), ('0.5', None), ('1', None), ('2', None), ('3', None), ('4', None), ('5', 'Maximum')
        return None

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 0:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                scale = float(entry)
                return 0.1 <= scale <= 5
            return False
        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        microGameMgr = self.air.microGameMgr
        if microGameMgr:
            microGame, active = microGameMgr.getActiveMicroGame(toon.zoneId)
            if active:
                return "Cannot set scale during %s! Please wait until it is over." % microGame.getName()

        scale = args[0]
        if not 0.1 <= scale <= 5:
            return "That scale is out of range! It must be between 0.1 and 5."
        toon.d_setToonScale(scale)
        return "Set {}'s scale to {}.!".format(toon.getName(), scale)


class SpawnProp(MagicWord):
    aliases = ["prop", "propgenerator"]
    desc = "Spawn a prop at the target's current location."
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT
    arguments = [("name", str, False, ''), ("scale", float, False, 1.0)]

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg == 1:
            return ('0.1', 'Minimum'), ('0.5', None), ('1', None), ('2', None), ('3', None), ('4', None), ('5', 'Maximum')
        return None

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 0:
            valid = False
            propName = PropGlobals.getPropNameCaseInsensitive(str(entry))
            if propName is not None:
                valid = True
            if not valid:
                for prop in [x[0] for x in ToontownGlobals.PropsBattle]:
                    propLower = prop.lower()
                    propStripped = propLower.replace(" ", "")
                    if propName == propLower or propName == propStripped:
                        valid = True
                        propName = prop
                        break
            return valid
        elif arg == 1:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                scale = float(entry)
                return 0.1 <= scale <= 5
            return False
        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        if not hasattr(base.cr, 'propGenerator') or not base.cr.propGenerator:
            return 'Sorry, you are unable to spawn props in this location.'
        if not base.cr.playGame.getPlace().fsm.getCurrentState().getName() == 'walk':
            return 'Sorry, you must be walking in order to spawn props.'

        propName = args[0].lower()

        if not propName:
            base.cr.propGenerator.openNewPropWindow()
            return "Prop generator opened!"

        propNames = list(PropGlobals.PropList.keys())

        valid = 0
        for prop in propNames:
            propLower = prop.lower()
            propStripped = propLower.replace(" ", "")
            if propName == propLower or propName == propStripped:
                valid = 1
                propName = prop
                break

        if not valid:
            return "Invalid prop name!"

        if propName not in propNames:
            return "Invalid prop name!"

        scale = args[1]
        if not 0.1 <= scale <= 5:
            return "That scale is out of range! It must be between 0.1 and 5."

        x, y, z = toon.getPos()
        h, p, r = toon.getHpr()

        base.cr.propGenerator.sendUpdate('requestSpawnProp', [propName, (x, y, z), (h, p, r), (scale, scale, scale)])
        return "Spawned a prop at {}'s location.".format(toon.getName())


class SetLoop(MagicWord):
    aliases = ['loop']
    desc = "Sets an animation to loop for the target."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("animName", str, True), ("start", int, False, -1), ("end", int, False, -1), ("part", str, False, '')]
    allAnims = ToonAnims + CharAnims + MickeyAnims + VampMickeyAnims + MinnieAnims + WitchMinnieAnims + SuperGoofyAnims \
               + DreamlandDonaldAnims + PlutoAnims + DoodleAnims + SuitAnims + SuitAAnims + SuitBAnims + SuitCAnims + GoonAnims + BossAnims

    def handleWord(self, invoker, avId, toon, *args):
        animations = []
        for anim in self.allAnims:
            animations.append(anim[0])

        # Have to validate this way cause this mw is running on the server
        if args[0] not in animations:
            return "Invalid Animation!"
 
        start = args[1]
        end = args[2]

        # Sadly we can't actually validate the frame ranges since this is running
        # on the server. This mw system is kinda bad
        if not -1 <= start <= 1000:
            return f"Start frame out of range! Must be between 0 and 1000"

        if not -1 <= end <= 1000:
            return f"End frame out of range! Must be between 0 and 1000"

        toon.d_setLoop(args[0], args[1], args[2], args[3])
        return f"Looping '{args[0]}' for {toon.getName()}."

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        suitAnimTypes = {
            'a': SuitAAnims,
            'b': SuitBAnims,
            'c': SuitCAnims
        }
        charAnimTypes = {
            'mk': MickeyAnims,
            'vmk': VampMickeyAnims,
            'mn': MinnieAnims,
            'wmn': WitchMinnieAnims,
            'sg': SuperGoofyAnims,
            'd': DreamlandDonaldAnims,
            'p': PlutoAnims,
            'wp': PlutoAnims
        }
        if base.localAvatar.getTransformationsIndex(0):
            anims = SuitAnims + suitAnimTypes.get(base.localAvatar.suit.getBodyType())
        elif base.localAvatar.getTransformationsIndex(1):
            chrName = base.localAvatar.char.style.name
            if chrName in charAnimTypes:
                anims = CharAnims + charAnimTypes.get(base.localAvatar.char.style.name)
            else:
                anims = CharAnims
        elif base.localAvatar.getTransformationsIndex(2):
            anims = DoodleAnims
        elif base.localAvatar.getTransformationsIndex(3):
            anims = GoonAnims
        elif base.localAvatar.getTransformationsIndex(5):
            anims = BossAnims
        else:
            anims = ToonAnims

        if arg == 0:
            return anims
        elif arg == 3:
            if base.localAvatar.getTransformationsIndex(0):
                return
            else:
                return ('head', None), ('torso', None), ('legs', None)

        return None

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        # start and stop animation must be in the range of the animation
        if 2 >= arg >= 1:
            # First, we gotta make sure the anim is a real one
            if MagicWord.validateArg(self, 0, allArgs[0], allArgs):
                # Then make sure its an int
                validType = MagicWord.validateArg(self, arg, entry, allArgs)
                if validType:
                    # Then we can check if its in between 0 and the # of frames in the animation
                    toon = base.localAvatar.getActiveTransformation()
                    if toon is None:
                        toon = base.localAvatar
                    return 0 <= int(entry) <= toon.getNumFrames(allArgs[0])
        return MagicWord.validateArg(self, arg, entry, allArgs)


class SetPingPong(MagicWord):
    aliases = ['pingpong']
    desc = "Sets two frames of an animation to go back and forth for the target. By default, these are the start and " \
           "end frames."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("animName", str, True), ("start", int, False, -1), ("end", int, False, -1), ("part", str, False, '')]
    allAnims = ToonAnims + CharAnims + MickeyAnims + VampMickeyAnims + MinnieAnims + WitchMinnieAnims + SuperGoofyAnims\
               + DreamlandDonaldAnims + PlutoAnims + DoodleAnims + SuitAnims + SuitAAnims + SuitBAnims + SuitCAnims + GoonAnims + BossAnims

    def handleWord(self, invoker, avId, toon, *args):
        animations = []
        for anim in self.allAnims:
            animations.append(anim[0])

        # Have to validate this way cause this mw is running on the server
        if args[0] not in animations:
            return "Invalid Animation!"

        start = args[1]
        end = args[2]

        if not -1 <= start <= 1000:
            return "Start frame out of range! Must be between -1 and 1000."

        if not -1 <= end <= 1000:
            return "End frame out of range! Must be between -1 and 1000."

        toon.d_setPingPong(args[0], args[1], args[2], args[3])
        return f"{toon.getName()} is now going back and forth between 2 frames of an animation."

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        suitAnimTypes = {
            'a': SuitAAnims,
            'b': SuitBAnims,
            'c': SuitCAnims
        }
        charAnimTypes = {
            'mk': MickeyAnims,
            'vmk': VampMickeyAnims,
            'mn': MinnieAnims,
            'wmn': WitchMinnieAnims,
            'sg': SuperGoofyAnims,
            'd': DreamlandDonaldAnims,
            'p': PlutoAnims,
            'wp': PlutoAnims
        }
        if base.localAvatar.getTransformationsIndex(0):
            anims = SuitAnims + suitAnimTypes.get(base.localAvatar.suit.getBodyType())
        elif base.localAvatar.getTransformationsIndex(1):
            chrName = base.localAvatar.char.style.name
            if chrName in charAnimTypes:
                anims = CharAnims + charAnimTypes.get(base.localAvatar.char.style.name)
            else:
                anims = CharAnims
        elif base.localAvatar.getTransformationsIndex(2):
            anims = DoodleAnims
        elif base.localAvatar.getTransformationsIndex(3):
            anims = GoonAnims
        elif base.localAvatar.getTransformationsIndex(5):
            anims = BossAnims
        else:
            anims = ToonAnims

        if arg == 0:
            return anims
        elif arg == 3:
            if base.localAvatar.getTransformationsIndex(0):
                return
            else:
                return ('head', None), ('torso', None), ('legs', None)

        return None

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        # start and stop animation must be in the range of the animation
        if 2 >= arg >= 1:
            # First, we gotta make sure the anim is a real one
            if MagicWord.validateArg(self, 0, allArgs[0], allArgs):
                # Then make sure its an int
                validType = MagicWord.validateArg(self, arg, entry, allArgs)
                if validType:
                    # Then we can check if its in between 0 and the # of frames in the animation
                    # Then we can check if its in between 0 and the # of frames in the animation
                    toon = base.localAvatar.getActiveTransformation()
                    if toon is None:
                        toon = base.localAvatar
                    return 0 <= int(entry) <= toon.getNumFrames(allArgs[0])
        return MagicWord.validateArg(self, arg, entry, allArgs)

class SetPose(MagicWord):
    aliases = ['pose']
    desc = "Sets the target's pose via a given frame of a given animation."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("animName", str, True), ("frame", int, True), ("part", str, False, '')]
    allAnims = ToonAnims + CharAnims + MickeyAnims + VampMickeyAnims + MinnieAnims + WitchMinnieAnims + \
               SuperGoofyAnims + DreamlandDonaldAnims + PlutoAnims + DoodleAnims + SuitAnims + SuitAAnims + \
               SuitBAnims + SuitCAnims + GoonAnims + BossAnims

    def handleWord(self, invoker, avId, toon, *args):
        animations = []
        for anim in self.allAnims:
            animations.append(anim[0])

        # Have to validate this way cause this mw is running on the server
        if args[0] not in animations:
            return "Invalid Animation!"

        frame = args[1]

        if not 0 <= frame <= 1000:
            return "Frame out of range! Must be between -1 and 1000."

        toon.d_setPose(args[0], args[1], args[2])
        return f"{toon.getName()} is now posing."

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        suitAnimTypes = {
            'a': SuitAAnims,
            'b': SuitBAnims,
            'c': SuitCAnims
        }
        charAnimTypes = {
            'mk': MickeyAnims,
            'vmk': VampMickeyAnims,
            'mn': MinnieAnims,
            'wmn': WitchMinnieAnims,
            'sg': SuperGoofyAnims,
            'd': DreamlandDonaldAnims,
            'p': PlutoAnims,
            'wp': PlutoAnims
        }
        if base.localAvatar.getTransformationsIndex(0):
            anims = SuitAnims + suitAnimTypes.get(base.localAvatar.suit.getBodyType())
        elif base.localAvatar.getTransformationsIndex(1):
            chrName = base.localAvatar.char.style.name
            if chrName in charAnimTypes:
                anims = CharAnims + charAnimTypes.get(base.localAvatar.char.style.name)
            else:
                anims = CharAnims
        elif base.localAvatar.getTransformationsIndex(2):
            anims = DoodleAnims
        elif base.localAvatar.getTransformationsIndex(3):
            anims = GoonAnims
        elif base.localAvatar.getTransformationsIndex(5):
            anims = BossAnims
        else:
            anims = ToonAnims

        if arg == 0:
            return anims
        elif arg == 2:
            if base.localAvatar.getTransformationsIndex(0):
                return None
            else:
                return ('head', None), ('torso', None), ('legs', None)

        return None

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        # start and stop animation must be in the range of the animation
        if arg == 1:
            # First, we gotta make sure the anim is a real one
            if MagicWord.validateArg(self, 0, allArgs[0], allArgs):
                # Then make sure its an int
                validType = MagicWord.validateArg(self, arg, entry, allArgs)
                if validType:
                    # Then we can check if its in between 0 and the # of frames in the animation
                    toon = base.localAvatar.getActiveTransformation()
                    if toon is None:
                        toon = base.localAvatar
                    return 0 <= int(entry) <= toon.getNumFrames(allArgs[0])
        return MagicWord.validateArg(self, arg, entry, allArgs)


class UnlockTrackAccess(MagicWord):
    aliases = ["trackaccess", 'settrackaccess']
    desc = "Unlocks the type of gags a toon has."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("toon-up", int, True), ("trap", int, True), ("lure", int, True), ("sound", int, True), ("throw", int, True),
                 ("squirt", int, True), ("drop", int, True)]

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg in list(range(6)):
            return ('0', 'Lock'), ('1', 'Unlock')
        return None

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg in list(range(6)):
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                track = int(entry)
                if track not in (0, 1):
                    return False
                return True
        return False

    def handleWord(self, invoker, avId, toon, *args):
        # args = toonup, trap, lure, sound, throw, squirt, drop
        for arg in args:
            if arg not in (0, 1):
                return "Invalid ID specified. Please specify a '1' if you want the track, and a '0' if you don't."

        if len(args) == 7:
            toon.b_setTrackAccess(list(args))
        else:
            return "Invalid amount of arguments! Please specify all 7 Gag Tracks."
        return "Tracks unlocked for {}.".format(toon.getName())


class UnlockTracks(MagicWord):
    aliases = ["tracks", 'settracks']
    desc = "Grants all the gag tracks, with the option of leaving one out."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("missingTrack", str, False, '')]

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg == 0:
            return ('None', None), ('Toon-Up', None), ('Trap', None), ('Lure', None), ('Sound', None), ('Throw', None), ('Squirt', None), ('Drop', None)
        return None

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 0:
            missingTrack = str(entry).lower()
            if missingTrack.isdigit():
                index = int(missingTrack)
                return 0 <= index <= 6
            if missingTrack not in ['none', 'null', '']:
                return missingTrack in MissingTrack2Index
            return True

        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        missingTrack = args[0].lower()

        # Set the target's gag tracks (they can specify if they wish to omit a track)
        gagTracks = [1, 1, 1, 1, 1, 1, 1]

        if missingTrack.isdigit():
            index = int(missingTrack)
            if index < 0 or index > 6:
                return 'Missing Gag track is invalid!'
            gagTracks[index] = 0
        elif missingTrack not in ['none', 'null', '']:
            if missingTrack in MissingTrack2Index:
                index = MissingTrack2Index[missingTrack]
                gagTracks[index] = 0
            else:
                return 'Missing Gag track is invalid!'
        toon.b_setTrackAccess(gagTracks)
        return "Unlocked your gag tracks!"


class Catalog(MagicWord):
    aliases = ["cattlelog"]
    desc = "Gives the toon a new catalog."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER

    def handleWord(self, invoker, avId, toon, *args):
        week = toon.catalogScheduleCurrentWeek + 1
        self.air.catalogManager.forceCatalog(toon, week, 0)
        return 'New catalog is arriving for {}.'.format(toon.getName())


class GetAccId(MagicWord):
    administrative = True
    aliases = ["accid", "accountid"]
    desc = "Gets the accountId from the target player."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    accessLevel = "MODERATOR"

    def handleWord(self, invoker, avId, toon, *args):
        accountId = toon.DISLid
        return "%s has the accountId of %d." % (toon.getName(), accountId)


class GetAvId(MagicWord):
    administrative = True
    aliases = ["avid", "avatarid"]
    desc = "Gets the avId from the target player."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    accessLevel = "MODERATOR"

    def handleWord(self, invoker, avId, toon, *args):
        return "%s has the avId of %d." % (toon.getName(), toon.getDoId())


class Announce(MagicWord):
    administrative = True
    aliases = ["announcement", "broadcast"]
    desc = "Broadcasts a message to the entire server."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("message", str, True)]
    accessLevel = "MODERATOR"
    affectRange = [MagicWordConfig.AFFECT_SELF]

    def handleWord(self, invoker, avId, toon, *args):
        message = args[0]
        from otp.avatar.DistributedPlayerAI import DistributedPlayerAI
        for doId, do in list(simbase.air.doId2do.items()):
            if isinstance(do, DistributedPlayerAI):
                if str(doId)[0] != str(simbase.air.districtId)[0]:
                    if do.getAccessLevel() >= 400:
                        do.d_setSystemMessage(0,
                                              str(invoker.getName()) + " (" + str(invoker.getDoId()) + "): " + message,
                                              WhisperPopup.WTAnnouncement)
                    else:
                        do.d_setSystemMessage(0, TTLocalizer.SystemMessagePrefix.format(message),
                                              WhisperPopup.WTAnnouncement)
        return "Announcement sent!"


class SystemMessage(MagicWord):
    administrative = True
    aliases = ["system", "sys", "sysmsg"]
    desc = "Broadcasts a message to the entire server in the form of a whisper."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("message", str, True)]
    accessLevel = "MODERATOR"
    affectRange = [MagicWordConfig.AFFECT_SELF]

    def handleWord(self, invoker, avId, toon, *args):
        message = args[0]
        from otp.avatar.DistributedPlayerAI import DistributedPlayerAI
        for doId, do in list(simbase.air.doId2do.items()):
            if isinstance(do, DistributedPlayerAI):
                if str(doId)[0] != str(simbase.air.districtId)[0]:
                    if do.getAccessLevel() >= 400:
                        do.d_setSystemMessage(0,
                                              str(invoker.getName()) + " (" + str(invoker.getDoId()) + "): " + message,
                                              WhisperPopup.WTSystem)
                    else:
                        do.d_setSystemMessage(0, TTLocalizer.SystemMessagePrefix.format(message), WhisperPopup.WTSystem)
        return "System message sent!"


class SetGravity(MagicWord):
    aliases = ["gravity"]
    desc = "Sets your gravity value."
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT
    arguments = [("gravity", float, False, ToontownGlobals.GravityValue * 2.0), ("override", bool, False, False)]

    def handleWord(self, invoker, avId, toon, *args):
        gravityValue = args[0]
        overrideWarning = args[1]

        if not base.localAvatar:
            return "Your Toon does not exist!"

        if hasattr(self.cr, 'pieBlitzGame') and self.cr.pieBlitzGame.isActive():
            return "Cannot set gravity during a Pie Blitz! Please wait until it is over."

        if hasattr(self.cr, 'hideAndSeekGame') and self.cr.hideAndSeekGame.isActive():
            return "Cannot set gravity during Hide and Seek! Please wait until it is over."

        if gravityValue < 1 and not overrideWarning:
            return "A value lower than 1 may crash your client."

        currentControls = base.localAvatar.controlManager.currentControls
        if hasattr(currentControls, 'setGravity'):
            currentControls.setGravity(gravityValue)
            if gravityValue == ToontownGlobals.NormalGravity:
                return "Gravity returned to normal."
            elif gravityValue == ToontownGlobals.AprilFoolsGravity:
                return "April fools gravity enabled!"
            return 'Gravity value set to {}.'.format(gravityValue)
        else:
            return 'Cannot set gravity in the current control mode.'


class GetPos(MagicWord):
    aliases = ["getxyz", "getposition"]
    desc = "Get the current position of the target."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    anyTarget = True

    def handleWord(self, invoker, avId, toon, *args):
        name = toon.getName()
        x, y, z = toon.getPos()
        return f"{name:}'s position is ({x:0.2f}, {y:0.2f}, {z:0.2f})."


class SetPos(MagicWord):
    aliases = ["setposition", "setxyz", "pos", "xyz"]
    desc = "Sets the current position of your Toon."
    advancedDesc = "Axis-Aligned relative coordinates can be prefixed with ~\n" \
                   "(e.g. ~ ~10 ~ will add 10 to the current Y position)\n\n" \
                   "Toon-Aligned relative coordinates can be prefixed with ^\n" \
                   "(e.g. ~ ^10 ~ will move the toon 10 units forward)\n\n" \
                   "Using ~ or ^ alone will maintain the current position\n" \
                   "(e.g. 32 13 ~ will set X to 32, Y to 13, and maintain your current Z)"
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT
    arguments = [("x", str, True), ("y", str, True), ("z", str, True)]

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if entry.startswith(('~', '^')) and entry not in '~^':
            # Using a relative position
            try:
                num = float(entry[1:])

                # todo: validate if the relative position will end up outside this range, not just
                #       if the inputted number is outside that range
                return -2500 <= num <= 2500

            except ValueError:
                return False
        elif entry in '~^':
            return True
        else:
            try:
                num = float(entry)
                return -2500 <= num <= 2500
            except ValueError:
                return False


    def handleWord(self, invoker, avId, toon, *args):
        if hasattr(self.cr, 'pieBlitzGame') and self.cr.pieBlitzGame.isActive():
            return "Cannot set position during a Pie Blitz! Please wait until it is over."

        if hasattr(self.cr, 'hideAndSeekGame') and self.cr.hideAndSeekGame.isActive():
            return "Cannot set position during Hide and Seek! Please wait until it is over."

        boss = toon.findBoss()
        if boss and boss.hardcore:
            return "You cannot cheat in this Boss Battle!"

        if not base.localAvatar:
            return "Your Toon does not exist!"

        strX = args[0]
        strY = args[1]
        strZ = args[2]

        try:
            if strX.startswith('~'):  # Relative (Axis Aligned)
                if strX != '~':
                    toonX = base.localAvatar.getX() + float(strX[1:])
                    if not -2500 <= toonX <= 2500:
                        return "This position is too far out!"
                    base.localAvatar.setX(toonX)
            elif strX.startswith('^'):  # Relative (Toon Aligned)
                if strX != '^':
                    base.localAvatar.setX(base.localAvatar, float(strX[1:]))
            else:  # Absolute
                toonX = float(strX)
                if not -2500 <= toonX <= 2500:
                    return "This position is too far out!"
                base.localAvatar.setX(toonX)

            if strY.startswith('~'):
                if strY != '~':
                    toonY = base.localAvatar.getY() + float(strY[1:])
                    if not -2500 <= toonY <= 2500:
                        return "This position is too far out!"
                    base.localAvatar.setY(toonY)
            elif strY.startswith('^'):  # Relative (Toon Aligned)
                if strY != '^':
                    base.localAvatar.setY(base.localAvatar, float(strY[1:]))
            else:
                toonY = float(strY)
                if not -2500 <= toonY <= 2500:
                    return "This position is too far out!"
                base.localAvatar.setY(toonY)

            if strZ.startswith('~'):
                if strZ != '~':
                    toonZ = base.localAvatar.getZ() + float(strZ[1:])
                    if not -2500 <= toonZ <= 2500:
                        return "This position is too far out!"
                    base.localAvatar.setZ(toonZ)
            elif strZ.startswith('^'):  # Relative (Toon Aligned)
                if strZ != '^':
                    base.localAvatar.setZ(base.localAvatar, float(strZ[1:]))
            else:
                toonZ = float(strZ)
                if not -2500 <= toonZ <= 2500:
                    return "This position is too far out!"
                base.localAvatar.setZ(toonZ)

        except ValueError:
            return "Invalid Arguments"
        return 'Position set to {0}, {1}, {2}.'.format(*base.localAvatar.getPos())


class GetHpr(MagicWord):
    aliases = ["getpitchrollyaw", "getrotation"]
    desc = "Get the current rotation of the target."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    anyTarget = True

    def handleWord(self, invoker, avId, toon, *args):
        name = toon.getName()
        h, p, r = toon.getHpr()
        return f"{name:}'s rotation is ({h:0.2f}, {p:0.2f}, {r:0.2f})."


class SetHpr(MagicWord):
    aliases = ["setpitchrollyaw", "pitchrollyaw", "hpr", "pry"]
    desc = "Sets the current pitch, roll, and yaw of your Toon."
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT
    arguments = [("h", float, True), ("p", float, True), ("r", float, True)]

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg in [0, 1, 2]:
            return ('-360', 'Minimum'), ('180', None), ('-90', None), ('-45', None), ('0', None), ('45', None), ('90', None), ('180', None), ('360', 'Maximum')
        return None

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg in [0, 1, 2]:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                track = float(entry)
                return -360 <= arg <= 360
        return False

    def handleWord(self, invoker, avId, toon, *args):
        toonH = args[0]
        toonP = args[1]
        toonR = args[2]
        if not base.localAvatar:
            return "Your Toon does not exist!"
        for arg in args:
            if not -360 <= arg <= 360:
                return "Invalid value specified! Please specify a value between -360 and 360."
        base.localAvatar.setHpr(toonH, toonP, toonR)
        return 'Pitch, roll, and yaw set to {0}, {1}, {2}.'.format(toonH, toonP, toonR)


class GetH(MagicWord):
    aliases = ["getdirection"]
    desc = "Returns the direction the target is facing."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    anyTarget = True

    def handleWord(self, invoker, avId, toon, *args):
        name = toon.getName()
        h = toon.getH()
        return f"{name:}'s direction is {h:0.2f}."


class SetH(MagicWord):
    aliases = ["h", "setdirection"]
    desc = "Sets the rotation value of your Toon."
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT
    arguments = [("h coordinate", int, True), ("part", str, False, 'toon')]

    def handleWord(self, invoker, avId, toon, *args):
        toonH = args[0]

        if not base.localAvatar:
            return "No Toon found!"

        part = args[1].lower()

        if part in ('head', 'torso', 'legs'):
            for lod in toon.getLODNames():
                base.localAvatar.getPart(part, lod).setH(toonH)
            return "Rotation value for part {} set to {}.".format(part, toonH)

        base.localAvatar.setH(toonH)
        return "Rotation value set to {}.".format(toonH)

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg == 1:
            return ('head', None), ('torso', None), ('legs', None)
        return None

class GetNumFrames(MagicWord):
    aliases = ["numframes", "frames"]
    desc = "Returns the number of frames in the given animation."
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT
    arguments = [("anim", str, False, '')]

    def handleWord(self, invoker, avId, toon, *args):
        anim = args[0]

        if not toon:
            return "No Toon found!"

        transformation = toon.getActiveTransformation()

        if not anim:
            anim = transformation.getCurrentAnim()
        if not anim:
            return "You are not currently animated, or this animation is not supported!"

        frames = transformation.getNumFrames(anim)

        return "There are {0} frames in the {1} animation.".format(str(frames), anim)

# TODO: validation (avIdShort) : check if npc, check if self
class TrueFriend(MagicWord):
    aliases = ["tf", "secretfriend"]
    desc = "Adds a Toon as a true friend."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("avIdShort", int, True)]
    accessLevel = "MODERATOR"

    def handleWord(self, invoker, avId, toon, *args):
        avIdShort = args[0]
        avIdFull = 400000000 - (300000000 - avIdShort)
        av = simbase.air.doId2do.get(avIdFull)
        if not av:
            return "avId not found/online!"
        if int(str(avIdFull)[:2]) >= 40:  # AI
            return "%s is an NPC!" % av.getName()
        if invoker == av:
            return "Cannot true friend yourself!"

        invoker.extendFriendsList(av.getDoId(), 1)
        av.extendFriendsList(invoker.getDoId(), 1)

        invoker.d_setFriendsList(invoker.getFriendsList())
        av.d_setFriendsList(av.getFriendsList())
        return "You are now true friends with {}.".format(av.getName())


class StartLeakDetector(MagicWord):
    aliases = ["leakdetector", "detectleak"]
    desc = "Starts a debug leak detector service that outputs warnings in output/logs."
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT

    def handleWord(self, invoker, avId, toon, *args):
        if base.cr.startLeakDetector() == True:
            return 'Leak detector has been enabled. Check output and/or logs.'
        return 'Leak detector already running! Restart your client to disable.'


class LogTaskMgr(MagicWord):
    aliases = ["taskmgr", "logtm"]
    desc = "Logs Panda3D task manager information. Used for debugging purposes."
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT

    def handleWord(self, invoker, avId, toon, *args):
        print(taskMgr)
        return 'Task Manager info printed. Check output and/or logs.'


class LogDoCount(MagicWord):
    aliases = ["docount"]
    desc = "Logs client distributed object count. Used for debugging purposes."
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT

    def handleWord(self, invoker, avId, toon, *args):
        base.cr.printObjectCount()
        return 'Client distributed object count printed. Check output and/or logs.'


class LogJobMgr(MagicWord):
    aliases = ["togglejobmgr", "jobmgr"]
    desc = "Logs job manager info. Used for debugging purposes."
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT

    def handleWord(self, invoker, avId, toon, *args):
        print(jobMgr)
        return 'Job Manager info printed. Check output and/or logs.'


class ToggleWire(MagicWord):
    aliases = ["togglewireframe", "wire", "wireframe"]
    desc = "Toggles wireframe view."
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT

    def handleWord(self, invoker, avId, toon, *args):
        base.toggleWireframe()
        return "Toggled wireframe."


class ToggleTextures(MagicWord):
    aliases = ["textures"]
    desc = "Toggles textures."
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT

    def handleWord(self, invoker, avId, toon, *args):
        base.toggleTexture()
        return 'Toggled textures.'


class ToggleVertexPainting(MagicWord):
    aliases = ["vertexpainting", "vertex", "toggleshading", "shading"]
    desc = "Toggles the display of vertex painting for objects within the scene."
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT

    def handleWord(self, invoker, avId, toon, *args):
        if not base.cr.vertexPaintingToggled:
            render.setColor(1, 1, 1)
            base.cr.vertexPaintingToggled = True
        else:
            render.clearColor()
            base.cr.vertexPaintingToggled = False
        return 'Toggled vertex painting.'


class ToggleShowVertices(MagicWord):
    aliases = ["showverts", "verts", "showvertices"]
    desc = "Toggles a mode that visualizes vertex density per screen area."
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT

    def handleWord(self, invoker, avId, toon, *args):
        base.toggleShowVertices()


class ToggleBackfaceCulling(MagicWord):
    aliases = ["togglebackface", "backface", "backfaceculling", "bculling"]
    desc = "Toggles the the culling mode in the scene. With backface culling enabled, the back faces of objects will " \
           "be see-through. Backface culling is enabled by default."
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT

    def handleWord(self, invoker, avId, toon, *args):
        base.toggleBackface()


class ToggleFrontfaceCulling(MagicWord):
    aliases = ["togglefrontface", "frontface", "frontfaceculling", "fculling"]
    desc = "Toggles the the culling mode in the scene. With frontface culling enabled, the front faces of objects " \
           "will be see-through."
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT

    def handleWord(self, invoker, avId, toon, *args):
        from panda3d.core import CullFaceAttrib
        if not base.cr.frontfaceCullingEnabled:
            render.setAttrib(CullFaceAttrib.make(CullFaceAttrib.MCullCounterClockwise))
            base.cr.frontfaceCullingEnabled = True
        else:
            render.clearAttrib(CullFaceAttrib)
            base.cr.frontfaceCullingEnabled = False


class ToggleTightBounds(MagicWord):
    aliases = ["tightbounds", "esp"]
    desc = "Toggles the display of a bounding box representing the 'tight' bounds of each node in the scene."
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT

    def handleWord(self, invoker, avId, toon, *args):
        if not base.cr.tightboundsToggled or base.cr.boundsToggled:
            for node in render.getChildren():
                node.showTightBounds()
            base.cr.tightboundsToggled = True
            base.cr.boundsToggled = False
        else:
            for node in render.getChildren():
                node.hideBounds()
            base.cr.tightboundsToggled = base.cr.boundsToggled = False


class ToggleBounds(MagicWord):
    aliases = ["bounds"]
    desc = "Toggles the display of the bounding volume of each node in the scene."
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT

    def handleWord(self, invoker, avId, toon, *args):
        if not base.cr.boundsToggled or base.cr.tightboundsToggled:
            for node in render.getChildren():
                node.showBounds()
            base.cr.boundsToggled = True
            base.cr.tightboundsToggled = False
        else:
            for node in render.getChildren():
                node.hideBounds()
            base.cr.boundsToggled = base.cr.tightboundsTarget = False


class RenderModeWireframe(MagicWord):
    desc = "Renders the scene with a wireframe overlay. Color values can be from 0 to 255. Thickness value can be " \
           "from 1 to 10. Default color is red."
    aliases = ["renderwire"]
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT
    arguments = [("red", int, False, 255), ("green", int, False, 0), ("blue", int, False, 0),
                 ("alpha", int, False, 255), ("thickness", float, False, 1.0)]

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg in [0, 1, 2, 3]:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                track = int(entry)
                return 0 <= arg <= 255
        elif arg == 4:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                track = float(entry)
                return 1.0 <= arg <= 10
        return False

    def handleWord(self, invoker, avId, toon, *args):
        for i in range(len(args)):
            arg = args[i]
            if i == 4:
                if not 1.0 <= arg < 10:
                    return f"Invalid thickness value: {arg}"
            elif arg > 255 or arg < 0:
                return f"Invalid color index: {arg}"

        r = args[0] / 255
        g = args[1] / 255
        b = args[2] / 255
        a = args[3] / 255
        thickness = args[4]
        for node in render.getChildren():
            node.setRenderModeFilledWireframe(LColor(r, g, b, a))
            node.setRenderModeThickness(thickness)
        return "Rendered the scene with a wireframe overlay."


class RenderModeNormal(MagicWord):
    desc = "Removes the wireframe render mode from the scene."
    aliases = ["clearwire"]
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT

    def handleWord(self, invoker, avId, toon, *args):
        for node in render.getChildren():
            node.setRenderModeFilled()
        return "Cleared wireframe."


class ToggleRenderCollisions(MagicWord):
    aliases = ["rendercollisions", "scenecollisions", "rendercol", "scenecol"]
    desc = "Displays collision bounds for currently rendered objects."
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT

    def handleWord(self, invoker, avId, toon, *args):
        if not base.cr.renderCollisionsToggled:
            render.findAllMatches('**/+CollisionNode').show()
            base.cr.renderCollisionsToggled = True
        else:
            render.findAllMatches('**/+CollisionNode').hide()
            base.cr.renderCollisionsToggled = False
        return 'Toggled displaying collision bounds for currently rendered objects.'


class ToggleFPS(MagicWord):
    aliases = ["fps", "showfps"]
    desc = "Toggles the frame rate meter."
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT

    def handleWord(self, invoker, avId, toon, *args):
        base.toggleFrameRateMeter(not base.frameRateMeter)
        return 'Toggled the frame rate meter.'


class GetAccessLevel(MagicWord):
    aliases = ["getaccess"]
    desc = "Gets the Access Level of a target."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    anyTarget = True
    accessLevel = "MODERATOR"

    def handleWord(self, invoker, avId, toon, *args):
        return "{}'s Access Level is {}.".format(toon.getName(), toon.getAccessLevel())


class ToggleAspect2D(MagicWord):
    aliases = ["a2d", 'aspect2d']
    desc = "Toggles aspect2d visibility on your client."
    advancedDesc = "This Magic Word will toggle the visibility of aspect2d, which represents the space used for " \
                   "rendering the 2d elements of the GUI."
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT

    def handleWord(self, invoker, avId, toon, *args):
        if hasattr(self.cr, 'hideAndSeekGame') and self.cr.hideAndSeekGame.isActive():
            return "aspect2d visibility toggling is disabled during Hide and Seek."
        base.toggleAspect2D()
        return "Toggled aspect2d visiblity."


class Ban(MagicWord):
    administrative = True
    aliases = ["bantoon", "bantarget"]
    desc = "Bans the target."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("minutes", int, False, 0), ("reason", str, False, "Not specified.")]
    accessLevel = "MODERATOR"
    affectRange = [MagicWordConfig.AFFECT_OTHER]

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 0:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                minutes = int(entry)
                return 1 <= minutes <= 20160
            return False
        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        from toontown.toon.DistributedToonAI import DistributedToonAI
        reason = args[1]
        minutes = args[0]

        if minutes:
            if not 1 <= minutes <= 20160:
                return f"Can't ban {toon.getName()} with {minutes} minutes. Specify a value between 1 and 20160 " \
                       f"minutes."

        if toon.getDoId() not in list(self.air.doId2do.keys()) or invoker.getDoId() not in list(
                self.air.doId2do.keys()):
            self.air.writeServerEvent('suspicious',
                                      issue = "Invalid invoker: %s and target: %s when trying to ban the target." % (
                                          invoker.getDoId(), toon.getDoId()))
            return "Failed to ban the target!"

        if not isinstance(toon, DistributedToonAI) and not isinstance(invoker, DistributedToonAI):
            return "You can only ban a Toon."
        else:
            toon.sendSetBan(reason = reason, target = toon, invoker = invoker, minutes = minutes)
            return f"Banned {toon.getName()}!"


class BanId(MagicWord):
    administrative = True
    aliases = ["bantoonid", "bantargetid"]
    desc = "Bans the target based on their Toon ID."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("id", int, True), ("minutes", int, False, 0), ("reason", str, False, "Not specified.")]
    accessLevel = "MODERATOR"

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 1:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                minutes = int(entry)
                return 1 <= minutes <= 20160
            return False
        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        from toontown.toon.DistributedToonAI import DistributedToonAI
        id = args[0]
        reason = args[2]
        minutes = args[1]

        toon = self.air.doId2do.get(id)
        if not toon:
            return "Invalid Toon ID specified, or the Toon is offline!"

        if minutes:
            if not 1 <= minutes <= 20160:
                return f"Can't ban {toon.getName()} with {minutes} minutes. Specify a value between 1 and 20160 " \
                       f"minutes."

        if toon.getDoId() not in list(self.air.doId2do.keys()) or invoker.getDoId() not in list(
                self.air.doId2do.keys()):
            self.air.writeServerEvent('suspicious',
                                      issue = "Invalid invoker: %s and target: %s when trying to ban the target." % (
                                          invoker.getDoId(), toon.getDoId()))
            return "Failed to ban the target!"

        if not isinstance(toon, DistributedToonAI) and not isinstance(invoker, DistributedToonAI):
            return "You can only ban a Toon."
        else:
            toon.sendSetBan(reason = reason, target = toon, invoker = invoker, minutes = minutes)
            return f"Banned {toon.getName()}!"


class Kick(MagicWord):
    administrative = True
    aliases = ["kicktoon", "kicktarget", "boot"]
    desc = "Kicks the target."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("reason", str, False, "Not specified.")]
    accessLevel = "MODERATOR"
    affectRange = [MagicWordConfig.AFFECT_OTHER]

    def handleWord(self, invoker, avId, toon, *args):
        from toontown.toon.DistributedToonAI import DistributedToonAI
        reason = args[0]

        if toon.getDoId() not in list(self.air.doId2do.keys()) or invoker.getDoId() not in list(
                self.air.doId2do.keys()):
            self.air.writeServerEvent('suspicious',
                                      issue = "Invalid invoker: %s and target: %s when trying to kick target." % (
                                          invoker.getDoId(), toon.getDoId()))
            return "Failed to kick avatar!"

        # Verify that we're a toon.
        if not isinstance(toon, DistributedToonAI) and not isinstance(invoker, DistributedToonAI):
            return "You can only kick an avatar."
        else:
            if toon.getDoId() == invoker.getDoId():
                return "You can\'t kick yourself, %s." % toon.getName()
            else:
                toon.sendSetKick(reason = reason, target = toon, silent = 3)
                return "Kicked %s!" % toon.getName()


class ToggleMute(MagicWord):
    aliases = ["setmute", "mutetoon", "toonmute", "mute"]
    desc = "Toggles a mute on the target Toon with a specified option(on, off, check). If on, you can provide a time " \
           "(in minutes) and a reason the Toon is muted for."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("action", str, False, 'on'), ("minutes", int, False, 60), ("reason", str, False, 'Not specified.')]
    affectRange = [MagicWordConfig.AFFECT_OTHER]
    accessLevel = "MODERATOR"

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg == 0:
            return ('on', 'Mutes the target Toon.'), ('off', 'Unmutes the target Toon.'), ('get', 'Determine if the target Toon is muted.')
        if arg == 1:
            return ('0', 'Permanent Mute'), ('15', '15 Minutes'), ('30', '30 Minutes'), ('45', '45 Minutes'), ('60', '60 Minutes'), ('120', '2 Hours'), ('10080', '1 Week'), ('20160', '2 Weeks (Maximum)')
        return None

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 0:
            action = str(entry).lower()
            if action in ('get', 'g', 'check', 'off', 'stop', 'finish', 'end', 'bye', 'adios', 'cya', 'begone', 'no', 'n',
                          'on', 'start', 'begin', 'yes', 'y'):
                return True
            return False
        elif arg == 1:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                minutes = int(entry)
                return 0 <= minutes <= 20160
            return False
        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        action = args[0].lower()

        if invoker == toon:
            return "You cannot toggle Mute on yourself!"

        if action in ('get', 'g', 'check'):
            muted = toon.getMuted()
            if muted:
                minutesLeft = 0
                if toon.mutedTask:
                    minutesLeft = abs(toon.mutedTask.delayTime) / 60

                    # We are about to become unmuted with less than 1 second left
                    # but we don't want to lie and say that we are perma-muted
                    if minutesLeft < 1 and minutesLeft > 0:
                        return f"{toon.getName()} is about to become unmuted."

                    # Round to the nearest integer for the sake of a clean minute string.
                    minutesLeft = round(minutesLeft)

                if minutesLeft == 0:
                    return f"{toon.getName()} is permanently muted."

                if minutesLeft == 1:
                    minuteStr = 'minute'
                else:
                    minuteStr = 'minutes'
                return f"{toon.getName()} is muted for {minutesLeft} {minuteStr}."

            return f"{toon.getName()} is not muted."

        if action in ('off', 'stop', 'finish', 'end', 'bye', 'adios', 'cya', 'begone', 'no', 'n'):
            toon.sendSetUnmute(target = toon)
            return f"Mute has been toggled off for {toon.getName()}"

        if action in ('on', 'start', 'begin', 'yes', 'y'):
            minutes = args[1]
            reason = args[2]

            if minutes < 0 or minutes > 20160:
                return "Mute time must be between 0 (permanent) and 21610 (2 weeks) minutes."

            toon.sendSetMute(reason = reason, target = toon, invoker = invoker, minutes = minutes)

            if not minutes:
                return f"{toon.getName()} is now PERMANENTLY muted!"

            if minutes == 1:
                minuteStr = 'minute'
            else:
                minuteStr = 'minutes'
            return f"{toon.getName()} is now muted for {minutes} {minuteStr}!"

        return f"Unknown action: {action} for mute command."


class GetInvasionStatus(MagicWord):
    aliases = ['invasionstatus']
    desc = "Returns the number of cogs remaining in an invasion."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    affectRange = [MagicWordConfig.AFFECT_SELF]

    def handleWord(self, invoker, avId, toon, *args):
        invasionMgr = simbase.air.suitInvasionManager

        if not invasionMgr.getInvading():
            return "The Cogs are currently not invading Toontown!"

        cogList = invasionMgr.getInvadingCogList()

        if ZoneUtil.isToonHQ(invoker.zoneId):
            from toontown.toon.DistributedNPCPeriscopeAI import DistributedNPCPeriscopeAI
            toons = self.air.getObjectsOfClassInZone(self.air.districtId, invoker.zoneId,
                                                     DistributedNPCPeriscopeAI)
            for toon in list(toons.values()):
                toon.d_speakAboutInvasionStatus(cogList[0], cogList[1], cogList[2], ToontownGlobals.SuitInvasionUpdate, invasionMgr.mega)

        return f"Cogs: {cogList[0]}, CogsRemaining: {invasionMgr.numCogsRemaining}, Special: {cogList[1]}, Virtual: {cogList[2]}, Mega: {invasionMgr.mega}"


class RevealMap(MagicWord):
    desc = "Reveals the entire map in the Sellbot Field Office maze game."
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT

    def handleWord(self, invoker, avId, toon, *args):
        mazeGame = None
        from toontown.cogdominium.DistCogdoMazeGame import DistCogdoMazeGame
        for do in list(base.cr.doId2do.values()):
            if isinstance(do, DistCogdoMazeGame):
                if invoker.doId in do.getToonIds():
                    mazeGame = do
                    break

        if mazeGame:
            mazeGame.game.guiMgr.mazeMapGui.showExit()
            mazeGame.game.guiMgr.mazeMapGui.revealAll()
            return "Map revealed!"

        return "You are not in the Maze Game!"


class EndMaze(MagicWord):
    aliases = ["endmazegame"]
    desc = "Ends the maze game in a Sellbot Field Office."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER

    def handleWord(self, invoker, avId, toon, *args):
        mazeGame = None
        from toontown.cogdominium.DistCogdoMazeGameAI import DistCogdoMazeGameAI
        for do in list(simbase.air.doId2do.values()):
            if isinstance(do, DistCogdoMazeGameAI):
                if invoker.doId in do.getToonIds():
                    mazeGame = do
                    break

        if mazeGame:
            mazeGame.openDoor()
            return "Completed the Maze Game."

        return "You are not in the Maze Game!"


class ToggleBurnFuel(MagicWord):
    aliases = ["burnfuel", "toggleinfinitefuel", "infinitefuel"]
    desc = "Toggles whether or not fuel is burned in the Lawbot Field Office flying game."
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT

    def handleWord(self, invoker, avId, toon, *args):
        flyingGame = None
        from toontown.cogdominium.DistCogdoFlyingGame import DistCogdoFlyingGame
        for do in list(base.cr.doId2do.values()):
            if isinstance(do, DistCogdoFlyingGame):
                if invoker.doId in do.getToonIds():
                    flyingGame = do
                    break

        if flyingGame and hasattr(flyingGame.game, 'localPlayer'):
            flyingGame.game.localPlayer.toggleBurnFuel()
            if flyingGame.game.localPlayer.burnFuel:
                return "Now burning fuel!"
            return "No longer burning fuel."

        return "You are not in the Flying Game!"

class SpawnBuilding(MagicWord):
    aliases = ["building", "spawnbldg", "bldg", "buildingspawn", "bldgspawn"]
    desc = "Spawns a Cog Building with the given difficulty, floors, and Cog departments(separated by commas)."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    affectRange = [MagicWordConfig.AFFECT_SELF]
    arguments = [("difficulty", int, False, 0), ("numFloors", int, False, 1), ("department(s)", str, False, "bossbot")]

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg == 0:
            return ((str(x), None) for x in range(9))
        elif arg == 1:
            return ('1', None), ('2', None), ('3', None), ('4', None), ('5', None), ('10', None), ('25', None), ('50', None), ('100', None), ('200', None), ('500', None), ('999', None)
        elif arg == 2:
            return ('bossbot', None), ('lawbot', None), ('cashbot', None), ('sellbot', None), ('sellbot,bossbot', 'Sample Mixed Building')
        return None

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 0:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                difficulty = int(entry)
                return 0 <= difficulty <= 8
            return False 
        elif arg == 1:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                numFloors = int(entry)
                return 1 <= numFloors <= 999
            return False 
        elif arg == 2:
            allEntries = entry.split(',')
            for x in allEntries:
                if x not in SuitDNA.suitDeptArgs2Dept:
                    return False
            return True

        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        difficulty = min(args[0], 8)
        numFloors = args[1]
        if not 1 <= numFloors <= 999:
            return f"Unable to spawn a Cog Building with {numFloors} floors!"
        departmentInput = args[2].split(",")
        departments = []
        for department in departmentInput:
            department = department.lower()
            if department in SuitDNA.suitDeptArgs2Dept:
                realDepartment = SuitDNA.suitDeptArgs2Dept[department]
                if realDepartment in departments:
                    continue
                departments.append(realDepartment)
        if not departments:
            return "Unable to spawn a Cog Building. All given departments are invalid!"

        streetId = ZoneUtil.getBranchZone(invoker.zoneId)
        if streetId not in self.air.suitPlanners:
            return f"Street {streetId} is unknown."
        building = invoker.findClosestDoor()
        if building == None:
            return f"Unable to spawn a Cog Building in this location."
        building.suitTakeOver(departments, difficulty, numFloors)
        return f"Successfuly spawned Cog Building with difficulty {difficulty}, numFloors {numFloors}, and departments {departments}!"

class RequestNumBldgCogs(MagicWord):
    aliases = ["requestnumbldgcogsnextfloor", "reqnumbldgcogsnextfloor", "reqnumbldgcogs", "requestnumcogsnextfloor",
               "reqnumcogsnextfloor", "numcogsnextfloor", "bldgnext", "bldgcog", "bldgcogs", "numbldgcog", "numbldgcogs"]
    desc = "Request the number of Cogs that will be in the next Cog Building floor."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    affectRange = [MagicWordConfig.AFFECT_SELF]
    arguments = [("numCogs", int, False, 1)]

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg == 0:
            return ((str(x), None) for x in range(1, 41))
        return None

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 0:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                numCogs = int(entry)
                return 1 < numCogs < 40
            return False
        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        numCogs = args[0]
        if numCogs < 0:
            numCogs = 1
        if numCogs > 40:
            numCogs = 40

        invoker.setNumRequestedBldgCogs(numCogs)
        return f"Your next visited Cog Building floor will now have {numCogs} Cogs requested."

class SpawnFO(MagicWord):
    aliases = ["fo", "spawncogdo", "cogdo"]
    desc = "Spawns a Field Office with the given type, difficulty, and battle floors(1-2)."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("type", str, True), ("difficulty", int, False, 0), ("numBattleFloors", int, False, 2)]

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg == 0:
            return ('s', 'Sellbot'), ('l', 'Lawbot')
        elif arg == 1:
            return ((str(x), None) for x in range(22))
        elif arg == 2:
            return ('1', None), ('2', None)
        return None

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 0:
            return str(entry).lower() in ['s', 'l']
        elif arg == 1:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                difficulty = int(entry)
                return 0 < difficulty < 21
            return False
        elif arg == 2:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                numBattleFloors = int(entry)
                return 1 < numBattleFloors < 2
            return False
        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        from toontown.building import SuitBuildingGlobals
        track = args[0]
        difficulty = args[1]
        numBattleFloors = args[2]
        if numBattleFloors < 1:
            numBattleFloors = 1
        elif numBattleFloors > 2:
            numBattleFloors = 2

        tracks = ('s', 'l')
        if track not in tracks:
            return "Invalid Field Office type! Supported types are 's' and 'l'."
        if not 0 <= difficulty < len(SuitBuildingGlobals.SuitBuildingInfo):
            return "Invalid difficulty index. Please specify a value between 0 and {}.".format(
                len(SuitBuildingGlobals.SuitBuildingInfo) - 1)

        if numBattleFloors == 1:
            floorStr = 'floor'
        else:
            floorStr = 'floors'

        try:
            # If we're in the Outskirts, be lenient with the visgroups
            # Use the branch zone because sometimes we can be in other zones
            lenient = False
            if ZoneUtil.getCanonicalBranchZone(invoker.zoneId) == ToontownGlobals.ToontownOutskirts:
                lenient = True
            building = invoker.findClosestDoor(lenient)
        except KeyError:
            return "You\'re not on a street!"
        if building is None:
            return "Unable to spawn a {0} Field Office with a difficulty of {1} and {2} battle {3}.".format(
                    ToontownGlobals.Dept2Dept.get(track), difficulty, numBattleFloors, floorStr)

        building.cogdoTakeOver(track, difficulty, numBattleFloors)
        return "Successfully spawned a {0} Field Office with a difficulty of {1} and {2} battle {3}.".format(
                ToontownGlobals.Dept2Dept.get(track), difficulty, numBattleFloors, floorStr)


class SetCEIndex(MagicWord):
    aliases = ["setce", "ce", "cheesyeffect", "setcheesyeffect"]
    desc = "Sets the Cheesy Effect of the target."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("index", int, False, 0), ("zoneId", int, False, 0), ("duration", int, False, 0)]

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg == 0:
            return CheesyEffects
        return None

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 0:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                index = int(entry)
                return 0 < index < 21
            return False
        elif arg == 1:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                zoneId = int(entry)
                if zoneId == 0:
                    return True
                return 100 < zoneId < ToontownGlobals.DynamicZonesBegin
            return False

        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        index = args[0]
        zoneId = args[1]
        duration = args[2]

        maxIndex = 21
        if not 0 <= index <= maxIndex:
            return f"Invalid value {index} specified for Cheesy Effect. Please specify a value between" \
                   f" 0 and {maxIndex}."
        if zoneId != 0 and not 100 < zoneId < ToontownGlobals.DynamicZonesBegin:
            return "Invalid zoneId specified."
        toon.b_setCheesyEffect(index, zoneId, time.time() + duration)
        return f"Cheesy effect {index} set for {toon.getName()} with a time of {duration}."


class SetFishingRod(MagicWord):
    aliases = ["rod", "setrod", "fishingrod", "fishrod", "setfishrod"]
    desc = "Sets the target's fishing rod value."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("rodVal", int, True)]

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg == 0:
            return ('0', 'Twig Rod'), ('1', 'Bamboo Rod'), ('2', 'Hardwood Rod'), ('3', 'Steel Rod'), ('4', 'Gold Rod')
        return None

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 0:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                rodVal = int(entry)
                return 0 <= rodVal <= 4
            return False 

        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        rodVal = args[0]
        if not 0 <= rodVal <= 4:
            return "Rod value must be between 0 and 4."
        toon.b_setFishingRod(rodVal)
        return "Rod changed to type {0} for {1}.".format(rodVal, toon.getName())


class SetFishingBucket(MagicWord):
    aliases = ["fishbucket", "bucket", "maxtank"]
    desc = "Sets the target's max fishing bucket value."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("tankVal", int, True)]

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg == 0:
            return ('20', 'Minimum'), ('30', None), ('40', None), ('50', None), ('60', None), ('70', None), ('80', None), ('90', None), ('99', 'Maximum')
        return None

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 0:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                tankVal = int(entry)
                return 20 <= tankVal <= 99
            return False 

        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        tankVal = args[0]
        if not 20 <= tankVal <= 99:
            return "Max fish bucket value must be between 20 and 99"
        toon.b_setMaxFishTank(tankVal)
        return "Max size of fish bucket changed to {0} for {1}.".format(tankVal, toon.getName())


class SetPlayRate(MagicWord):
    aliases = ["playrate"]
    desc = "Sets the target's play rate."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("playRate", float, False, 1.0)]

    def handleWord(self, invoker, avId, toon, *args):
        rate = args[0]
        rate = max(min(rate, 1000.0), -1000.0)
        toon.d_setAnimPlayRate(rate)
        if rate == 1:
            return "Set playrate to normal!"

        return "Set {0}'s play rate to {1}.".format(toon.getName(), rate)


class SetName(MagicWord):
    aliases = ["name", "nick"]
    desc = "Sets the target's name."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("name", str, True)]

    def handleWord(self, invoker, avId, toon, *args):
        nameStr = args[0].strip()
        oldName = toon.getName()

        if not nameStr:
            return "Cannot change %s's name to nothing!" % oldName

        if oldName == nameStr:
            return f"Name is already {oldName}"

        if len(nameStr) > 64:
            return "Cannot change %s's name to %s. Name too long." % (oldName, nameStr)

        if not re.match(ToontownGlobals.ToonNameRegex, nameStr) and not __debug__:
            return "Cannot change %s's name to %s. Invalid characters specified." % (oldName, nameStr)

        toon.b_setName(nameStr)
        return "Changed %s's name to %s!" % (oldName, nameStr)


class SetHat(MagicWord):
    aliases = ["hat"]
    desc = "Sets the hat of the target."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("id", int, True), ("textureId", int, False, 0)]

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg == 0:
            return ((str(x), ToonDNA.HatModels[x]) for x in range(len(ToonDNA.HatModels)))
        elif arg == 1:
            hatStylesDescriptions = list(TTLocalizer.HatStylesDescriptions.values())
            return ((str(x), hatStylesDescriptions[x]) for x in range(len(hatStylesDescriptions)))
        return None

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 0:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                id = int(entry)
                return 0 <= id <= len(ToonDNA.HatModels) - 1
        elif arg == 1:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                textureId = int(entry)
                return 0 <= textureId <= len(ToonDNA.HatTextures) - 1
        return False

    def handleWord(self, invoker, avId, toon, *args):
        hatId = args[0]
        hatTex = args[1]
        hatIdListLength = len(ToonDNA.HatModels) - 1
        hatTextureListLength = len(ToonDNA.HatTextures) - 1

        if not 0 <= hatId <= hatIdListLength:
            return "Invalid hat specified. Must be between 0 and %d." % hatIdListLength
        if not 0 <= hatTex <= hatTextureListLength:
            return "Invalid hat texture specified. Must be between 0 and %d." % hatTextureListLength
        toon.b_setHat(hatId, hatTex, 0)
        self.air.updateOnlineAvatar(toon)
        return "{0}'s hat has been set to {1} with texture {2}.".format(toon.getName(), hatId, hatTex)


class SetGlasses(MagicWord):
    aliases = ["glasses"]
    desc = "Sets the glasses of the target."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("id", int, True), ("textureId", int, False, 0)]

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg == 0:
            return ((str(x), ToonDNA.GlassesModels[x]) for x in range(len(ToonDNA.GlassesModels)))
        elif arg == 1:
            glassesStyleDescriptions = list(TTLocalizer.GlassesStylesDescriptions.values())
            return ((str(x), glassesStyleDescriptions[x]) for x in range(len(glassesStyleDescriptions)))
        return None

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 0:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                id = int(entry)
                return 0 <= id <= len(ToonDNA.GlassesModels) - 1
        elif arg == 1:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                textureId = int(entry)
                return 0 <= textureId <= len(ToonDNA.GlassesTextures) - 1
        return False

    def handleWord(self, invoker, avId, toon, *args):
        glassesId = args[0]
        glassesTex = args[1]
        glassesIdListLength = len(ToonDNA.GlassesModels) - 1
        glassesIdTexLength = len(ToonDNA.GlassesTextures) - 1

        if not 0 <= glassesId <= glassesIdListLength:
            return "Invalid glasses specified. Must be between 0 and %d." % glassesIdListLength
        if not 0 <= glassesTex <= glassesIdTexLength:
            return "Invalid glasses texture specified. Must be between 0 and %d." % glassesIdTexLength
        toon.b_setGlasses(glassesId, glassesTex, 0)
        self.air.updateOnlineAvatar(toon)
        return "{0}'s Glasses have been set to {1} with texture {2}.".format(toon.getName(), glassesId, glassesTex)


class SetBackpack(MagicWord):
    aliases = ["backpack"]
    desc = "Sets the backpack of the target."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("id", int, True), ("textureId", int, False, 0)]

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg == 0:
            return ((str(x), ToonDNA.BackpackModels[x]) for x in range(len(ToonDNA.BackpackModels)))
        elif arg == 1:
            backpackStyleDescriptions = list(TTLocalizer.BackpackStylesDescriptions.values())
            return ((str(x), backpackStyleDescriptions[x]) for x in range(len(backpackStyleDescriptions)))
        return None

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 0:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                id = int(entry)
                return 0 <= id <= len(ToonDNA.BackpackModels) - 1
        elif arg == 1:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                textureId = int(entry)
                return 0 <= textureId <= len(ToonDNA.BackpackTextures) - 1
        return False

    def handleWord(self, invoker, avId, toon, *args):
        bpId = args[0]
        bpTex = args[1]
        backpackIdListLength = len(ToonDNA.BackpackModels) - 1
        backpackTexListLength = len(ToonDNA.BackpackTextures) - 1

        if not 0 <= bpId <= backpackIdListLength:
            return "Invalid backpack specified. Must be between 0 and %d." % backpackIdListLength
        if not 0 <= bpTex <= backpackTexListLength:
            return "Invalid backpack texture specified. Must be between 0 and %d." % backpackTexListLength
        toon.b_setBackpack(bpId, bpTex, 0)
        self.air.updateOnlineAvatar(toon)
        return "{0}'s backpack has been set to {1} with texture {2}.".format(toon.getName(), bpId, bpTex)


class SetShoes(MagicWord):
    aliases = ["shoes"]
    desc = "Sets the shoes of the target."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("id", int, True), ("textureId", int, False, 0)]

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg == 0:
            return ((str(x), ToonDNA.ShoesModels[x]) for x in range(len(ToonDNA.ShoesModels)))
        elif arg == 1:
            shoeStyleDescriptions = list(TTLocalizer.ShoesStylesDescriptions.values())
            return ((str(x), shoeStyleDescriptions[x]) for x in range(len(shoeStyleDescriptions)))
        return None

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 0:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                id = int(entry)
                return 0 <= id <= len(ToonDNA.ShoesModels) - 1
        elif arg == 1:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                textureId = int(entry)
                return 0 <= textureId <= len(ToonDNA.ShoesTextures) - 1
        return False

    def handleWord(self, invoker, avId, toon, *args):
        shoesId = args[0]
        shoesTex = args[1]
        shoesIdListLength = len(ToonDNA.ShoesModels) - 1
        shoesTexListLength = len(ToonDNA.ShoesTextures) - 1

        if not 0 <= shoesId <= shoesIdListLength:
            return "Invalid shoe type specified. Must be between 0 and %d." % shoesIdListLength
        if not 0 <= shoesTex <= shoesTexListLength:
            return "Invalid shoe specified. Must be between 0 and %d." % shoesTexListLength
        toon.b_setShoes(shoesId, shoesTex, 0)
        self.air.updateOnlineAvatar(toon)
        return "{0}'s shoes have been set to {1} with texture {2}.".format(toon.getName(), shoesId, shoesTex)


class ClearAccessories(MagicWord):
    aliases = ["removeallaccessories", "removeaccessories"]
    desc = "Clears all the accessories of the target."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER

    def handleWord(self, invoker, avId, toon, *args):
        toon.b_setHat(0, 0, 0)
        toon.b_setGlasses(0, 0, 0)
        toon.b_setBackpack(0, 0, 0)
        toon.b_setShoes(0, 0, 0)
        self.air.updateOnlineAvatar(toon)
        return "Cleared the target's accessories."


class SetInventory(MagicWord):
    aliases = ["inventory", "gaginventory"]
    desc = "Sets target's gag inventory. Can reset (clear) inventory or restock."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("command", str, False, "restock"), ("level", int, False, 6), ("track", int, False, 6)]

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg == 0:
            return ('restock', 'Restocks gags for specified track(s)'), ('clear', 'Clears gags for specified track(s)')
        return None

    def handleWord(self, invoker, avId, toon, *args):
        boss = toon.findBoss()
        if boss and boss.hardcore:
            return "You cannot cheat in this Boss Battle!"

        type = args[0]
        level = args[1]
        track = args[2]

        inventory = toon.inventory
        if type in ("reset", "clear", "clean", "remove"):
            maxLevelIndex = level or 5
            if not 0 <= maxLevelIndex < len(ToontownBattleGlobals.Levels[0]):
                return "Invalid max level index: {0}".format(maxLevelIndex)
            targetTrack = -1 or track
            if not -1 <= targetTrack < len(ToontownBattleGlobals.Tracks):
                return "Invalid target track index: {0}".format(targetTrack)
            for track in range(0, len(ToontownBattleGlobals.Tracks)):
                if (targetTrack == -1) or (track == targetTrack):
                    inventory.inventory[track][:maxLevelIndex + 1] = [0] * (maxLevelIndex + 1)
            toon.b_setInventory(inventory.makeNetString())
            if targetTrack == -1:
                return "Inventory cleared."
            else:
                return "Inventory cleared for target track index: {0}".format(targetTrack)
        elif type in ("restock", "restore", "refill", "resupply", "replenish", "supply", "fill"):
            maxLevelIndex = level or 5
            if not 0 <= maxLevelIndex < len(ToontownBattleGlobals.Levels[0]):
                return "Invalid max level index: {0}".format(maxLevelIndex)
            targetTrack = -1 or track
            if not -1 <= targetTrack < len(ToontownBattleGlobals.Tracks):
                return "Invalid target track index: {0}".format(targetTrack)
            if (targetTrack != -1) and (not toon.hasTrackAccess(targetTrack)):
                return "The target doesn't have target track index: {0}".format(targetTrack)
            inventory.NPCMaxOutInv(targetTrack = targetTrack, maxLevelIndex = maxLevelIndex)
            toon.b_setInventory(inventory.makeNetString())
            if targetTrack == -1:
                return "Inventory restocked."
            else:
                return "Inventory restocked for target track index: {0}".format(targetTrack)
        else:
            try:
                targetTrack = int(type)
            except:
                return "Invalid first argument."
            if not toon.hasTrackAccess(targetTrack):
                return "The target Toon doesn't have target track index: {0}".format(targetTrack)
            maxLevelIndex = level or 6
            if not 0 <= maxLevelIndex < len(ToontownBattleGlobals.Levels[0]):
                return "Invalid max level index: {0}".format(maxLevelIndex)
            for _ in range(track):
                inventory.addItem(targetTrack, maxLevelIndex)
                toon.b_setInventory(inventory.makeNetString())
            return "Restored {0} Gags to: {1}, {2}.".format(track, targetTrack, maxLevelIndex)


class ToggleGhost(MagicWord):
    administrative = True
    aliases = ["ghost"]
    desc = "Toggle's invisibility for the target"
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    accessLevel = 'MODERATOR'

    def handleWord(self, invoker, avId, toon, *args):
        if toon.ghostMode == 0:
            toon.b_setGhostMode(2)
            return "{} has gone ghost!".format(toon.getName())
        else:
            toon.b_setGhostMode(0)
            return "{} is no longer ghost!".format(toon.getName())


class SetSrgbEncode(MagicWord):
    aliases = ["srgb"]
    desc = "Applies the inverse sRGB EOTF to the output, unless the window already has an sRGB framebuffer"
    arguments = [("force", bool, False, False)]
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT

    def handleWord(self, invoker, avId, toon, *args):
        force = args[0]
        if not base.cr.sRGBEnabled:
            filterSupported: bool = base.filters.setSrgbEncode(force = force)
            if not filterSupported:
                # See: https://docs.panda3d.org/1.10/python/programming/render-to-texture/common-image-filters
                self.notify.warning("Video card doesn't support the sRGB filter.")
                return "Failed to enable the sRGB filter. Please check if your hardware is supported."
            base.cr.sRGBEnabled = True
            return "Applied the sRGB filter!"
        else:
            base.filters.delSrgbEncode()
            base.cr.sRGBEnabled = False
            return "Reverted the sRGB filter!"


class SetHighDynamicRange(MagicWord):
    aliases = ["hdr", "togglehdr", "highdynamicrange"]
    desc = "Toggles high dynamic range."
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT

    def handleWord(self, invoker, avId, toon, *args):
        if not base.cr.HDREnabled:
            filterSupported: bool = base.filters.setHighDynamicRange()
            if not filterSupported:
                self.notify.warning("Video card doesn't support the HDR filter.")
                return "Failed to enable HDR. Please check if your hardware is supported."
            base.cr.HDREnabled = True
            return "HDR Enabled!"
        else:
            base.filters.delHighDynamicRange()
            base.cr.HDREnabled = False
            return "HDR Disabled!"


class SetInverted(MagicWord):
    aliases = ["negative", "inverted", "invert", "setinvert", "setnegative", "toggleinvert", "toggleinverted"]
    desc = "Inverts the colors on the display. Run this magic word again to disable the effect."
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT

    def handleWord(self, invoker, avId, toon, *args):
        if not base.cr.invertedEnabled:
            filterSupported: bool = base.filters.setInverted()
            if not filterSupported:
                self.notify.warning("Video card doesn't support the inverted filter.")
                return "Failed to invert the scene. Please check if your hardware is supported."
            base.cr.invertedEnabled = True
            return "Inverted the scene!"
        else:
            base.filters.delInverted()
            base.cr.invertedEnabled = False
            return "Scene is back to normal!"


class ToggleSGMeter(MagicWord):
    aliases = ["sgmeter"]
    desc = "Toggles a meter that analyzes rendered objects in the Scene Graph."
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT

    def handleWord(self, invoker, avId, toon, *args):
        if not base.cr.SGMeterToggled:
            base.setSceneGraphAnalyzerMeter(True)
            base.cr.SGMeterToggled = True
        else:
            base.setSceneGraphAnalyzerMeter(False)
            base.cr.SGMeterToggled = False
        return 'Toggled the Scene Graph analyzer meter.'


class ToggleStereo(MagicWord):
    aliases = ["stereo"]
    desc = "Toggles a stereoscopic 3d effect on the game."
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT

    def handleWord(self, invoker, avId, toon, *args):
        base.toggleStereo()
        return 'Toggled the stereoscopic 3d effect.'


class ToggleGuiPopup(MagicWord):
    aliases = ["guipopup"]
    desc = "Toggles the bounds of on-screen GUI."
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT

    def handleWord(self, invoker, avId, toon, *args):
        if base.cr.guiPopupShown:
            base.mouseWatcherNode.hideRegions()
            base.cr.guiPopupShown = 0
        else:
            base.mouseWatcherNode.showRegions(render2d, 'gui-popup', 0)
            base.cr.guiPopupShown = 1

# TODO: validation on local avatar, nearby target if it exists
class SetGM(MagicWord):
    administrative = True
    aliases = ["gmicon", "gm"]
    desc = "Set the target's GM Icon."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("id", int, True), ("name", bool, False, False)]
    accessLevel = 'MODERATOR'

    def handleWord(self, invoker, avId, toon, *args):
        gmId = args[0]
        name = args[1]

        # Reminder - Add a better system for making sure only team members have team member GM icons

        if not 0 <= gmId <= 8:
            return "Invalid GM Icon specified."

        accessLevel = toon.getAccessLevel()
        if gmId > 3 and accessLevel < 600:
            return "Your Access Level is too low to use this GM icon."
        else:
            if (accessLevel < 400 and gmId > 2) or (accessLevel < 500 and gmId > 3):
                return "Your Access Level is too low to use this GM icon."

        if toon.isGM() and gmId != 0:
            toon.b_setGM(0, name)
        elif toon.isGM and gmId == 0:
            toon.b_setGM(0, True)

        toon.b_setGM(gmId, name)

        return "You have set %s to GM type %s." % (toon.getName(), gmId)


class SetTickets(MagicWord):
    aliases = ["tickets"]
    desc = "Sets the target's amount of racing tickets."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("val", int, True)]

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg == 0:
            return ('0', 'None (Minimum)'), ('100', None), ('1000', None), ('2500', None), ('5000', None), ('7500', None), ('10000', None), ('25000', None), ('50000', None), ('75000', None), ('99999', 'Maximum')
        return None

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 0:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                val = int(entry)
                return 0 <= val <= 99999
            return False
        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        tixVal = args[0]
        if not 0 <= tixVal <= 99999:
            return "Ticket value out of range. Must be between 0 and 99999"
        toon.b_setTickets(tixVal)
        return "%s's tickets were set to %s." % (toon.getName(), tixVal)


class TransformMario(MagicWord):
    aliases = ['mario']
    desc = 'Toggle Mario mode for your local Toon.'
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT
    affectRange = [MagicWordConfig.AFFECT_SELF]

    def handleWord(self, invoker, avId, toon, *args):
        if toon is not base.localAvatar:
            return 'Mario mode is only available for your local Toon.'
        return toon.toggleMarioMode()


class TransformCog(MagicWord):
    aliases = ["setcogindex", "cogindex"]
    desc = "Transform the toon into a cog based on the cog shorthand."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("cogShorthand", str, False, ''), ("displayLevel", int, False, 50), ("cogType", int, False, 0)]

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg == 0:
            return ((sh, DataPackManager.getLocalizedText(base.cr.dataPackMgr.getCogAppearance(sh)[CogAppearanceIndex.NAME]) if sh else 'Toon') for sh in [''] + SuitDNA.suitHeadTypes)
        elif arg == 2:
            return ('0', 'Regular Cog (Toon Head)'), ('1', 'Regular Cog'), ('2', 'V2.0 Cog'), ('3', 'Waiter Cog (Toon Head)'), \
                   ('4', 'Waiter Cog'), ('5', 'Waiter V2.0 Cog'), ('6', 'Skelecog'), ('7', 'Virtual Skelecog'), ('8', 'Virtual Cog'), ('9', 'Rental Cog (Toon Head)'), ('10', 'Rental Cog')
        return None

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 0:
            suitName = str(entry)
            if suitName not in SuitDNA.suitHeadTypes:
                return False
            return True
        elif arg == 1:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                level = int(entry)
                return 1 <= level <= ToontownGlobals.MaxCogLevel
            return False
        elif arg == 2:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                cogType = int(entry)
                return 0 <= cogType <= 9
            return False
        return False

    def handleWord(self, invoker, avId, toon, *args):
        cogShorthand = args[0].lower()
        displayLevel = args[1]
        if displayLevel <= 0:
            displayLevel = 1
        elif displayLevel > ToontownGlobals.MaxCogLevel:
            displayLevel = ToontownGlobals.MaxCogLevel
        cogType = args[2]

        if cogShorthand and cogShorthand not in SuitDNA.suitHeadTypes:
            return f"Invalid Cog Shorthand ({cogShorthand}) specified!"

        if cogType < 0 or cogType > 10:
            return 'The cog type must be between 0 and 10!'

        toon.b_setCogIndex(cogShorthand, displayLevel, cogType, 2)
        if not cogShorthand:
            return 'Transformed {} back into a Toon!'.format(toon.getName())
        return 'Transformed {} to a Level {} {}.'.format(toon.getName(), displayLevel, cogShorthand)


class SetColor(MagicWord):
    aliases = ['tooncolor', 'dnacolor', 'color']
    desc = 'Set the color of a speciifc part of the Target'
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("part", str, True), ('r', float, True), ('g', float, True), ('b', float, True)]

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg == 0:
            return (
                ('head', "Sets the Target's head color"),
                ('torso', "Sets the Target's arm and neck colors"),
                ('legs', "Sets the Target's legs color"),
                ('body', "Sets the target's head, arms, and legs color"),
                ('shirt', "Set the Target's shirt color"),
                ('sleeves', "Set the target's sleeve color"),
                ('gloves', "Sets the target's gloves color"),
                ('bottom', "Sets the target's shorts or skirt color"),
                ('clothing', "Sets the target's shirt, sleeves, and bottoms color")
            )

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if not MagicWord.validateArg(self, arg, entry, allArgs):
            return False
        if arg != 0:
            return 0 <= float(entry) < 256
        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        part = args[0].lower()
        dna = ToonDNA.ToonDNA()
        dna.makeFromNetString(toon.getDNAString())

        r,g,b = args[1:4]
        if 1 < r < 256:
            r = r/255.
        if 1<g<256:
            g = g/255.
        if 1<b<256:
            b = b/255.
        color = (r, g, b, 1.0)
        if part == 'head':
            dna.headColor = color
        elif part == 'torso':
            dna.armColor = color
        elif part == 'legs':
            dna.legColor = color
        elif part == 'shirt':
            dna.topTexColor = color
        elif part == 'sleeves':
            dna.sleeveTexColor = color
        elif part == 'gloves':
            dna.gloveColor = color
        elif part == 'bottom':
            dna.botTexColor = color
        elif part == 'body':
            dna.headColor = color
            dna.armColor = color
            dna.legColor = color
        elif part == 'clothing':
            dna.topTexColor = color
            dna.sleeveTexColor = color
            dna.botTexColor = color
        else:
            return "Invalid part"

        toon.b_setDNAString(dna.makeNetString())
        return f"Set {toon.name}'s {part.lower()} color to ({r}, {g}, {b})"


class SetDNA(MagicWord):
    aliases = ["dna"]
    desc = "Sets a specific part of DNA for the target."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("part", str, True), ("val", str, False, 0)]

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg == 0:
            return (
                    ('gender',  None),
                    ('species', None),
                    ('head', None),
                    ('torso', None),
                    ('legs', None),
                    ('shirt', None),
                    ('sleeve', None),
                    ('pants', None)
                    )

        return None

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 0:
            return MagicWord.validateArg(self, arg, entry, allArgs)
        if arg == 1:
            part = allArgs[0].lower()
            if MagicWord.validateArg(self, 0, part):
                if part == 'species':
                    return entry in ('dog', 'cat', 'horse', 'mouse', 'rabbit', 'duck', 'monkey', 'bear', 'pig',
                                     'gyro', 'scrooge')
                elif part == 'head':
                    return entry in ('ls', 'ss', 'sl', 'll')

                elif part == 'gender':
                    return entry in ('m', 'male', 'boy', 'guy', 'f', 'female', 'girl', 'gal')
        return False

    def handleWord(self, invoker, avId, toon, *args):
        part = args[0].lower()
        value = args[1].lower()

        colorsList = ToonDNA.allColorsList
        colors2Int = ToonDNA.colorToInt

        dna = ToonDNA.ToonDNA()
        dna.makeFromNetString(toon.getDNAString())
        colors2Int = {k.lower(): v for k, v in colors2Int.items()}

        part = part.lower()

        def isValidColor(colorIndex):
            if not 0 <= colorIndex <= len(colorsList) - 1:
                return False
            return True

        colorInt = -1
        colorNames = []
        for colorName in list(colors2Int.keys()):
            colorNames.append(colorName.lower())
        if value.lower() in colorNames:
            colorInt = colors2Int[value.lower()]
        try:
            colorInt = int(value)
        except:
            pass

        if part == 'headcolor':
            value = value.title()
            if value not in list(colors2Int.keys()) and not isValidColor(colorInt):
                return "Invalid head color specified!"
            dna.headColor = colorInt
        elif part == 'armcolor':
            value = value.title()
            if value not in list(colors2Int.keys()) and not isValidColor(colorInt):
                return "Invalid arm color specified!"
            dna.armColor = colorInt
        elif part == 'legcolor':
            value = value.title()
            if value not in list(colors2Int.keys()) and not isValidColor(colorInt):
                return "Invalid leg color specified!"
            dna.legColor = colorInt
        elif part == 'color':
            value = value.title()
            if value not in list(colors2Int.keys()) and not isValidColor(colorInt):
                return "Invalid Toon color specified!"
            dna.headColor = colorInt
            dna.armColor = colorInt
            dna.legColor = colorInt
        elif part == 'gloves':
            value = value.title()
            if value not in list(colors2Int.keys()) and not isValidColor(colorInt):
                return "Invalid glove color specified!"
            dna.gloveColor = colorInt
        elif part == 'gender':
            if value.lower() in ('m', 'male', 'boy', 'guy'):
                dna.gender = 'm'
            elif value.lower() in ('f', 'female', 'girl', 'gal'):
                dna.gender = 'f'
            else:
                return "Invalid gender specified!"
        elif part == 'species':
            species = ['dog', 'cat', 'horse', 'mouse', 'rabbit', 'duck', 'monkey', 'bear', 'pig', 'gyro', 'scrooge']
            if value.lower() not in species:
                return "Invalid Toon species specified!"
            speciesDict = {species[i]: ToonDNA.toonSpeciesTypes[i] for i in range(len(species))}
            headSize = dna.head[1:3]
            if value in ['gyro', 'scrooge']:
                headSize = 'ss'
            elif value == 'mouse':
                if headSize in ['sl', 'll']:
                    headSize = 'ls'
            dna.head = (speciesDict.get(value) + headSize)
        elif part == 'head':
            sizes = ['ls', 'ss', 'sl', 'll']
            species = dna.head[0]
            try:
                value = int(value)
            except ValueError:
                return "Invalid head size specified!"
            if species in ['i', 'o']:
                return "Cannot change the head size of this Toon species! "
            elif species == 'm':
                if not 0 <= value <= 1:
                    return "Invalid head size specified!"
            else:
                if not 0 <= value <= 3:
                    return "Invalid head size specified!"
            if species == 'g':
                value = 2
            elif species == 'o':
                value = 3
            elif species == 'i':
                value = 1
            dna.head = (species + sizes[value])
        elif part == 'torso':
            try:
                value = int(value)
            except ValueError:
                return "Invalid torso size specified!"
            if dna.gender == 'm':
                if not 0 <= value <= 2:
                    return "Invalid torso size specified!"
            elif dna.gender == 'f':
                if not 3 <= value <= 8:
                    return "Invalid torso size specified!"
                if 6 <= value <= 8:
                    value = value - 6
            dna.torso = ToonDNA.toonTorsoTypes[value]
        elif part == 'legs':
            try:
                value = int(value)
            except ValueError:
                return "Invalid legs size specified!"
            if not 0 <= value <= 2:
                return "Invalid legs size specified!"
            dna.legs = ToonDNA.toonLegTypes[value]
        elif part == 'shirt':
            try:
                value = int(value)
            except ValueError:
                return "Invalid shirt ID specified!"
            if not 0 <= value <= len(ToonDNA.Shirts):
                return "Invalid shirt ID specified! Please specify an ID between 0 and {}.".format(len(ToonDNA.Shirts))
            dna.topTex = value
        elif part == 'shirtcolor':
            try:
                value = int(value)
            except ValueError:
                return "Invalid shirt color ID specified!"
            if not 0 <= value <= len(ToonDNA.ClothesColors):
                return "Invalid shirt color ID specified! Please specify an ID between 0 and {}.".format(
                    len(ToonDNA.ClothesColors))
            dna.topTexColor = value
        elif part == 'sleeve':
            try:
                value = int(value)
            except ValueError:
                return "Invalid sleeve ID specified!"
            if not 0 <= value <= len(ToonDNA.Sleeves):
                return "Invalid sleeve ID specified! Please specify an ID between 0 and {}.".format(
                    len(ToonDNA.Sleeves))
            dna.sleeveTex = value
        elif part == 'sleevecolor':
            try:
                value = int(value)
            except ValueError:
                return "Invalid sleeve color ID specified"
            if not 0 <= value <= len(ToonDNA.ClothesColors):
                return "Invalid sleeve color ID specified! Please specify an ID between 0 and {}.".format(
                    len(ToonDNA.ClothesColors))
            dna.sleeveTexColor = value
        elif part == 'pants':
            try:
                value = int(value)
            except ValueError:
                return "Invalid pants ID specified!"
            if dna.gender == 'm':
                bottoms = ToonDNA.BoyShorts
            else:
                bottoms = ToonDNA.GirlBottoms
            if not 0 <= value <= len(bottoms):
                return "Invalid pants ID specified! Please specify an ID between 0 and {}.".format(len(bottoms))
            dna.botTex = value
        elif part == 'pantscolor':
            try:
                value = int(value)
            except ValueError:
                return "Invalid pants color ID specified!"
            if not 0 <= value <= len(ToonDNA.ClothesColors):
                return "Invalid pants color ID specified! Please specify an ID between 0 and {}.".format(
                    len(ToonDNA.ClothesColors))
            dna.botTexColor = value
        else:
            return "Invalid Toon part specified!"

        toon.b_setDNAString(dna.makeNetString())
        return "Successfully changed {}'s Toon DNA!".format(toon.getName())


class GrowFlowers(MagicWord):
    desc = "Grows a target's flowers."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER

    def handleWord(self, invoker, avId, toon, *args):
        estate = self.air.estateMgr.estate.get(toon.doId)

        if not estate:
            return "Estate not found!"

        flowers = estate.getFlowers(toon.doId)
        for flower in flowers:
            flower.b_setWaterLevel(5)
            flower.b_setGrowthLevel(2)

        return "{0} flowers grown for {1}.".format(len(flowers), toon.getName())


class PickAllFlowers(MagicWord):
    aliases = ["pickflowers"]
    desc = "Picks all of the target's flowers."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER

    def handleWord(self, invoker, avId, toon, *args):
        estate = self.air.estateMgr.estate.get(toon.doId)

        if not estate:
            return "Estate not found!"

        flowers = estate.getFlowers(toon.doId)

        for flower in flowers:
            if flower.isFruiting():
                flower.forceRemoveItem(toon.doId)

        return "{0} flowers picked for {1}.".format(len(flowers), toon.getName())


class GrowTrees(MagicWord):
    desc = "Grows the target's trees."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("track", str, False, 'all'), ("level", int, False, -1), ("amount", int, False, 21)]

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 0:
            track = str(entry)
            return track in ['all', 'toonup', 'trap', 'lure', 'sound', 'throw', 'squirt', 'drop', 'fire']
        elif arg == 1:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                level = int(entry)
                if level == 9:
                    return True
                return -1 <= level <= 6
            return False
        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        track = args[0]
        level = args[1]
        grown = args[2]

        estate = self.air.estateMgr.estate.get(toon.doId)

        if not estate:
            return "Estate not found!"

        try:
            trackIndex = {'all': -1, 'toonup': 0, 'trap': 1, 'lure': 2, 'sound': 3,
                          'throw': 4, 'squirt': 5, 'drop': 6, 'fire': 9
                          }[track]
        except KeyError:
            # Backwards compatibility
            try:
                trackIndex = int(track)
            except ValueError:
                return 'Gag track is invalid. Please specify a value between -1 and 6 or 9.'

        if trackIndex < -1 and trackIndex > 6 and not trackIndex == 9:
            return 'Gag track is invalid. Please specify a value between -1 and 6 or 9.'

        trees = estate.getTrees(toon.doId, trackIndex, level)
        if not trees:
            return "No trees found!"

        for tree in trees:
            growthLevel = tree.getGrowthLevel()
            growthLevel += grown
            tree.b_setGrowthLevel(growthLevel)

        return f'{len(trees)} {"tree" if len(trees) == 1 else "trees"} {"grown" if grown > -1 else "de-grown"} for {toon.getName()}.'


class PickTrees(MagicWord):
    desc = "Picks the target's trees."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("track", str, False, 'all'), ("level", int, False, -1)]

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 0:
            track = str(entry)
            return track in ['all', 'toonup', 'trap', 'lure', 'sound', 'throw', 'squirt', 'drop', 'fire']
        elif arg == 1:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                level = int(entry)
                if level == 9:
                    return True
                return -1 <= level <= 6
            return False
        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        track = args[0]
        level = args[1]
        estate = self.air.estateMgr.estate.get(toon.doId)

        if not estate:
            return "Estate not found!"

        try:
            trackIndex = {'all': -1, 'toonup': 0, 'trap': 1, 'lure': 2, 'sound': 3,
                          'throw': 4, 'squirt': 5, 'drop': 6, 'fire': 9
                          }[track]
        except KeyError:
            # Backwards compatibility
            try:
                trackIndex = int(track)
            except ValueError:
                return 'Gag track is invalid. Please specify a value between -1 and 6 or 9.'

        if trackIndex < -1 and trackIndex > 6 and not trackIndex == 9:
            return 'Gag track is invalid. Please specify a value between -1 and 6 or 9.'

        trees = estate.getTrees(toon.doId, trackIndex, level)
        if not trees:
            return "Trees not found!"

        pickedTrees = 0
        for tree in trees:
            if tree.doActualHarvest(toon):
                pickedTrees += 1

        return f"{pickedTrees} {'tree' if pickedTrees == 1 else 'trees'} picked for {toon.getName()}."

# TODO: validation: validate varierty based on previous species argument
class PlantFlowers(MagicWord):
    aliases = ["flowerall"]
    desc = "Plants the target's flowers."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("species", int, False, 49), ("variety", int, False, 0)]

    def handleWord(self, invoker, avId, toon, *args):
        species = args[0]
        variety = args[1]

        estate = self.air.estateMgr.estate.get(toon.doId)

        if not estate:
            return "Estate not found!"

        plots = estate.getPlots(toon.doId, True)
        if not plots:
            return "No unoccupied flower plots found!"

        flowerSpecies = GardenGlobals.getFlowerSpecies()
        flowerVarieties = GardenGlobals.getFlowerVarieties(species)

        if species not in flowerSpecies:
            return 'Invalid flower species %d!' % species

        if variety not in flowerVarieties:
            return 'Invalid flower variety %d!' % variety

        for plot in plots:
            estate.removeGardenPlot(plot.ownerIndex, plot.plot)
            estate.plantFlower(avId = avId,
                               type = species,
                               plot = plot.plot,
                               water = 0,
                               growth = 0,
                               optional = variety,
                               box = plot.box)

        return f"{len(plots)} {'flower' if len(plots) == 1 else 'flowers'} planted for {toon.getName()}"


class RestockFlowerSpecials(MagicWord):
    aliases = ["specials", "gibspecials", "specialsall"]
    desc = "Restocks special flowers for the target."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER

    def handleWord(self, invoker, avId, toon, *args):
        toon.gardenSpecials = []
        for x in (100, 101, 102, 103, 105, 106, 107, 108, 109, 130, 131, 135):
            toon.addGardenItem(x, 99)
        return "Special flowers restocked for {}.".format(toon.getName())


class MaxDoodle(MagicWord):
    desc = "Maxes the target's doodle."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER

    def handleWord(self, invoker, avId, toon, *args):
        petId = toon.getPetId()
        pet = simbase.air.doId2do.get(petId)
        if not pet:
            return "{}'s pet is unavailable. They must be in the same area as their pet to use this Magic Word.".format(
                toon.getName())

        pet.b_setTrickAptitudes([1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0])
        return "Maxed out {}'s doodle.".format(toon.getName())


class LeaveRace(MagicWord):
    aliases = ["exitrace"]
    desc = "Leave the current race you are in."
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT

    def handleWord(self, invoker, avId, toon, *args):
        messenger.send('leaveRace')
        return "You have left the race! 'you done!!'"


class HitBoss(MagicWord):
    desc = "Hits a Boss Cog for the specified damage amount."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("damage", int, False, 1)]
    affectRange = [MagicWordConfig.AFFECT_SELF]

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 0:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                dmg = int(entry)
                return dmg >= 1
            return False
        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        dmg = args[0]

        boss = toon.findBoss()
        if not boss:
            return "You aren't in a boss battle!"

        if dmg < 1:
            boss = toon.findBoss('ss')
            if not boss:
                return "Boss damage must be at least 1."

        if boss.hardcore:
            return "You cannot cheat in this Boss Battle!"

        boss.magicWordHit(dmg, invoker.doId)
        return "Hit boss for {} damage.".format(dmg)


class ToggleBoss(MagicWord):
    aliases = ["pauseboss"]
    desc = "Pauses a Cog Boss's attack cycle."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    affectRange = [MagicWordConfig.AFFECT_SELF]

    def handleWord(self, invoker, avId, toon, *args):
        boss = toon.findBoss()
        if not boss:
            return "You aren't in a boss battle!"

        if boss.hardcore:
            return "You cannot cheat in this Boss Battle!"

        boss.setPaused(not boss.paused)
        return "Toggled the Cog Boss's attack cycle."


class DisableGoons(MagicWord):
    desc = "Disables all of the goons in an area."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    affectRange = [MagicWordConfig.AFFECT_SELF]

    def handleWord(self, invoker, avId, toon, *args):
        boss = toon.findBoss()
        if boss and boss.hardcore:
            return "You cannot cheat in this Boss Battle!"

        count = 0
        from toontown.suit.DistributedGoonAI import DistributedGoonAI
        for goon in simbase.air.doFindAllInstances(DistributedGoonAI):
            goon.requestStunned(0)
            count += 1

        return "Disabled {} Goons in this area!".format(count)


class ResetCFOObjects(MagicWord):
    desc = "Resets the state of cranes and safes in the crane round of the C.F.O. Boss Battle."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    affectRange = [MagicWordConfig.AFFECT_SELF]

    def handleWord(self, invoker, avId, toon, *args):
        boss = toon.findBoss('m')
        if not boss:
            return "You aren't in a CFO!"

        if boss.hardcore:
            return "You cannot cheat in this Boss Battle!"

        if boss.state == 'BattleThree':
            boss.magicWordReset()
            return "Cranes and safes have been reset!"

        return 'You must be in the crane round!'


class DestroyCFOGoons(MagicWord):
    aliases = ["destroygoons"]
    desc = "Destroys all of the goons in the Crane Round of the C.F.O. Boss Battle."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    affectRange = [MagicWordConfig.AFFECT_SELF]

    def handleWord(self, invoker, avId, toon, *args):
        boss = toon.findBoss('m')
        if not boss:
            return "You aren't in a CFO!"

        if boss.hardcore:
            return "You cannot cheat in this Boss Battle!"

        if boss.state == 'BattleThree':
            boss.magicWordResetGoons()
            return "Destroyed all Goons!"

        return 'You must be in the crane round!'


class FillJury(MagicWord):
    desc = "Fills all of the chairs in the Jury Round of the C.J. Boss Battle."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    affectRange = [MagicWordConfig.AFFECT_SELF]

    def handleWord(self, invoker, avId, toon, *args):
        boss = toon.findBoss('l')
        if not boss:
            return "You are not currently fighting the C.J.!"

        if boss.hardcore:
            return "You cannot cheat in this Boss Battle!"

        if not boss.state == 'BattleTwo':
            return "You are not currently in the Jury Round of the C.J.!"

        for i in range(len(boss.chairs)):
            boss.chairs[i].b_setToonJurorIndex(0)
            boss.chairs[i].requestToonJuror()
        return "Filled all of the chairs in the Lawbot Jury successfully!"


class ToggleScale(MagicWord):
    desc = "Toggles the functionality of the scale in the C.J. Boss Battle."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    affectRange = [MagicWordConfig.AFFECT_SELF]

    def handleWord(self, invoker, avId, toon, *args):
        boss = toon.findBoss('l')
        if not boss:
            return "You are not currently fighting the C.J.!"

        if boss.hardcore:
            return "You cannot cheat in this Boss Battle!"

        if not boss.state == 'BattleThree':
            return "You are not currently in the Scale Round of the C.J.!"

        boss.scalePaused = not boss.scalePaused
        return "Toggled the scale successfully!"


class SkipCourtroomCatastrophe(MagicWord):
    aliases = ["skipcc", "skipcourtroom"]
    desc = "Skips the introduction cutscene of the Courtroom Catastrophe Mini-Game."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    affectRange = [MagicWordConfig.AFFECT_SELF]

    def handleWord(self, invoker, avId, toon, *args):
        boss = toon.findBoss('cc')
        if not boss:
            return "You aren't in a Courtroom Catastrophe!"

        if boss.state == 'Elevator':
            return "Please wait until the following cutscene begins to skip."
        elif boss.state != 'Introduction':
            return "You are not currently in the introduction cutscene!"

        boss.b_setState('BattleOne')
        return "Skipped the Courtroom Catastrophe introduction cutscene."

class SkipBoss(MagicWord):
    aliases = ['skipvp', 'skipcfo', 'skipcj', 'skipceo']
    desc = "Skips to the indicated round of the current Boss Battle."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("round", str, False, "next")]
    accessLevel = "MODERATOR"
    affectRange = [MagicWordConfig.AFFECT_SELF]

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg == 0:
            return ('Next',  'Default'), ('Final', None), ('Two', 'Only works if a second round exists.'), ('Three', 'Only works if a third round exists.'), ('Four', 'Only works if a fourth round exists.')

        return None

    def handleWord(self, invoker, avId, toon, *args):
        battle = args[0].lower()

        boss = toon.findBoss()
        if not boss:
            return "You are not currently fighting a boss."
        dept = boss.dept

        if toon.findBoss('cc'):
            return "This command cannot skip Courtroom Castastrophe. Please use the SkipCourtroomCatastrophe command!"

        if boss.state in ('Elevator', 'Introduction'):
            return "You cannot skip the introduction cutscene!"

        # TODO: this could probably be refactored, it was copied from the now removed skip commands, and just merged into this large code block
        if dept in ['s', 'l']:
            if battle == 'two':
                if boss.state in ('RollToBattleTwo', 'PrepareBattleTwo', 'BattleTwo', 'PrepareBattleThree', 'BattleThree'):
                    return "You can not return to previous rounds!"
                else:
                    boss.exitIntroduction()
                    boss.b_setState('RollToBattleTwo')
                    return "Skipping to the second round..."
            if battle in ['final', 'three']:
                if boss.state in ('PrepareBattleThree', 'BattleThree'):
                    return "You can not return to previous rounds!"
                else:
                    boss.exitIntroduction()
                    boss.b_setState('PrepareBattleThree')
                    return "Skipping to the final round..."
            if battle == 'next':
                if boss.state in ('PrepareBattleOne', 'BattleOne'):
                    boss.exitIntroduction()
                    boss.b_setState('RollToBattleTwo')
                    return "Skipping the current round..."
                elif boss.state in ('RollToBattleTwo', 'PrepareBattleTwo', 'BattleTwo'):
                    boss.exitIntroduction()
                    boss.b_setState('PrepareBattleThree')
                    return "Skipping the current round..."
                elif boss.state in ('PrepareBattleThree', 'BattleThree'):
                    boss.exitIntroduction()
                    boss.enterNearVictory()
                    boss.b_setState('Victory')
                    return "Skipping the final round..."
        elif dept == 'm':
            if battle in ['final', 'two']:
                if boss.state in ('PrepareBattleThree', 'BattleThree'):
                    return "You can not return to previous rounds!"
                else:
                    boss.exitIntroduction()
                    boss.b_setState('PrepareBattleThree')
                    return "Skipping to the last round..."
            if battle == 'next':
                if boss.state in ('PrepareBattleOne', 'BattleOne'):
                    boss.exitIntroduction()
                    boss.b_setState('PrepareBattleThree')
                    return "Skipping the current round..."
                elif boss.state in ('PrepareBattleThree', 'BattleThree'):
                    boss.exitIntroduction()
                    boss.b_setState('Victory')
                    return "Skipping the final round..."
        elif dept == 'c':
            if battle == 'two':
                if boss.state in (
                'PrepareBattleFour', 'BattleFour', 'PrepareBattleThree', 'BattleThree', 'PrepareBattleTwo', 'BattleTwo'):
                    return "You can not return to previous rounds!"
                else:
                    boss.exitIntroduction()
                    boss.b_setState('PrepareBattleTwo')
                    return "Skipping to the second round..."
            if battle == 'three':
                if boss.state in ('PrepareBattleFour', 'BattleFour', 'PrepareBattleThree', 'BattleThree'):
                    return "You can not return to previous rounds!"
                else:
                    boss.exitIntroduction()
                    boss.b_setState('PrepareBattleThree')
                    return "Skipping to the third round..."
            if battle in ['final', 'four']:
                if boss.state in ('PrepareBattleFour', 'BattleFour'):
                    return "You can not return to previous rounds!"
                else:
                    boss.exitIntroduction()
                    boss.b_setState('PrepareBattleFour')
                    return "Skipping to the last round..."
            if battle == 'next':
                if boss.state in ('PrepareBattleOne', 'BattleOne'):
                    boss.exitIntroduction()
                    boss.b_setState('PrepareBattleTwo')
                    return "Skipping the current round..."
                elif boss.state in ('PrepareBattleTwo', 'BattleTwo'):
                    boss.exitIntroduction()
                    boss.b_setState('PrepareBattleThree')
                    return "Skipping the current round..."
                elif boss.state in ('PrepareBattleThree', 'BattleThree'):
                    boss.exitIntroduction()
                    boss.b_setState('PrepareBattleFour')
                    return "Skipping the current round..."
                elif boss.state in ('PrepareBattleFour', 'BattleFour'):
                    boss.exitIntroduction()
                    boss.b_setState('Victory')
                    return "Skipping the final round..."

        return "Invalid round provided. The boss may not support this round."

class StunVP(MagicWord):
    desc = "Stuns the Boss Cog during the pie round of the V.P. Boss Battle."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    affectRange = [MagicWordConfig.AFFECT_SELF]

    def handleWord(self, invoker, avId, toon, *args):
        boss = toon.findBoss('s')
        if not boss:
            return "You are not currently fighting the V.P.!"

        if boss.hardcore:
            return "You cannot cheat in this Boss Battle!"

        currState = boss.getCurrentOrNextState()
        if currState != 'BattleThree':
            return "You are not in the final round of the V.P.!"

        boss.b_setAttackCode(ToontownGlobals.BossCogDizzyNow)
        boss.b_setBossDamage(boss.getBossDamage(), 0, 0)
        return 'Stunned the V.P. successfully!'


class SkipSellbotShowdown(MagicWord):
    aliases = ["skipss"]
    hidden = True
    desc = "Skips the introduction cutscene of the Sellbot Showdown Mini-Game."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    affectRange = [MagicWordConfig.AFFECT_SELF]

    def handleWord(self, invoker, avId, toon, *args):
        boss = toon.findBoss('ss')
        if not boss:
            return "You aren't in a Sellbot Showdown!"

        if boss.state == 'Elevator':
            return "Please wait until the following cutscene begins to skip."
        elif boss.state != 'Introduction':
            return "You are not currently in the introduction cutscene!"

        boss.b_setState('BattleOne')
        return "Skipped the Sellbot Showdown introduction cutscene."

class FeedDiners(MagicWord):
    desc = "Feeds all of the diners in the Banquet Round of the C.E.O. Boss Battle."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER

    def handleWord(self, invoker, avId, toon, *args):
        boss = toon.findBoss('c')
        if not boss:
            return "You aren't in a CEO!"

        if boss.hardcore:
            return "You cannot cheat in this Boss Battle!"

        if boss.state != 'BattleTwo':
            return "You aren't in the banquet round!"

        for table in boss.tables:
            for chairIndex in list(table.dinerInfo.keys()):
                dinerStatus = table.getDinerStatus(chairIndex)
                if dinerStatus in (table.HUNGRY, table.ANGRY):
                    table.foodServed(chairIndex)

        return "All diners have been fed!"


class AbortGame(MagicWord):
    aliases = ["abortminigame", "leaveminigame", "cancelminigame"]
    desc = "Abort any minigame you are currently in."
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT

    def handleWord(self, invoker, avId, toon, *args):
        messenger.send('minigameAbort')
        return 'Aborting the minigame.'


class RequestGame(MagicWord):
    aliases = ["reqgame", "requestminigame", "reqminigame", "nextgame", "nexttrolleygame"]
    desc = "Requests a trolley minigame."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("name", str, False, "remove"), ("zoneId", int, False, 0),
                 ("keep", bool, False, False), ("difficulty", int, False, 0)]
    affectRange = [MagicWordConfig.AFFECT_SELF]

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg == 0:
            return (
                ('racing', 'Race Game'),
                ('racingbeta', 'Race Game (Beta Version)'),
                ('cannon', 'Cannon Game'),
                ('toontag', 'Toon Tag'),
                ('match', 'Match Minnie'),
                ('matchbeta', 'Match Minnie (Beta Version)'),
                ('ring', 'Ring Game'),
                ('maze', 'Maze Game'),
                ('tugofwar', 'Tug-O-War'),
                ('catch', 'Catching Game'),
                ('diving', 'Treasure Dive'),
                ('toonslingshot', 'Toon Slingshot'),
                ('memory', 'Toon Memory Game'),
                ('vine', 'Jungle Vines'),
                ('ice', 'Ice Slide'),
                ('cogthief', 'Cog Thief'),
                ('escape', 'Toon Escape'),
                ('photofun', 'Photo Fun'),
                ('travel', 'Trolley Tracks')
            )

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 0:
            return entry in ToontownGlobals.MinigameNames
        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        name = args[0]
        zone = args[1]
        keep = args[2]
        difficulty = args[3]

        if zone == 0:
            zone = invoker.zoneId
            if zone not in MinigameGlobals.SafeZones:
                zone = 0
        elif zone not in MinigameGlobals.SafeZones:
            zone = ToontownGlobals.ToontownCentral
        else:
            return "Invalid minigame Zone ID specified!"

        from toontown.minigame import MinigameCreatorAI
        if name == 'remove':
            if invoker.doId in MinigameCreatorAI.RequestMinigame:
                del MinigameCreatorAI.RequestMinigame[invoker.doId]
                return "Removed the current minigame request."
            else:
                return "You don't have any active minigame requests!"
        elif name not in ToontownGlobals.MinigameNames:
            return "Invalid minigame name specified!"
        else:
            MinigameCreatorAI.RequestMinigame[invoker.doId] = ToontownGlobals.MinigameNames[name], keep, difficulty, \
                                                              zone
            return "Your next trolley game will be the {} game!".format(name)


class SpawnCog(MagicWord):
    aliases = ["cog"]
    desc = "Spawns a cog with the specified level."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("cogShorthand", str, False, "f"), ("level", int, False, 1), ("special", int, False, 0),
                 ("virtual", bool, False, False)]

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg == 0:
            return ((sh, DataPackManager.getLocalizedText(base.cr.dataPackMgr.getCogAppearance(sh)[CogAppearanceIndex.NAME])) for sh in SuitDNA.suitHeadTypes)
        elif arg == 2:
            return ('0', 'none'), ('1', 'skelecog'), ('2', 'v2.0')
        elif arg == 3:
            return ('0', 'False'), ('1', 'True')
        else:
            return None

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 0:
            suitName = str(entry)
            if suitName not in SuitDNA.suitHeadTypes:
                return False
            return True
        elif arg == 1:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                level = int(entry)
                return 1 <= level <= ToontownGlobals.MaxCogLevel
            return False
        elif arg == 2:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                special = int(entry)
                return 0 <= special <= 2
            return False 
        elif arg == 3:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                virtual = int(entry)
                return 0 <= virtual <= 1
            return False 
        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        cogShorthand = args[0].lower()
        level = args[1]
        special = args[2]
        virtual = args[3]

        if not 0 <= special <= 2:
            return f"Can't toggle special flag to {special}! Specify a value between 0 and 2."

        if not 0 <= virtual <= 1:
            return f"Can't toggle virtual flag to {virtual}! Specify a value between 0 and 1."

        if cogShorthand not in SuitDNA.suitHeadTypes:
            return f"Invalid Cog Shorthand ({cogShorthand}) specified!"

        maxCogLevel = ToontownGlobals.MaxCogLevel

        if level < 1 or level > maxCogLevel:
            return f"Invalid Cog level specified. Specify a value between 1 and {maxCogLevel}."

        if special == 1 and virtual:
            prefix = TTLocalizer.Virtual + TTLocalizer.Skeleton + cogShorthand
        elif special == 2 and virtual:
            prefix = TTLocalizer.Virtual + TTLocalizer.SkeleRevive + cogShorthand
        elif special == 1:
            prefix = TTLocalizer.Skeleton + cogShorthand
        elif special == 2:
            prefix = TTLocalizer.SkeleRevive + cogShorthand
        elif virtual:
            prefix = TTLocalizer.Virtual + cogShorthand
        else:
            prefix = cogShorthand

        zoneId = invoker.getLocation()[1]
        sp = simbase.air.suitPlanners.get(zoneId - (zoneId % 100))
        if not sp:
            return f"Unable to spawn a {prefix} in current zone."

        pointMap = sp.getZoneIdToPointMap()
        zones = [zoneId, zoneId - 1, zoneId + 1]
        for zoneId in zones:
            if zoneId in pointMap:
                points = pointMap[zoneId][:]
                suit = sp.createNewSuit([], points, suitName = cogShorthand, suitLevel = level, special = special,
                                        virtual = virtual)
                if suit:
                    return f"Spawned {prefix} in the current zone."
        return f"Failed to spawn {prefix} in the current zone."


# We separate this from the invasion command because of the cooldown in the invasion command.
class InvasionWho(MagicWord):
    aliases = ["invwho"]
    desc = "Names the Toon who summoned an invasion that may be currently active."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    affectRange = [MagicWordConfig.AFFECT_SELF]

    def handleWord(self, invoker, avId, toon, *args):
        invasionManager = simbase.air.suitInvasionManager

        if not invasionManager.getInvading():
            return "The Cogs are not currently invading."
        summonerId = invasionManager.getSummonerId()
        if summonerId:
            if invoker.getAccessLevel() >= OTPGlobals.AccessLevelName2Int.get('MODERATOR'):
                nameStr = '{0}({1})'.format(invasionManager.getSummonerName(), invasionManager.getSummonerId())
            else:
                nameStr = '{}'.format(invasionManager.getSummonerName())
            return '{} is the creator of this invasion.'.format(nameStr)
        return "This is a naturally spawned invasion."


class SpawnInvasion(MagicWord):
    aliases = ["invasion", "cinv", "coginv", "coginvasion"]
    desc = "Spawns a Cog Invasion with the specified values. You can separate Cog shorthands through commas in order " \
           "to have multiple Cogs invade."
    cooldown = 10.0
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("start/stop", str, True), ("cogShorthand(s)", str, False, "f"), ("special", int, False, 0),
                 ("virtual", int, False, 0), ("amount", int, False, 3000)]
    affectRange = [MagicWordConfig.AFFECT_SELF]

    NORMAL = 0
    SKELECOG = 1
    REVIVE = 2

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg == 0:
            return ('start', None), ('stop', None)
        elif arg == 1:
            return ((sh, DataPackManager.getLocalizedText(base.cr.dataPackMgr.getCogAppearance(sh)[CogAppearanceIndex.NAME])) for sh in SuitDNA.suitHeadTypes)
        elif arg == 2:
            return ('0', 'none'), ('1', 'skelecog'), ('2', 'v2.0')
        elif arg == 3:
            return ('0', 'False'), ('1', 'True')
        elif arg == 4:
            return ((str(i), None) for i in SuggestedInvasionAmounts)
        else:
            return None

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 1:
            allEntries = entry.split(',')
            for x in allEntries:
                if x not in SuitDNA.suitHeadTypes:
                    return False
            return True
        elif arg == 2:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                special = int(entry)
                return 0 <= special <= 2
            return False 
        elif arg == 3:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                virtual = int(entry)
                return 0 <= virtual <= 1
            return False 
        elif arg == 4:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                amount = int(entry)
                return 1000 <= amount <= 25000
            return False

        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        cogsList = []
        invalidCogs = []
        names = []
        cogFlag = 0
        departmentFlag = 0

        invasionManager = simbase.air.suitInvasionManager

        start = args[0]
        if start in ('off', 'stop', 'finish', 'end', 'bye', 'adios', 'cya', 'begone', 'no', 'n'):
            if not invasionManager.getInvading():
                return "The Cogs are not currently invading."
            elif invasionManager.mega:
                return "You cannot stop a Mega-Invasion with this Magic Word."
            invasionManager.stopInvasion()
            return "Ending a Cog Invasion!"

        if start not in ('on', 'start', 'begin', 'yes', 'y'):
            return "Invalid start/stop argument."

        cogs = args[1].split(",")
        for cog in cogs:
            cog = cog.lower()
            department = cog.capitalize()

            if cog in SuitDNA.suitHeadTypes:
                if departmentFlag:
                    return "You can't mix departments and Cogs in a Cog Invasion!"
                if cog in names:
                    continue
                names.append(cog)
                cogsList.append(cog)
                cogFlag = 1
            elif department in ToontownGlobals.Dept2Dept.values():
                if cogFlag:
                    return "You can't mix departments and Cogs in a Cog Invasion!"
                name = department
                if name in names:
                    continue
                names.append(name)
                cogsList.append(cog)
                departmentFlag = 1
            else:
                invalidCogs.append(cog)

        special = args[2]
        if not 0 <= special <= 2:
            return f"Can't start a Cog Invasion with a special flag of {special}! Specify a value between 0 and 2."

        virtual = args[3]
        if not 0 <= virtual <= 1:
            return f"Can't start a Cog Invasion with a virtual flag of {virtual}! Specify a value between 0 and 1."

        amount = args[4]
        if not 1000 <= amount <= 25000:
            return f"Can't start a Cog Invasion with {amount} Cogs! Specify a value between 1,000 and 25,000."

        # None of our specified Cogs are valid.
        if not cogsList:
            return f"No valid Cog shorthands have been specified. Invalid Cogs: {invalidCogs}"

        # If we're currently invading, stop the invasion before starting a new one
        if invasionManager.getInvading():
            invasionManager.stopInvasion()

        if invasionManager.startInvasion(cogsList, amount, special, virtual, summonerId = invoker.getDoId()):
            if len(cogsList) > 1:
                nameStr = 'Names'
            else:
                nameStr = 'Name'
            namesListStr = ", ".join(names)
            return f"Began a Cog Invasion! {nameStr}: {namesListStr} Amount: {amount}"
        else:
            return "Failed to start a Cog Invasion..."


class SetTrophyScore(MagicWord):
    aliases = ["trophyscore"]
    desc = "Sets the trophy score of the target."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("val", int, True)]

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg == 0:
            return ('0', 'No Star'), ('10', 'Bronze Star'), ('20', 'Spinning Bronze Star'), ('30', 'Silver Star'), \
                   ('50', 'Spinning Silver Star'), ('75', 'Gold Star'), ('100', 'Spinning Gold Star'), \
                   ('150', 'Diamond Star'), ('200', 'Spinning Diamond Star')

        return None

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 0:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                amt = int(entry)
                return 0 <= amt <= 255
            return False
        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        amt = args[0]

        if not 0 <= amt <= 255:
            return "The amount must be between 0 and 255!"

        simbase.air.trophyMgr.addTrophy(toon.doId, toon.name, amt, True)
        return f"{toon.getName()}'s trophy score is now {amt}."


class SetActionProp(MagicWord):
    aliases = ['actionprop', "setpies", "pies", "givepies", "getpies", "throwableprop", "throwable", "throwables",
               "setthrowableprop"]
    desc = "Sets the target's current action prop, used by the 'Action' Hotkey."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("type", int, True), ("amount", int, False, -1)]

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg == 0:
            return ValidActionProps
        elif arg == 1:
            return SuggestedActionPropAmounts

        return None

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 0:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                propType = int(entry)
                return -1 <= propType <= 9
            return False
        elif arg == 1:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                propAmount = int(entry)
                return -1 <= propAmount <= 99
            return False
        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        propType = args[0]
        numProps = args[1]

        microGameMgr = self.air.microGameMgr
        if microGameMgr:
            microGame, active = microGameMgr.getActiveMicroGame(toon.zoneId)
            if active and microGame.getName() == 'Pie Blitz':
                return "A Pie Blitz is currently active! Cannot set action prop during a Pie Blitz."

        boss = toon.findBoss()
        if boss and boss.hardcore:
            return "You cannot cheat in this Boss Battle!"

        if propType == -1:
            toon.b_setNumPies(0)
            return f"Removed {toon.getName()}'s action prop."

        if not 0 <= propType <= 10:
            return "You can only specify between action prop types 0 and 10."

        if numProps == -1:
            toon.b_setPieType(propType)
            toon.b_setNumPies(ToontownGlobals.FullPies)
            return f"Gave {toon.getName()} an infinite amount of action prop type {propType}."

        if not 0 <= numProps <= 99:
            return "You can only specify between 0 and 99 of your chosen action prop."

        toon.b_setPieType(propType)
        toon.b_setNumPies(numProps)
        return f"Gave {toon.getName()} {numProps} of action prop type {propType}."


class SetToonTaskProgress(MagicWord):
    aliases = ["setquestprogress", "setqp", "qp", "questprogress", "ttp", "toontaskprogress"]
    desc = "Set the target's ToonTask progress."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("id", int, False, 0), ("progress", int, False, 0)]

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg == 0:
            return ((str(i), QuestIndexTitles[i]) for i in range(len(base.localAvatar.quests)))
        else:
            return None

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 0:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                index = int(entry)
                return 0 <= index <= len(base.localAvatar.quests) - 1
            return False 
        elif arg == 1:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                progress = int(entry)
                return 0 <= progress <= 10000
            return False 

        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        index = args[0]
        progress = args[1]
        if not 0 <= index <= len(toon.quests) - 1:
            return "Invalid ToonTask index."
        if progress < 0:
            progress = 0
        # 10000 sounds like a good amount for max progress, especially for moddable quests as well
        # if not, can always bump it up
        if progress > 10000:
            progress = 10000
        toon.quests[index][4] = progress
        toon.b_setQuests(toon.quests)
        return f"Set {QuestIndexTitles[index]} progress to {progress}."


class SetUnites(MagicWord):
    aliases = ["unites", "restockunites", "unitephrases"]
    desc = "Restocks the target's unites. The default amount is 999."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("amount", int, False, 999)]

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg == 0:
            return ('0', 'None'), ('100', None), ('200', None), ('300', None), ('400', None), ('500', None), ('600', None), ('700', None), ('800', None), ('900', None), ('999', 'Maximum')
        return None

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 0:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                amt = int(entry)
                return 0 <= amt <= 999
            return False
        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        boss = toon.findBoss()
        if boss and boss.hardcore:
            return "You cannot cheat in this Boss Battle!"
        amt = args[0]
        if not 0 <= amt <= 999:
            return "Invalid amount specified. Unite amount must be between 0 and 999!"
        toon.restockAllResistanceMessages(amt)
        return "Successfully gave {} unites.".format(amt)


class UnlockTricks(MagicWord):
    aliases = ["tricks"]
    desc = "Unlock all the target's pet trick phrases."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER

    def handleWord(self, invoker, avId, toon, *args):
        toon.b_setPetTrickPhrases(list(range(7)))
        return "Unlocked all pet tricks for {}!".format(toon.getName())


class RestockSummons(MagicWord):
    desc = "Restock all of the target's CJ summons."
    aliases = ["summons"]
    execLocation = MagicWordConfig.EXEC_LOC_SERVER

    def handleWord(self, invoker, avId, toon, *args):
        # Make sure we have every cog in our Cog Page.
        cogCount = []
        for deptIndex in range(4):
            for cogIndex in range(8):
                cogCount.append(CogPageGlobals.COG_QUOTAS[1][cogIndex])
        toon.b_setCogCount(cogCount)
        toon.b_setCogStatus(([CogPageGlobals.COG_COMPLETE2] * 8) * 4)
        toon.restockAllCogSummons()
        return "Restocked all cog summons successfully!"


class SetPinkSlips(MagicWord):
    aliases = ["pinkslips", "setfires", "fires"]
    desc = "Sets the target's pink slips. The default amount is 255."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("amount", int, False, 255)]

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg == 0:
            return ('0', 'None'), ('10', None), ('25', None), ('50', None), ('75', None), ('100', None), ('125', None), ('150', None), ('175', None), ('200', None), ('225', None), ('255', 'Maximum')
        return None

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 0:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                amt = int(entry)
                return 0 <= amt <= 255
            return False
        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        boss = toon.findBoss()
        if boss and boss.hardcore:
            return "You cannot cheat in this Boss Battle!"

        amt = args[0]
        plural = 's'
        if not 0 <= amt <= 255:
            return "Invalid amount specified.The amount must be between 0 and 255!"
        if amt == 1:
            plural = ''
        toon.b_setPinkSlips(amt)
        return "Set {0} pink slip{1} successfully!".format(amt, plural)


class SetQuestTier(MagicWord):
    aliases = ['questtier']
    desc = "Sets the target's quest tier to specified value."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("tier", int, True)]

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg == 0:
            return ('0', 'Toontown Central'), ('4', "Donald's Dock"), ('7', "Daisy Gardens"), ('8', "Minnie's Melodyland"), ('11', "The Brrrgh"), ('14', "Donald's Dreamland"), \
                   ('18', "Donald's Dreamland"), ('32', "Bossbot HQ"), ('49', "Cog Nation"), ('51', "Elder")
        return None

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 0:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                tier = int(entry)
                return 0 <= tier <= 255
            return False
        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        tier = args[0]

        if not 0 <= tier <= 255:
            return "Can't set {}'s quest tier to {}! Specify a value between 0 and 255.".format(toon.getName(), tier)

        toon.b_setRewardHistory(tier, [])
        toon.fixAvatar()
        toon.correctLaff()
        return "Set %s's quest tier to %d." % (toon.getName(), tier)


class SetExp(MagicWord):
    aliases = ["exp"]
    desc = "Sets the target's experience for the specified gag track. The default amount is 0."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("track", str, True), ("amount", int, False, 0)]

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg == 0:
            return ('Toon-Up', None), ('Trap', None), ('Lure', None), ('Sound', None), ('Throw', None), ('Squirt', None), ('Drop', None), ('Maxed', None)
        elif arg == 1:
            return ('0', 'Minimum'), ('20', None), ('100', None), ('200', None), ('500', None), ('800', None), ('2000', None), \
                   ('2500', None), ('4000', None), ('6000', None), ('7500', None), ('10000', None), ('10500', 'Maximum')

        return None

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 1:
            track = str(entry).lower()
            return track in ['toon-up', 'trap', 'lure', 'sound', 'throw', 'squirt', 'drop', 'max', 'maxed', 'maxxed']
        elif arg == 1:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                amt = int(entry)
                return 0 <= amt <= 10500
            return False
        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        track = args[0].lower()
        amt = args[1]

        tracks = ['toon-up', 'trap', 'lure', 'sound', 'throw', 'squirt', 'drop']
        maxed = ['max', 'maxed', 'maxxed']

        if track not in tracks + maxed:
            return "Invalid gag track specified!"

        if not 0 <= amt <= 10500:
            return "Can't set {0}'s {1} exp to {2}! Specify a value between 0 and 10,500.".format(toon.getName(), track,
                                                                                                  amt)

        if track in maxed:
            for track in tracks:
                toon.experience.setExp(track, 10500)
            toon.b_setExperience(toon.experience.makeNetString())
            return "Maxed all of {}'s gag tracks.".format(toon.getName())
        else:
            trackIndex = TTLocalizer.BattleGlobalTracks.index(track)
            toon.experience.setExp(trackIndex, amt)
            toon.b_setExperience(toon.experience.makeNetString())
            return "Set %s exp to %d successfully." % (track, amt)


class SetTrackBonus(MagicWord):
    aliases = ["trackbonus"]
    desc = "Sets the target's track bonus level."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("track", int, True)]

    def handleWord(self, invoker, avId, toon, *args):
        track = args[0]

        trackLength = ToontownBattleGlobals.UBER_GAG_LEVEL_INDEX
        numTracks = ToontownBattleGlobals.NUM_GAG_TRACKS
        gagAccess = toon.getTrackAccess()

        trackBonusLevel = [-1] * numTracks
        if track == 8:
            bonusAccess = lambda x: trackLength if x > 0 else x
            trackBonusLevel = list(map(bonusAccess, gagAccess))
        elif 0 <= track < numTracks:
            if gagAccess[track]:
                trackBonusLevel[track] = trackLength
            else:
                return "{} doesn't have the specified gag track!".format(toon.getName())
        else:
            return "Invalid gag track specified!"

        toon.b_setTrackBonusLevel(trackBonusLevel)
        return "Track bonus set for {}!".format(toon.getName())


class SetCogSuit(MagicWord):
    aliases = ["cogsuit", "setdisguise", "disguise"]
    desc = "Set disguise type and level."
    advancedDesc = "This Magic Word will change the target's Cog Disguise. To remove the disguise entirely, " \
                   "specify the corresponding Cog Department. For example, if you want to remove your Cashbot " \
                   "disguise, you would specify 'cashbot'. To change the Cog Type and Level of your disguise, " \
                   "specify a cog type abbreviation and level. For example, if you want to become a level 23 The " \
                   "Big Cheese, you would specify 'tbc 23'."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("type", str, True), ("level", int, False, 0)]

    def handleWord(self, invoker, avId, toon, *args):
        type = args[0].lower()
        level = args[1]

        corps = ('bossbot', 'lawbot', 'cashbot', 'sellbot')

        # If the department is provided, that means we should reset their progress no matter the "level" arg
        if type in corps:
            # Even if they provided a level arg, just overwrite it to 0 so our laff calculations have no problem
            level = 0
            corpIndex = corps.index(type)

            # Get info related to the target's cog disguises
            parts = toon.getCogParts()
            types = toon.getCogTypes()
            levels = toon.getCogLevels()
            merits = toon.getCogMerits()

            # Change their laff points respectively
            for levelBoost in [14, 19, 29, 39, 49]:
                if level <= levelBoost and not levelBoost > toon.getCogLevels()[corpIndex]:
                    if toon.getMaxHp() <= 15:
                        continue
                    toon.b_setMaxHp(toon.getMaxHp() - 1)
                elif level > levelBoost and not levelBoost <= toon.getCogLevels()[corpIndex]:
                    if toon.getMaxHp() >= 137:
                        continue
                    toon.b_setMaxHp(toon.getMaxHp() + 1)
            if toon.getHp() > toon.getMaxHp():
                toon.takeDamage(toon.getHp() - toon.getMaxHp())
            else:
                toon.toonUp(toon.getMaxHp() - toon.getHp())

            # Set everything to 0, because we want to reset their progress
            parts[corpIndex] = 0
            types[corpIndex] = 0
            levels[corpIndex] = 0
            merits[corpIndex] = 0

            # Update it on the Toon
            toon.b_setCogParts(parts)
            toon.b_setCogTypes(types)
            toon.b_setCogLevels(levels)
            toon.b_setCogMerits(merits)

            return "Reset {}'s {} disguise.".format(toon.getName(), type.capitalize())

        suits = ToontownGlobals.GreenEffectMassFlyCogs[:]
        suits.reverse()

        # If a suit type is provided, that means we should automatically detect which corp disguise to change
        corpIndex = -1
        typeIndex = -1
        for dept in suits:
            for suit in dept:
                if type == suit:
                    corpIndex = suits.index(dept)
                    typeIndex = dept.index(type)
                    break

        if corpIndex == -1 or typeIndex == -1:
            return "Invalid Cog Type specified!"

        # Make sure they gave a level that is in range.
        if typeIndex == 7:
            # The final suit can go up to Level 50.
            levelRange = list(range(8, 51))
        else:
            levelRange = list(range((typeIndex + 1), (typeIndex + 6)))
        if level not in levelRange:
            return "Invalid Cog Disguise level specified!"

        # Reset their merits to 0.
        merits = toon.getCogMerits()
        merits[corpIndex] = 0
        toon.b_setCogMerits(merits)

        # Ensure they have all the parts.
        parts = toon.getCogParts()
        parts[corpIndex] = CogDisguiseGlobals.PartsPerSuitBitmasks[corpIndex]
        toon.b_setCogParts(parts)

        # Find out if they need laff boosts or laff points removed.
        for levelBoost in [14, 19, 29, 39, 49]:
            if level <= levelBoost and not levelBoost > toon.getCogLevels()[corpIndex]:
                if toon.getMaxHp() <= 15:
                    continue
                toon.b_setMaxHp(toon.getMaxHp() - 1)
            elif level > levelBoost and not levelBoost <= toon.getCogLevels()[corpIndex]:
                if toon.getMaxHp() >= 137:
                    continue
                toon.b_setMaxHp(toon.getMaxHp() + 1)
        # Lets be nice and give them a toonup or make them suffer.
        if toon.getHp() > toon.getMaxHp():
            toon.takeDamage(toon.getHp() - toon.getMaxHp())
        else:
            toon.toonUp(toon.getMaxHp() - toon.getHp())

        # Set their type and level that they specified.
        types = toon.getCogTypes()
        types[corpIndex] = typeIndex
        toon.b_setCogTypes(types)
        levels = toon.getCogLevels()
        levels[corpIndex] = level - 1  # -1 because it starts at 0
        toon.b_setCogLevels(levels)

        return "Set {}'s {} disguise to {} Level {}.".format(toon.getName(), corps[corpIndex].capitalize(),
                                                             type, level)

# TODO: validation on local avatar, nearby target if it exists
class SetMerits(MagicWord):
    aliases = ["merits"]
    desc = "Sets the target's merits to the specified value."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("corp", str, True), ("amount", int, True)]

    def handleWord(self, invoker, avId, toon, *args):
        corp = args[0]
        amount = args[1]
        corps = ['bossbot', 'lawbot', 'cashbot', 'sellbot']
        if corp not in corps:
            return "Invalid cog department specified."
        corpIndex = corps.index(corp)

        total = CogDisguiseGlobals.getTotalMerits(toon, corpIndex)
        if amount > total:
            return f"{toon.getName()} cannot have more than {total} {TTLocalizer.RewardPanelMeritBarLabels[corpIndex]} in their current {corp.capitalize()} suit."
        merits = toon.getCogMerits()
        merits[corpIndex] = amount
        toon.b_setCogMerits(merits)
        return "Set {0}'s {1} to {2}.".format(toon.getName(), TTLocalizer.RewardPanelMeritBarLabels[corpIndex], amount)


class Fanfare(MagicWord):
    desc = "Gives the target a fanfare, because why not?"
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    accessLevel = "MODERATOR"

    def handleWord(self, invoker, avId, toon, *args):
        toon.d_generateFanfare()
        return "much congratulations. many trumpets. wow. (Fanfare given to {}.)".format(toon.getName())


class SetPouch(MagicWord):
    aliases = ["pouch", "setgagpouch", "gagpouch", "setmaxgags"]
    desc = "Sets the target's max gag pouch limit."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("amount", int, True)]

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg == 0:
            return ('1', 'Minimum'), ('20', 'Starter Pouch'), ('25', 'Medium Pouch'), ('30', 'Large Pouch'), ('35', 'Small Bag'), ('40', 'Medium Bag'), ('50', 'Large Bag'), \
                   ('60', 'Small Backpack'), ('70', 'Medium Backpack'), ('80', 'Large Backpack'), ('255', 'Maximum')
        return None

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 0:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                amt = int(entry)
                return 1 <= amt <= 255
            return False
        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        amt = args[0]

        if not 1 <= amt <= 255:
            return "Can't set {0}'s pouch size to {1}! Specify a value between 1 and 255.".format(toon.getName(), amt)

        toon.b_setMaxCarry(amt)
        return "Set {0}'s pouch size to {1}.".format(toon.getName(), amt)


class SetNametagStyle(MagicWord):
    aliases = ["setnametag", "nametag", "nametagstyle"]
    desc = "Sets the style of the target's nametag to the specified ID."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("style", str, True)]

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg == 0:
            return ((x, None) for x in ['Basic'] + list(TTLocalizer.NametagFontNames))
        return None

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 0:
            styleName = str(entry).lower()
            nametag_list = list(TTLocalizer.NametagFontNames)
            for index, item in enumerate(nametag_list):
                nametag_list[index] = item.lower()
            return styleName in nametag_list

        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        styleName = args[0]

        nametag_list = list(TTLocalizer.NametagFontNames)
        for index, item in enumerate(nametag_list):
            nametag_list[index] = item.lower()
        styleName = styleName.lower()

        if styleName in nametag_list:
            index = nametag_list.index(styleName)
        elif styleName == "basic":
            index = 100
        else:
            return "Invalid nametag name entered."

        toon.b_setNametagStyle(index)
        return "Set {}'s nametag style successfully.".format(toon.getName())


class SetNametagType(MagicWord):
    aliases = ["nametagtype", "nametype", "lacker"]
    desc = "Set the style of the target's nametag to the specified ID."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("type", int, False, 0)]

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg == 0:
            return ('0', 'Normal'), ('1', 'Non Player'), ('3', 'Cog')
        return None

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 0:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                type = int(entry)
                return type in [0, 1, 3]
            return False 

        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        type = args[0]

        nametagTypeList = [(0, NametagGroup.CCNormal), (1, NametagGroup.CCNonPlayer), (3, NametagGroup.CCSuit)]
        for nametag in nametagTypeList:
            if type == nametag[0]:
                toon.b_setNametagType(nametag[0])
                return "Changed {}'s nametag type successfully.".format(toon.getName())

        return "Invalid nametag type specified!"


class SetNametagColor(MagicWord):
    aliases = ["nametagcolor", "namecolor", "colorname"]
    desc = "Set the color of the target's nametag to the specified RGB value."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("r", float, False, 0.0),
                 ("g", float, False, 0.0),
                 ("b", float, False, 0.0)]

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg in [0, 1, 2]:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                color = float(entry)
                return 0.0 <= color <= 255.0
            return False 

        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        r = args[0]
        g = args[1]
        b = args[2]

        if not all(0.0 <= x <= 255.0 for x in (r, g, b)):
            return "Color numbers must be in range 0-255!"

        toon.b_setNametagColor(r / 255., g / 255., b / 255.)

        if (r, g, b) == (0, 0, 0):
            return "Reset {}'s nametag color back to normal.".format(toon.getName())
        return "Changed {}'s nametag color successfully.".format(toon.getName())


class SetLaffMeterTextColor(MagicWord):
    aliases = ["laffmetertextcolor", "lafftextcolor", "laffmetertextfg", "lafftextfg"]
    desc = "Set the text color of the target's laff meter to the specified RGB value."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("r", int, False, 0),
                 ("g", int, False, 0),
                 ("b", int, False, 0)]

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg in [0, 1, 2]:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                color = int(entry)
                return 0 <= color <= 255
            return False 

        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        r = args[0]
        g = args[1]
        b = args[2]

        if not all(0 <= x <= 255 for x in (r, g, b)):
            return "Color numbers must be in range 0-255!"

        toon.b_setLaffMeterTextColor(r, g, b)

        if (r, g, b) == (0, 0, 0):
            return "Reset {}'s laff meter text color back to normal.".format(toon.getName())
        return "Changed {}'s laff meter text color successfully.".format(toon.getName())


class UnlockPhrase(MagicWord):
    aliases = ["phrase", "addphrase"]
    desc = "Unlocks a new phrase and adds it to target's list of 'My Phrases'."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("id", int, True)]

    def handleWord(self, invoker, avId, toon, *args):
        phraseId = args[0]

        strings = OTPLocalizer.CustomSCStrings
        scId = int(phraseId) * 10
        id = None
        if scId in iter(strings.keys()):
            id = scId

        if id:
            if toon.customMessages.count(id) != 0:
                return "{} already has this custom phrase!".format(toon.getName())
            if len(toon.customMessages) >= ToontownGlobals.MaxCustomMessages:
                toon.customMessages = toon.customMessages[1:]
            toon.customMessages.append(id)
            toon.d_setCustomMessages(toon.customMessages)
            return "Added phrase id {0} to {1}'s list.".format(id, toon.getName())

        return "Invalid phrase id! Could not set."


class SetSos(MagicWord):
    aliases = ["sos", "givesos"]
    desc = "Sets your SOS cards. The default is 1 Flippy card."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("name", str, False, 'Flippy'), ("amount", int, False, 1)]

    def handleWord(self, invoker, avId, toon, *args):
        boss = toon.findBoss()
        if boss and boss.hardcore:
            return "You cannot cheat in this Boss Battle!"

        name = args[0]
        amt = args[1]

        if name == "0":
            for npcId in list(toon.NPCFriendsDict.keys()):
                del toon.NPCFriendsDict[npcId]
            toon.d_setNPCFriendsDict(toon.NPCFriendsDict)
            return "Deleted all SOS cards successfully."

        npcId = None

        for id, npcName in list(NPCToons.getNPCToonsNames().items()):
            npcNameLower = npcName.lower()
            npcNameStripped = npcNameLower.replace(" ", "")
            if name.lower() in (npcNameLower, npcNameStripped):
                if id not in NPCToons.npcFriends:
                    continue
                else:
                    npcId = id
                    break

        if not npcId:
            return "The {0} SOS card was not found!".format(name)

        if len(list(toon.NPCFriendsDict.keys())) >= toon.maxNPCFriends and npcId not in toon.NPCFriendsDict:
            return "{} already has the maximum amount of SOS cards.".format(toon.getName())

        if not 0 <= amt <= 100:
            return "The amount must be between 0 and 100!"

        npcName = NPCToons.getNPCName(npcId)

        if (amt == 0) and (npcId in toon.NPCFriendsDict):
            del toon.NPCFriendsDict[npcId]
            toon.d_setNPCFriendsDict(toon.NPCFriendsDict)
            return "Deleted all {} SOS cards successfully.".format(npcName)
        else:
            toon.NPCFriendsDict[npcId] = amt
            toon.d_setNPCFriendsDict(toon.NPCFriendsDict)
            return "Restocked {0} {1} SOS cards successfully!".format(amt, npcName)


class FreeBldg(MagicWord):
    aliases = ["freecogbldg", "freecogbuilding", "freebuilding"]
    desc = "Turns the closest Cog Building to the target back into a Toon Building"
    execLocation = MagicWordConfig.EXEC_LOC_SERVER

    def handleWord(self, invoker, avId, toon, *args):
        # If we're in the Outskirts, be lenient with the visgroups
        # Use the branch zone because sometimes we can be in other zones
        lenient = False
        if ZoneUtil.getCanonicalBranchZone(toon.zoneId) == ToontownGlobals.ToontownOutskirts:
            lenient = True
        returnCode = toon.doBuildingFree(lenient)
        state = returnCode[0]

        if state == 'success':
            return "Successfully took back the nearest Cog Building from the Cogs!"
        elif state == 'busy':
            return "Toons are currently taking back the building!"
        elif state == 'badlocation':
            return "Could not locate a nearby Cog Building to take back."

        return "Could not locate a nearby Cog Building to take back."

class MaxFishing(MagicWord):
    aliases = ['maxfish']
    desc = "Maxes the target's fishing data."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER

    def handleWord(self, invoker, avId, toon, *args):
        # Add all fish to their collection, set their rod to gold, and max out fishing trophies
        allFish = TTLocalizer.FishSpeciesNames
        fishLists = [[], [], []]
        for genus in list(allFish.keys()):
            for species in range(len(allFish[genus])):
                fishLists[0].append(genus)
                fishLists[1].append(species)
                fishLists[2].append(FishGlobals.getRandomWeight(genus, species))
        toon.b_setFishCollection(*fishLists)
        toon.b_setFishingRod(FishGlobals.MaxRodId)
        toon.b_setFishingTrophies(list(FishGlobals.TrophyDict.keys()))
        return "{}'s fishing data has been maxed.".format(toon.getName())

class MaxRacing(MagicWord):
    aliases = ['maxrace', 'maxkart']
    desc = "Maxes the target's racing data."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER

    def handleWord(self, invoker, avId, toon, *args):
        # Give them the most expensive kart, maxed out tickets, and complete racing trophies
        if not toon.hasKart() and simbase.wantKarts:
            toon.b_setKartBodyType(list(KartDict.keys())[1])
        toon.b_setTickets(RaceGlobals.MaxTickets)
        maxTrophies = RaceGlobals.NumTrophies + RaceGlobals.NumCups
        toon.b_setKartingTrophies(list(range(1, maxTrophies + 1)))
        toon.b_setTickets(99999)
        return "{}'s racing data has been maxed.".format(toon.getName())

class MaxGolfing(MagicWord):
    aliases = ['maxgolf']
    desc = "Maxes the target's golfing data."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER

    def handleWord(self, invoker, avId, toon, *args):
        # Complete all the golfing trophies
        toon.b_setGolfHistory([600] * (GolfGlobals.MaxHistoryIndex * 2 + 2))
        return "{}'s garden has been maxed.".format(toon.getName())

class MaxGarden(MagicWord):
    desc = "Maxes the target's garden."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER

    def handleWord(self, invoker, avId, toon, *args):
        # Give a garden if they don't already have one
        if not toon.getGardenStarted():
            estate = self.air.estateMgr.estate.get(toon.doId)
            if estate:
                estate.placeStarterGarden(toon.doId)

        toon.b_setShovel(3)
        toon.b_setWateringCan(3)
        toon.b_setShovelSkill(639)
        toon.b_setWateringCanSkill(999)
        varietyList = []
        speciesList = []
        flowerSpecies = GardenGlobals.getFlowerSpecies()
        for species in flowerSpecies:
            numVarieties = len(GardenGlobals.getFlowerVarieties(species))
            for variety in range(numVarieties):
                speciesList.append(species)
                varietyList.append(variety)
        toon.b_setFlowerCollection(speciesList, varietyList)
        toon.b_setGardenTrophies(list(GardenGlobals.TrophyDict.keys()))
        return "{}'s garden has been maxed.".format(toon.getName())


class MailFurniture(MagicWord):
    # CatalogFurnitureItem has the delivery ID list; not the same as the list in the localizer
    aliases = ["furniture"]
    desc = "Mails a piece of furniture as denoted from the delivery ID list. Default will mail you a radio."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    affectRange = [MagicWordConfig.AFFECT_SELF]  # Don't want people flooding other's mailboxes
    arguments = [("id", int, False, 1210), ("quantity", int, False, 1)]

    def handleWord(self, invoker, avId, toon, *args):
        id = args[0]
        quantity = args[1]
        from toontown.catalog.CatalogFurnitureItem import CatalogFurnitureItem, FurnitureTypes
        if id not in FurnitureTypes:
            return "Invalid item ID specified."
        furnitureItem = CatalogFurnitureItem(id)
        furnitureItem.deliveryDate = int(time.time() / 60 + 0.5)  # instant delivery
        total = 0
        for amt in range(quantity):
            if len(invoker.mailboxContents) + len(invoker.onGiftOrder) > ToontownGlobals.MaxMailboxContents:
                return "Error: Mailbox is full! Only {} out of {} has been mailed.".format(amt, quantity)
            invoker.onOrder.append(furnitureItem)
            invoker.b_setDeliverySchedule(invoker.onOrder)
            total = amt + 1
        return '{} {} mailed successfully.'.format(total, furnitureItem.getName())


class MailAllFurniture(MagicWord):
    aliases = ["allfurniture", "furnitures"]
    desc = "Mails a certain quantity of each type of available furniture from the Cattlelog. By default, the quantity " \
           "is 1."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    affectRange = [MagicWordConfig.AFFECT_SELF]  # Don't want people flooding other's mailboxes
    arguments = [("quantity", int, False, 1)]

    def handleWord(self, invoker, avId, toon, *args):
        quantity = args[0]
        from toontown.catalog.CatalogFurnitureItem import getAllFurnitures, FurnitureTypes
        for furnitureID in FurnitureTypes:
            for furnitureItem in getAllFurnitures(furnitureID):
                furnitureItem.deliveryDate = int(time.time() / 60 + 0.5)  # Instant delivery
                for amt in range(quantity):  # No need to check to see if mailbox is full w/ this command
                    invoker.onOrder.append(furnitureItem)
                invoker.b_setDeliverySchedule(invoker.onOrder)
        return 'Furniture has been mailed.'


class ToggleInstantDelivery(MagicWord):
    aliases = ["fastdelivery", "togglefastdelivery", "toggleinstadelivery", "instantdelivery", "instadelivery",
               "speedydelivery"]
    desc = "Toggles instant delivery of all cattlelog items to your house."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    affectRange = [MagicWordConfig.AFFECT_SELF]

    def handleWord(self, invoker, avId, toon, *args):
        invoker.instantDelivery = not invoker.instantDelivery
        if invoker.instantDelivery and len(invoker.onOrder) > 0:
            for catalogItem in invoker.onOrder:
                catalogItem.deliveryDate = int(time.time() / 60 + 0.5)
            for catalogItem in invoker.onGiftOrder:
                catalogItem.deliveryDate = int(time.time() / 60 + 0.5)
            for catalogItem in invoker.onAwardOrder:
                catalogItem.deliveryDate = int(time.time() / 60 + 0.5)
            invoker.onOrder.markDirty()
            invoker.b_setDeliverySchedule(invoker.onOrder)
            return f"Instant Delivery has been turned on with {len(invoker.onOrder)} {'orders' if len(invoker.onOrder) > 1 else 'order'} being delivered right now!"
        return "Instant Delivery has been turned {0}.".format('on' if invoker.instantDelivery else 'off')


class TPose(MagicWord):
    aliases = ["settpose", "forcetpose"]
    desc = "Forces T-Pose on yourself."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER

    def handleWord(self, invoker, avId, toon, *args):
        toon.d_setTPose()
        return "Forced {} into a T-Pose.".format(toon.getName())


class SetAnimalSound(MagicWord):
    aliases = ["animalsound", "forceanimalsound", "speciesdialogue"]
    desc = "Forces you to make a specific animal sound for this session."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("animalType", str, False, '')]

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg == 0:
            return ((str(x), None) for x in ToontownGlobals.ValidAnimalTypes)
        return None

    def handleWord(self, invoker, avId, toon, *args):
        animalSound = args[0]

        if not animalSound:
            toon.d_setAnimalSound('')
            return "No longer forcing animal sound on {0}.".format(toon.getName())
        if animalSound not in ToontownGlobals.ValidAnimalTypes:
            return "{0} is not a valid animal sound!".format(animalSound)

        toon.d_setAnimalSound(animalSound)
        return "Set animal sound to {0} for {1}.".format(animalSound, toon.getName())


class SetMuzzle(MagicWord):
    aliases = ["muzzle"]
    desc = "Sets the target's muzzle to the specified type."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("id", int, False, 0)]

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg == 0:
            return ((str(x), MuzzleNames[x]) for x in range(6))
        return None

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 0:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                type = int(entry)
                return 0 <= type <= 5
            return False

        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        muzzleType = args[0]
        if not 0 <= muzzleType <= 5:
            return "The muzzle type must be between 0 and 5!"

        toon.b_setMuzzle(muzzleType)
        return f'Set muzzle to {MuzzleNames[muzzleType].lower()} for {toon.getName()}'


class SetEyes(MagicWord):
    aliases = ["eyes"]
    desc = "Sets the target's eyes to the specified type."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("id", int, False, 0)]

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg == 0:
            return ((str(x), EyeNames[x]) for x in range(9))
        return None

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 0:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                type = int(entry)
                return 0 <= type <= 8
            return False 

        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        eyeType = args[0]

        if not 0 <= eyeType <= 8:
            return "The eye type must be between 0 and 8!"

        toon.b_setEyes(eyeType)
        return f"Set eyes to {EyeNames[eyeType].lower()} for {toon.getName()}!"


class ToggleJapanDialog(MagicWord):
    aliases = ["togglejapanesedialog", "japandialog", "japanesedialog"]
    desc = "Toggles Japanese dialog for certain characters speaking to the target."
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT
    accessLevel = 'USER'

    def handleWord(self, invoker, avId, toon, *args):
        if base.japanDialog:
            base.japanDialog = 0
            ClientSettings.JapanDialog.set(False)
            return "Toggled Japanese dialog to off for {}.".format(toon.getName())
        else:
            base.japanDialog = 1
            ClientSettings.JapanDialog.set(True)
            return "Toggled Japanese dialog to on for {}.".format(toon.getName())


class PlaySound(MagicWord):
    aliases = ["sound", "playsfx", "sfx"]
    desc = "Plays a sound given by its name on the specified toon."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("name", str, True), ("loop", int, False, 0)]

    def handleWord(self, invoker, avId, toon, *args):
        sound = args[0]
        loop = args[1]
        # Sanity check to make sure people can't crash the server by putting bad values
        if loop not in (0, 1):
            loop = 0
        toon.d_playSound(sound, loop)
        return "Attempting to play %s on %s." % (sound, toon.getName())


class Drop(MagicWord):
    aliases = ["trolley", "dingding", "littlecat"]
    desc = "Creates a prop that falls from the sky on the specified target."
    cooldown = 5.0
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("propName", str, False, 'Trolley')]

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg == 0:
            return ((x, None) for x in DropPropGlobals.DropPropList.keys())
        return None

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 0:
            propName = DropPropGlobals.getDropPropNameCaseInsensitive(str(entry))
            if propName is not None:
                return True
            return False
        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        propName = args[0]

        valid = False
        propName = DropPropGlobals.getDropPropNameCaseInsensitive(propName)
        if propName is not None:
            valid = True        

        if not valid:
            return "Invalid drop prop name."

        toon.d_generateDropProp(propName)
        return "Drop prop spawned for {}!".format(toon.getName())


class SetTaskCarryLimit(MagicWord):
    aliases = ["taskcarrylimit", "settaskcarry", "taskcarry", "setcarry"]
    desc = "Set the amount of tasks the target can carry."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("limit", int, False, 1)]

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg == 0:
            return ('0', 'Minimum'), ('1', None), ('2', None), ('3', None), ('4', 'Maximum')
        return None

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 0:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                amt = int(entry)
                return 1 <= amt <= 4
            return False 

        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        amt = args[0]
        plural = 's'

        if not 1 <= amt <= 4:
            return "The amount must be between 1 and 4!"
        if amt == 1:
            plural = ''
        toon.b_setQuestCarryLimit(amt)
        return f"{toon.getName()} can now carry {amt} task{plural}!"


class ToggleAlwaysHitCogs(MagicWord):
    aliases = ["alwayshitcogs", "hitcogs", "setalwayshitcogs", "alwayshit"]
    desc = "Toggles always hitting cogs. When enabled, the target will have 100% gag accuracy at all times."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER

    def handleWord(self, invoker, avId, toon, *args):
        if not toon:
            return

        boss = toon.findBoss()
        if boss and boss.hardcore:
            return "You cannot cheat in this Boss Battle!"

        if not toon.getAlwaysHitSuits():
            toon.setAlwaysHitSuits(True)
        else:
            toon.setAlwaysHitSuits(False)

        return "Toggled always hitting Cogs {0} for {1}.".format('ON' if toon.getAlwaysHitSuits() else 'OFF',
                                                                 toon.getName())

class ToggleCogsAlwaysMiss(MagicWord):
    aliases = ["alwayscogsmiss", "cogsmiss", "setcogsalwaysmiss"]
    desc = "Toggles cogs always missing. When enabled, Cogs will miss the target."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER

    def handleWord(self, invoker, avId, toon, *args):
        if not toon:
            return

        boss = toon.findBoss()
        if boss and boss.hardcore:
            return "You cannot cheat in this Boss Battle!"

        toon.setCogsAlwaysHit(False)

        toon.setCogsAlwaysMiss(not toon.getCogsAlwaysMiss())

        return f"Toggled Cogs always miss {'ON' if toon.getCogsAlwaysMiss() else 'OFF'} for {toon.getName()}."

class ToggleCogsAlwaysHit(MagicWord):
    aliases = ["alwayscogshit", "cogshit", "setcogsalwayshit"]
    desc = "Toggles cogs always hitting. When enabled, Cogs will hit the target."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER

    def handleWord(self, invoker, avId, toon, *args):
        if not toon:
            return

        boss = toon.findBoss()
        if boss and boss.hardcore:
            return "You cannot cheat in this Boss Battle!"

        toon.setCogsAlwaysMiss(False)

        toon.setCogsAlwaysHit(not toon.getCogsAlwaysHit())

        return f"Toggled Cogs always hit {'ON' if toon.getCogsAlwaysHit() else 'OFF'} for {toon.getName()}."

class ToggleFireworks(MagicWord):
    aliases = ["fireworks", "startfireworks", "beginfireworks"]
    desc = "Start a fireworks show.  Spawns in the current zone you're in by default."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("showName(summer/july4, newyears, party, combo)", str, False, "july4"),
                 ("startInAllZones", bool, False, False)]
    accessLevel = "MODERATOR"

    def handleWord(self, invoker, avId, toon, *args):
        showName = args[0]
        startAll = args[1]

        zoneId = invoker.zoneId

        if showName in ('summer', 'july4'):
            showType = ToontownGlobals.JULY4_FIREWORKS
        elif showName == 'newyears':
            showType = ToontownGlobals.NEWYEARS_FIREWORKS
        elif showName == 'party':
            showType = PartyGlobals.FireworkShows.Summer
        elif showName == 'combo':
            showType = ToontownGlobals.COMBO_FIREWORKS
        else:
            return 'Improper firework type specified. Refer to your Spellbook for acceptable types.'

        fireworkMgr = simbase.air.fireworkManager

        if startAll:
            isFireworksAlreadyRunning = len(fireworkMgr.fireworkShows)
            fireworkMgr.startAllShows(showType)
            if isFireworksAlreadyRunning:
                return 'Started fireworks in all playgrounds (Except those that currently have a show running)!'
            else:
                return 'Started fireworks in all playgrounds!'

        if not ZoneUtil.isPlayground(zoneId):
            return 'You cannot start a firework show outside the playground!'

        if ZoneUtil.isBetaPlaygroundZone(zoneId):
            return 'You cannot start a firework show in beta playgrounds!'

        if ZoneUtil.isCogHQZone(zoneId):
            return 'You cannot start a firework show in a Cog Headquarters!'

        if zoneId not in fireworkMgr.zoneToStyleDict:
            return 'Could not start a firework show because no show style is defined for this playground.'

        if fireworkMgr.isShowRunning(zoneId):
            return 'A firework show is already running in the playground you\'re currently in. Please wait before ' \
                   'starting another.'

        if fireworkMgr.startShow(showType, zoneId, fireworkMgr.zoneToStyleDict[zoneId]):
            return 'Started fireworks in the current playground!'


class Snap(MagicWord):
    desc = "Temporaily snaps your Toon out of existence."
    affectRange = [MagicWordConfig.AFFECT_SELF]
    execLocation = MagicWordConfig.EXEC_LOC_SERVER

    def handleWord(self, invoker, avId, toon, *args):
        toon.d_generateSnapEffect()
        return "Your Toon will now be snapped out of existence!"


class MakeToonGoSad(MagicWord):
    aliases = ["gosad", "green"]
    desc = "Makes the targeted Toon go sad with the specified character."
    cooldown = 5.0
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("character", str, False, 'f')]

    def handleWord(self, invoker, avId, toon, *args):
        character = args[0]
        hqOfficers = []
        type = 0
        toonId = 0
        if character not in SuitDNA.suitHeadTypes:
            for npcId, npcName in list(TTLocalizer.NPCToonNames.items()):
                if character.lower() == 'hq officer':
                    if npcName.lower() != 'hq officer':
                        continue
                    hqOfficers.append(npcId)
                elif character.lower() == npcName.lower():
                    if character.lower() != 'kong':
                        toonId = npcId
                        type = 1
                        break
            if hqOfficers:
                toonId = random.choice(hqOfficers)
                type = 1
            elif character == 'toon':
                toonId = 2
                type = 1
            elif character == 'panda':
                type = 2
            elif character not in [TTLocalizer.SellbotP.lower(), TTLocalizer.CashbotP.lower(),
                                   TTLocalizer.LawbotP.lower(), TTLocalizer.BossbotP.lower()] and type != 1:
                return "Invalid character name! Target could not go sad."
        if type == 1:
            toon.d_generateGreenEffect(character, toonId)
            if toonId == 2 and toon.cogIndex != 0:
                landingDuration = 10.0
            else:
                landingDuration = 5.5
            seq = Sequence(Wait(landingDuration), Func(toon.b_setHp, -1))
        elif type == 2:
            toon.d_generateGreenEffect(character, 0)
            seq = Sequence(Func(toon.b_setHp, -1))
        else:
            toon.d_generateGreenEffect(character, 0)
            seq = Sequence(Wait(10.0), Func(toon.b_setHp, -1))
        seq.start()
        return f"{toon.getName()} is going sad!"


class EndFlying(MagicWord):
    aliases = ["endflyinggame", "setendflying", "setendflyinggame"]
    desc = "Ends the flying game in a Lawbot Field Office."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER

    def handleWord(self, invoker, avId, toon, *args):
        from toontown.cogdominium.DistCogdoFlyingGameAI import DistCogdoFlyingGameAI
        flyingGame = None
        for do in list(simbase.air.doId2do.values()):
            if isinstance(do, DistCogdoFlyingGameAI):
                if invoker.doId in do.getToonIds():
                    flyingGame = do
                    break

        if flyingGame:
            flyingGame._handleGameFinished()
            return "Completed the flying game."
        else:
            return "You are not in a flying game! Could not complete."


class Ping(MagicWord):
    desc = "Pong!"
    execLocation = MagicWordConfig.EXEC_LOC_SERVER

    def handleWord(self, invoker, avId, toon, *args):
        return "Pong!"


class GardenGame(MagicWord):
    aliases = ["gardendrop"]
    desc = "Start the garden drop mini-game."
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT

    def handleWord(self, invoker, avId, toon, *args):
        from toontown.estate import GardenDropGame
        base.localAvatar.game = GardenDropGame.GardenDropGame()
        return "Started the garden drop mini-game."


class WinGame(MagicWord):
    aliases = ["winminigame", "skiptrolley"]
    desc = "Win the trolley game you are in."
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT

    def handleWord(self, invoker, avId, toon, *args):
        messenger.send("minigameVictory")
        return "Trolley game won."


class LeftHandProp(MagicWord):
    aliases = ["lefthand", "proplefthand"]
    desc = "Attaches a prop to the target's left hand."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("prop", str, False, '')]

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 0:
            valid = False
            propName = PropGlobals.getPropNameCaseInsensitive(str(entry))
            if propName is not None:
                valid = True
            if not valid:
                for prop in [x[0] for x in ToontownGlobals.PropsBattle]:
                    propLower = prop.lower()
                    propStripped = propLower.replace(" ", "")
                    if propName == propLower or propName == propStripped:
                        valid = True
                        propName = prop
                        break
            return valid
        elif arg == 1:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                scale = float(entry)
                return 0.1 <= scale <= 5
            return False
        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        propName = args[0]

        if not propName:
            toon.d_setLeftHand(propName)
            return "Cleared the target's left hand."

        valid = False
        propName = PropGlobals.getPropNameCaseInsensitive(propName)
        if propName is not None:
            valid = True

        # Incase it wasn't found in the regular props, it could be a battleprop
        if not valid:
            for prop in [x[0] for x in ToontownGlobals.PropsBattle]:
                propLower = prop.lower()
                propStripped = propLower.replace(" ", "")
                if propName == propLower or propName == propStripped:
                    valid = 1
                    propName = prop
                    break

        if not valid:
            return "Invalid prop name!"

        toon.d_setLeftHand(propName)

        return "Prop attached to target's left hand."


class RightHandProp(MagicWord):
    aliases = ["righthand", "proprighthand"]
    desc = "Attaches a prop to the target's right hand."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("prop", str, False, '')]

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 0:
            valid = False
            propName = PropGlobals.getPropNameCaseInsensitive(str(entry))
            if propName is not None:
                valid = True
            if not valid:
                for prop in [x[0] for x in ToontownGlobals.PropsBattle]:
                    propLower = prop.lower()
                    propStripped = propLower.replace(" ", "")
                    if propName == propLower or propName == propStripped:
                        valid = True
                        propName = prop
                        break
            return valid
        elif arg == 1:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                scale = float(entry)
                return 0.1 <= scale <= 5
            return False
        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        propName = args[0]

        if not propName:
            toon.d_setRightHand(propName)
            return "Cleared the target's right hand."

        valid = False
        propName = PropGlobals.getPropNameCaseInsensitive(propName)
        if propName is not None:
            valid = True

        # Incase it wasn't found in the regular props, it could be a battleprop
        if not valid:
            for prop in [x[0] for x in ToontownGlobals.PropsBattle]:
                propLower = prop.lower()
                propStripped = propLower.replace(" ", "")
                if propName == propLower or propName == propStripped:
                    valid = 1
                    propName = prop
                    break

        if not valid:
            return "Invalid prop name!"

        toon.d_setRightHand(propName)

        return "Prop attached to target's right hand."


class BothHandsProp(MagicWord):
    aliases = ["bothhands", "propbothhands"]
    desc = "Attaches a prop to both of the target's hands."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("prop", str, False, '')]

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 0:
            valid = False
            propName = PropGlobals.getPropNameCaseInsensitive(str(entry))
            if propName is not None:
                valid = True
            if not valid:
                for prop in [x[0] for x in ToontownGlobals.PropsBattle]:
                    propLower = prop.lower()
                    propStripped = propLower.replace(" ", "")
                    if propName == propLower or propName == propStripped:
                        valid = True
                        propName = prop
                        break
            return valid
        elif arg == 1:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                scale = float(entry)
                return 0.1 <= scale <= 5
            return False
        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        propName = args[0]

        if not propName:
            toon.d_setLeftHand(propName)
            toon.d_setRightHand(propName)
            return "Cleared both of the target's hands."

        valid = False
        propName = PropGlobals.getPropNameCaseInsensitive(propName)
        if propName is not None:
            valid = True

        # Incase it wasn't found in the regular props, it could be a battleprop
        if not valid:
            for prop in [x[0] for x in ToontownGlobals.PropsBattle]:
                propLower = prop.lower()
                propStripped = propLower.replace(" ", "")
                if propName == propLower or propName == propStripped:
                    valid = 1
                    propName = prop
                    break

        if not valid:
            return "Invalid prop name!"

        toon.d_setLeftHand(propName)
        toon.d_setRightHand(propName)

        return "Prop attached to both of the target's hands."


class SetHouse(MagicWord):
    aliases = ["house", "housetype", "sethousetype"]
    desc = "Sets the house of the target."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("type", int, False, 0)]

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg == 0:
            return ('0', 'Default'), ('1', 'Tiki'), ('2', 'Teepee'), ('3', 'Castle'), ('4', 'Cupcake'), ('5', 'Cabin')
        return None

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 0:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                type = int(entry)
                return 0 <= type <= 5
            return False

        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        type = args[0]

        if not 0 <= type <= 5:
            return "Invalid house type!"

        if toon.getHouseId() in simbase.air.doId2do:
            house = simbase.air.doId2do.get(toon.getHouseId())
            if house is None:
                return "House not generated! Target must visit their estate to generate their house."
            house.b_setHouseType(type)
            toon.b_setHouseType(type)
            return "{0}'s House type set to {1}.".format(toon.getName(), type)
        return "House not generated! Go to your estate to generate your house."


class SetHouseNameColor(MagicWord):
    aliases = ["housenametagcolor", "housenamecolor", "housecolorname"]
    desc = "Set the color of the target's house name color to the specified RGB value."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("r", int, False, 0),
                 ("g", int, False, 0),
                 ("b", int, False, 0)]

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg in [0, 1, 2]:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                color = int(entry)
                return 0 <= color <= 255
            return False

        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        r = args[0]
        g = args[1]
        b = args[2]

        if not all(0 <= x <= 255 for x in (r, g, b)):
            return "Color numbers must be in range 0-255!"

        if toon.getHouseId() in simbase.air.doId2do:
            house = simbase.air.doId2do.get(toon.getHouseId())
            if house is None:
                return "House not generated! Target must visit their estate to generate their house."
            house.b_setNameColor(r, g, b)
            return f'{toon.getName()}\'s house name color was set to {r}, {g}, {b}!'
        return "House not generated! Go to your estate to generate your house."


class GetZone(MagicWord):
    aliases = ["getzoneid", "zoneid"]
    desc = "Returns the target's zone ID."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    anyTarget = True

    def handleWord(self, invoker, avId, toon, *args):
        return "{}'s Zone ID is {}.".format(toon.getName(), str(toon.zoneId))


class Oboe(MagicWord):
    aliases = ["playoboe", "oboesfx", "sfxoboe", "oboesound", "playoboesfx", "playoboesound"]
    desc = "Plays an oboe sound effect for everyone nearby the target."
    cooldown = 5.0
    execLocation = MagicWordConfig.EXEC_LOC_SERVER

    def handleWord(self, invoker, avId, toon, *args):
        toon.d_generateOboeEffect()
        return "Played an oboe sound effect on {}.".format(toon.getName())


class ToggleCage(MagicWord):
    administrative = True
    aliases = ["cage", "setcage", "tooncage"]
    desc = "Toggles a lock-down on the target Toon."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    accessLevel = "MODERATOR"

    def handleWord(self, invoker, avId, toon, *args):
        if invoker == toon:
            return "You cannot toggle a Cage on yourself!"

        battleId = toon.getBattleId()
        if battleId:
            return "You cannot cage {} while they are in a cog battle!".format(toon.getName())
        exemption = toon.getExemption()
        if exemption == ToontownGlobals.LockedStateCagedExemption:
            return f"You cannot cage {toon.getName()} because they are locked with a cage exemption."

        state = toon.getLocked()
        if state:
            toon.b_setTempImmortalMode(0)
        else:
            toon.b_setTempImmortalMode(1)
        toon.b_setLocked(not state)
        toon.d_generateCage()
        return "Cage has been toggled for {}.".format(toon.getName())


class TransformDisney(MagicWord):
    aliases = ["transformchar", "setdisneyindex", "setcharindex", "disney", "char", "setchar"]
    desc = "Transforms the target into a Disney character."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("id", int, False, 0)]

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg == 0:
            return ((str(x), 'Toon' if x == 0 else TTLocalizer.charName2Id[x - 1]) for x in range(20))
        return None

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 0:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                index = int(entry)
                return 0 <= index <= 19
            return False 

        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        index = args[0]

        if not 0 <= index <= 19:
            return "Invalid character ID specified. Please specify a value between 0 and 19."

        toon.b_setCharIndex(index, 2)
        if index != 0:
            return 'Transformed {0} into {1}!'.format(toon.getName(), TTLocalizer.charName2Id[index - 1])
        else:
            return 'Transformed {} back into a Toon!'.format(toon.getName())


class TransformDoodle(MagicWord):
    aliases = ["setdoodleindex", "doodleindex", "doodle", "setdoodle"]
    desc = "Transforms the target into their Doodle."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    # TODO: in the future we might wanna consider some preselected doodles if we don't have one
    arguments = [("wantFluffy", bool, False, False)]

    def handleWord(self, invoker, avId, toon, *args):
        petName = "Fluffy"
        petDNA = [-1, 0, 0, -1, 4, 0, 0, 5, 1, 191, -263, 4.597, 109]
        wantFluffy = args[0]
        if wantFluffy:
            toon.b_setDoodleIndex(1, 2, petName, petDNA)
            return f'Transformed {toon.getName()} into {petName} the Doodle!'

        index = toon.getDoodleIndex()
        if index == 0:
            index = 1
        elif index == 1:
            index = 0

        if index == 0:
            toon.b_setDoodleIndex(index, 2, "", [])
            return f'Transformed {toon.getName()} back into a Toon!'

        petId = toon.getPetId()
        pet = simbase.air.doId2do.get(petId)
        if not pet:

            def handlePetDetails(dclass, fields):
                if dclass != simbase.air.dclassesByName['DistributedPetAI']:
                    return
                head = fields['setHead'][0]
                ears = fields['setEars'][0]
                nose = fields['setNose'][0]
                tail = fields['setTail'][0]
                body = fields['setBodyTexture'][0]
                color = fields['setColor'][0]
                colorScale = fields['setColorScale'][0]
                eyeColor = fields['setEyeColor'][0]
                gender = fields['setGender'][0]

                petDNA = [head, ears, nose, tail, body, color, colorScale, eyeColor, gender]
                petName = fields['setPetName'][0]
                toon.b_setDoodleIndex(index, 2, petName, petDNA)

            if not petId:
                toon.b_setDoodleIndex(index, 2, petName, petDNA)
                return f'Transformed {toon.getName()} into {petName} the Doodle!'

            simbase.air.dbInterface.queryObject(simbase.air.dbId, petId, handlePetDetails)
            return f'Transformed {toon.getName()} into a Doodle!'
        else:
            petDNA = pet.getDNA()
            petName = pet.getPetName()
            toon.b_setDoodleIndex(index, 2, petName, petDNA)
            return f'Transformed {toon.getName()} into a Doodle!'


class TransformGoon(MagicWord):
    aliases = ["setgoonindex", "goonindex", "goon", "setgoon"]
    desc = "Transforms the target into a Goon."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("id", int, False, 0)]

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg == 0:
            return ((str(x), GoonTypes[x]) for x in range(3))
        return None

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 0:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                index = int(entry)
                return 0 <= index <= 2
            return False 

        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        index = args[0]

        if not 0 <= index <= 2:
            return "Invalid Goon ID specified. Please specify a value between 0 and 2.".format(toon.getName())

        toon.b_setGoonIndex(index, 2)
        return f'Transformed {toon.getName()} into a {GoonTypes[index]}!'


class TransformProp(MagicWord):
    aliases = ["setpropindex", "propindex", "setprop"]
    desc = "Transforms the target into a Prop."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("propName", str, False, '')]

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 0:
            propNameArg = str(entry)
            if propNameArg == '':
                return True
            propName = PropGlobals.getPropNameCaseInsensitive(propNameArg)
            return propName is not None

        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        propNameArg = args[0]
        propName = PropGlobals.getPropNameCaseInsensitive(propNameArg)

        if propNameArg == '':
            toon.b_setPropIndex('', 2)
            return 'Transformed {} back into a Toon!'.format(toon.getName())

        if propName is not None:
            retMsg = 'Transformed {} into a Prop!'.format(toon.getName())
        else:
            return f"Invalid prop name ({propNameArg})!" \
                   f" Could not transform {toon.getName()} into a prop."
        toon.b_setPropIndex(propName, 2)
        return retMsg


class TransformBoss(MagicWord):
    aliases = ["setbossindex", "bossindex", "boss", "setboss"]
    desc = "Transforms the target into a Cog Boss."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("id", int, False, 0)]

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg == 0:
            return ((str(x), BossTypes[x]) for x in range(5))
        return None

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 0:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                index = int(entry)
                return 0 <= index <= 4
            return False

        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        index = args[0]

        if not 0 <= index <= 4:
            return "Invalid Cog Boss ID specified. Specify a value between 0 and 4."

        toon.b_setBossIndex(index, 2)
        return f'Transformed {toon.getName()} into a {BossTypes[index]}!'

class TransformFish(MagicWord):
    aliases = ["setfishindex", "fishindex", "fish"]
    desc = "Transforms the target into a Fish."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("id", int, False, 0)]

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg == 0:
            fishGenusNames = list(TTLocalizer.FishGenusNames.values())
            return ((str(x), 'Toon' if x == 0 else fishGenusNames[x - 1]) for x in range(len(fishGenusNames) + 1))
        return None

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 0:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                index = int(entry)
                return 0 <= index <= len(list(TTLocalizer.FishGenusNames.keys()))
            return False 

        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        index = args[0]

        fishGenusNames = list(TTLocalizer.FishGenusNames.values())
        if not 0 <= index <= len(fishGenusNames):
            return "Invalid Fish ID specified. Specify a value between 0 and 18."

        if index != 0:
            index *= 2

        toon.b_setFishIndex(index, 2)
        return f'Transformed {toon.getName()} into a {"Toon" if index == 0 else fishGenusNames[(index // 2) - 1]}!'

class TransformButterfly(MagicWord):
    aliases = ["setbutterflyindex", "butterflyindex", "butterfly", "setbutterfly"]
    desc = "Transforms the target into a Butterfly."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("id", int, False, 0), ("r", int, False, 0), ("g", int, False, 0), ("b", int, False, 0)]

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg == 0:
            return ((str(x), ButterflyTypes[x]) for x in range(6))
        return None

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 0:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                index = int(entry)
                return 0 <= index <= 6
            return False
        if arg in (1, 2, 3):
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                color = int(entry)
                return 0 <= color <= 255
            return False

        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        index = args[0]

        if not 0 <= index <= 6:
            return "Invalid Butterfly ID specified. Please specify a value between 0 and 6.".format(toon.getName())

        r = args[1]
        g = args[2]
        b = args[3]

        if not all(0 <= x <= 255 for x in (r, g, b)):
            return "Color numbers must be in range 0-255!"

        toon.b_setButterflyIndex(index, r, g, b, 2)
        return f'Transformed {toon.getName()} into a {ButterflyTypes[index]}!'

class TransformMisc(MagicWord):
    aliases = ["setmiscindex", "setmisc", "misc"]
    desc = "Transforms the target into a miscellaneous character."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("id", int, False, 0)]

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        return ((str(x), MiscTypes[x]) for x in range(6))

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 0:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                minimum = ToontownGlobals.TransformationMiscStatue
                maximum = ToontownGlobals.TransformationMiscMickey + 1
                index = int(entry)
                return minimum <= index <= maximum
            return False 

        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        index = args[0]

        minimum = ToontownGlobals.TransformationMiscStatue
        maximum = ToontownGlobals.TransformationMiscMickey + 1

        if not minimum <= index <= maximum:
            return "Invalid character ID specified. Please specify a value between {} and {}.".format(minimum, maximum)

        toon.b_setMiscIndex(index, 2)
        return f'Transformed {toon.getName()} into a {MiscTypes[index]}!'


class TransformStreetProp(MagicWord):
    aliases = ["transformstreet", "setstreetpropindex", "setstreetindex", "streetprop", "street", "setstreet",
               "setstreetprop"]
    desc = "Transforms the target into a street prop."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("id", int, False, 0)]

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg == 0:
            return ((str(x), StreetPropTypes[x]) for x in range(18))
        return None

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 0:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                index = int(entry)
                return 0 <= index <= 17
            return False

    def handleWord(self, invoker, avId, toon, *args):
        index = args[0]

        if not 0 <= index <= 17:
            return "Invalid character ID specified. Please specify a value between 0 and 17."

        toon.b_setStreetIndex(index, 2)
        return f'Transformed {toon.getName()} into a {StreetPropTypes[index]}!'


# TODO: validation: check rank on local avatar; target if it is near us
class SetAccessLevel(MagicWord):
    administrative = True
    aliases = ["accesslevel", "access", "setaccess"]
    desc = "Sets the target's Access Level."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("rank", int, False, 100)]
    affectRange = [MagicWordConfig.AFFECT_OTHER]
    accessLevel = "MODERATOR"

    def handleWord(self, invoker, avId, toon, *args):
        rank = args[0]

        max = min(invoker.getAccessLevel(), rank)
        if not -100 <= rank <= max:
            return "Can't set {0}'s Access Level to {1}! Specify a value between -100 and {2}.".format(toon.getName(),
                                                                                                       rank, max)

        if rank not in list(OTPGlobals.AccessLevelInt2Name.keys()):
            return "Invalid Access Level specified!"

        if invoker.getAccessLevel() == rank:
            return "You cannot set the target to your own Access Level!"

        rank = OTPGlobals.AccessLevelInt2Name.get(rank)
        toon.b_setAccessLevel(rank)
        return "Set {0}'s Access Level to {1}.".format(toon.getName(), rank)


class StartMaintenance(MagicWord):
    administrative = True
    aliases = ["update", "maintenance", "startupdate", "updatestart", "maintenancestart"]
    desc = "Sends a maintenance warning to the players."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("time", int, False, 300), ("type", int, False, 0)]
    accessLevel = "MODERATOR"

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg == 0:
            return ('60', '1 Minute (Minimum)'), ('120', '2 Minutes'), ('180', '3 Minutes'), ('240', '4 Minutes'), ('300', '5 Minutes'), \
                   ('360', '6 Minutes'), ('420', '7 Minutes'), ('480', '8 Minutes'), ('540', '9 Minutes'), ('600', '10 Minutes (Maximum)')
        elif arg == 1:
            return ('0', 'Update Reason'), ('1', 'Maintenance Reason')
        return None

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 0:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                seconds = int(entry)
                return 60 <= seconds <= 600
            return False 
        elif arg == 1:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                return int(entry) in [0, 1]
            return False

        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        time = args[0]
        type = args[1]

        if not 60 <= time <= 600:
            return "Can't announce maintenance with a time of {}! Specify a value between 60 and 600 seconds.".format(
                    time)

        if type not in [0, 1]:
            return "Could not announce maintenance with a type of {}! Specify a value between 0 and 1.".format(time)

        if type:
            reasonType = TTLocalizer.ServerShutdownUpdate
        else:
            reasonType = TTLocalizer.ServerShutdownMaintenance

        reason = TTLocalizer.ServerShutdownMessage % reasonType
        simbase.air.announceMaintenance(reason, reasonType, time)
        return "Announcing {0} with a time of {1} seconds and a reason of {2}".format(reasonType, time, reason)


class PhotosPath(MagicWord):
    # simple test to see if pyp can handle this
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT
    hidden = True

    def handleWord(self, invoker, avId, toon, *args):
        from winreg import ConnectRegistry, OpenKey, HKEY_CURRENT_USER, QueryValueEx
        reg = ConnectRegistry(None, HKEY_CURRENT_USER)
        akey = OpenKey(reg, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders")

        val = QueryValueEx(akey, "My Pictures")[0]
        return val


class Turbo(MagicWord):
    aliases = ["turbomode", "kartturbo", "turbokart"]
    desc = "Gives your kart a TURBO boost!"
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT

    def handleWord(self, invoker, avId, toon, *args):
        if not base.localAvatar.kart:
            return "You aren't in a Kart! Kart could not be set to TURBO mode."

        base.localAvatar.kart.startTurbo()
        return "Kart set to TURBO mode!"


class StartHoliday(MagicWord):
    aliases = ["holiday", "setholidaystart", "setstartholiday", "holidaystart"]
    desc = "Starts the specified holiday on the server."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("holidayId", int, True)]
    accessLevel = "MODERATOR"
    affectRange = [MagicWordConfig.AFFECT_SELF]

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg == 0:
            return [(str(x), HolidayNamesInCalendar.get(x, (None,))[0]) for x in Holidays]

    def handleWord(self, invoker, avId, toon, *args):
        holidayId = args[0]

        if not hasattr(self.air, 'holidayManager'):
            return "Holiday manager isn't generated in this AI.  Holiday not started."
        elif self.air.holidayManager.isHolidayRunning(holidayId):
            return 'Holiday {} is already running!'.format(holidayId)
        elif not self.air.holidayManager.isValidHoliday(holidayId):
            return 'Holiday {} is not a valid holiday!'.format(holidayId)

        self.air.holidayManager.startHoliday(holidayId)
        return 'Holiday {} has started!'.format(holidayId)


class GetCurrentHolidays(MagicWord):
    aliases = ["currentholidays", "curholidays", "getcurholidays", "listholidays", "holidays"]
    desc = "Lists all currently running holidays."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    affectRange = [MagicWordConfig.AFFECT_SELF]

    def handleWord(self, invoker, avId, toon, *args):
        if not hasattr(self.air, 'holidayManager'):
            return "Holiday manager isn't generated on this server.  Could not list running Holidays."
        curHolidays = list(self.air.holidayManager.currentHolidays.keys())
        if len(curHolidays) == 0:
            return 'No Holidays are running.'
        return f'These Holidays are running: {curHolidays}'


class EndHoliday(MagicWord):
    aliases = ["setholidayend", "setendholiday", "holidayend", "stopholiday", "holidaystop"]
    desc = "Ends the specified holiday currently running on the server."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("holidayId", int, True)]
    accessLevel = "MODERATOR"
    affectRange = [MagicWordConfig.AFFECT_SELF]

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg == 0:
            return [(str(x), HolidayNamesInCalendar.get(x, (None,))[0]) for x in Holidays if base.cr.newsManager.isHolidayRunning(x)]

    def handleWord(self, invoker, avId, toon, *args):
        holidayId = args[0]

        if not hasattr(self.air, 'holidayManager'):
            return 'Holiday manager isn\'t generated in this AI.  Holiday not ended.'
        elif not self.air.holidayManager.isValidHoliday(holidayId):
            return 'Holiday {} is not a valid holiday!'.format(holidayId)
        elif not self.air.holidayManager.isHolidayRunning(holidayId):
            return 'Holiday {} isn\'t currently active!'.format(holidayId)

        self.air.holidayManager.endHoliday(holidayId)
        return 'Holiday {} has been ended.'.format(holidayId)


class ToggleRougesGallery(MagicWord):
    aliases = ["roguesgallery", "togglerogues", "rogues", "togglegallery", "gallery"]
    desc = "Toggles the Rogues Gallery page in your Shticker Book."
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT

    def handleWord(self, invoker, avId, toon, *args):
        if base.localAvatar.roguesPage:
            return "Rogues Gallery already loaded."

        if base.localAvatar.cogRadar != [1, 1, 1, 1]:
            return "You must finish your Cog Radar before toggling the Rogues Gallery."

        base.localAvatar.addRoguesPage()
        return "Loaded the Rogues Gallery."


class PrintChildren(MagicWord):
    aliases = ["children", "getchildren"]
    desc = "Prints all of render's children to the client log."
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT
    arguments = [("type", int, False, 0), ("mode", int, False, 0)]

    def handleWord(self, invoker, avId, toon, *args):
        type = args[0]
        mode = args[1]

        if not type:
            node = render
        else:
            node = render2d

        if not mode:
            print(node.getChildren())
        elif mode == 2:
            for child in node.getChildren():
                for secondaryChild in child.getChildren():
                    print(secondaryChild.getChildren())
        elif mode == 3:
            for child in node.getChildren():
                for secondaryChild in child.getChildren():
                    for thirdChild in secondaryChild.getChildren():
                        print(thirdChild.getChildren())
        elif mode == 4:
            for child in node.getChildren():
                for secondaryChild in child.getChildren():
                    for thirdChild in secondaryChild.getChildren():
                        for fourthChild in thirdChild.getChildren():
                            print(fourthChild.getChildren())
        elif mode == 5:
            for child in node.getChildren():
                for secondaryChild in child.getChildren():
                    for thirdChild in secondaryChild.getChildren():
                        for fourthChild in thirdChild.getChildren():
                            for fifthChild in fourthChild.getChildren():
                                print(fifthChild.getChildren())
        else:
            for child in node.getChildren():
                print(child.getChildren())
        return "Printed children of render to the client log file."


class SetSillyMeterPhase(MagicWord):
    aliases = ["setsillymeter", "setsilly", "sillymeter", "sillymeterphase", "sillyphase", "phase", "silly"]
    desc = "Sets the phase of the Silly Meter if the Silly Meter holiday is active."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("phase", int, False, 0)]

    def handleWord(self, invoker, avId, toon, *args):
        phase = args[0]

        if not hasattr(simbase.air, 'holidayManager') or not simbase.air.holidayManager or \
                not simbase.air.holidayManager.isHolidayRunning(ToontownGlobals.SILLYMETER_HOLIDAY):
            return "Silly Meter not active! Could not set phase."

        maxPhase = len(simbase.air.holidayManager.currentHolidays[ToontownGlobals.SILLYMETER_HOLIDAY].dates) - 2

        if not 0 <= phase < maxPhase:
            return "Can't set the Silly Meter to phase {0}! Specify a value between 0 and {1}.".format(phase,
                                                                                                       maxPhase - 1)

        self.air.SillyMeterMgr.b_setCurPhase(phase)
        return "Silly Meter phase set to {}!".format(phase)


class StartToonParty(MagicWord):
    aliases = ['toonparty']
    desc = "Starts a predefined Toon party, free of charge."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    accessLevel = "MODERATOR"
    affectRange = [MagicWordConfig.AFFECT_SELF]

    def handleWord(self, invoker, avId, toon, *args):
        if not invoker.canPlanParty():
            return "You're already hosting a Toon party!  You can only host one at a time."

        # Get ASAP time.
        from datetime import timedelta
        curServerTime = simbase.air.toontownTimeManager.getCurServerDateTime()
        startTime = curServerTime
        startTime = startTime.replace(startTime.year, startTime.month, startTime.day, startTime.hour, startTime.minute,
                                      second = 0, microsecond = 0)
        minute = curServerTime.minute
        remainder = minute % PartyGlobals.PartyPlannerAsapMinuteRounding
        if remainder:
            startTime += timedelta(minutes = PartyGlobals.PartyPlannerAsapMinuteRounding - remainder)
        else:
            startTime += timedelta(minutes = PartyGlobals.PartyPlannerAsapMinuteRounding)
        endTime = startTime + timedelta(hours = PartyGlobals.DefaultPartyDuration)

        isPrivate = 0
        inviteTheme = PartyGlobals.InviteTheme.GenericMale
        activities = [(1, 7, 14, 12), (1, 8, 14, 12), (1, 9, 14, 12), (1, 10, 14, 12), (5, 9, 11, 0), (2, 4, 10, 6),
                      (10, 15, 7, 18), (6, 3, 7, 6), (7, 8, 7, 0), (3, 5, 4, 6), (9, 12, 2, 18)]
        decorations = [(28, 6, 14, 12)]

        invitees = []
        for friend in invoker.friendsList:
            invitees.append(friend[0])

        simbase.air.partyManager.addPartyRequest(invoker.doId, startTime.strftime('%Y-%m-%d %H:%M:%S'),
                                                 endTime.strftime('%Y-%m-%d %H:%M:%S'), isPrivate, inviteTheme,
                                                 activities, decorations, invitees, free = True)
        return "Toon Party requested."


class PhotoShoot(MagicWord):
    aliases = ["photomode", "photo"]
    desc = "Forces Toons to co-operate better for screenshot taking."
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT

    def handleWord(self, invoker, avId, toon, *args):
        from toontown.toon.DistributedToon import DistributedToon

        for do in self.cr.doId2do.values():
            if isinstance(do, DistributedToon):
                do.stopLookAroundNow()
                do.stopBlink()

        return "Photo Shoot Mode Enabled!"


class RandomDNA(MagicWord):
    desc = "Randomizes the target's DNA."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER

    def handleWord(self, invoker, avId, toon, *args):
        try:
            seed = toon.getDoId() + int(round(time.time() * random.randrange(1, 100)))
            randomDNA = ToonDNA.ToonDNA()
            randomDNA.newToonRandom(seed, random.choice(('m', 'f')), stage = ToonDNA.MAGIC_WORD)

            toon.b_setDNAString(randomDNA.makeNetString())
            return "Randomized {}'s DNA successfully.".format(toon.getName())
        except:
            print("MagicWordIndex: RandomDNA Failed!")
            return "RandomDNA failed to execute. Please contact a developer."


class RandomName(MagicWord):
    desc = "Randomizes the target's Name."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER

    def handleWord(self, invoker, avId, toon, *args):
        oldName = toon.getName()

        namegen = NameGenerator.NameGenerator()
        if toon.getStyle().gender == 'm':
            boy = 1
            girl = 0
        else:
            boy = 0
            girl = 1
        toon.b_setName(namegen.randomNameMoreinfo(boy = boy, girl = girl)[-1])
        return "Randomized {}'s name successfully.".format(oldName)


class SetZone(MagicWord):
    desc = "Sets your zone."
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT
    arguments = [("zone", int, True)]

    def handleWord(self, invoker, avId, toon, *args):
        zoneId = args[0]

        if zoneId == 1836:
            return "Gyro's Lighthouse? Where's that?"

        if not ToontownGlobals.DonaldsDock <= zoneId <= ToontownGlobals.DynamicZonesEnd:
            return "Can't set your Zone ID to {0}! Specify a value between {1} and {2}".format(zoneId,
                                                                                               ToontownGlobals.DonaldsDock,
                                                                                               ToontownGlobals.DynamicZonesEnd)

        base.cr.sendSetZoneMsg(zoneId, [zoneId])
        return "Set your zone to {}".format(zoneId)


class Rewards(MagicWord):
    aliases = ["goodrewards", "goodsos"]
    desc = "Gives the target all of the best Boss rewards."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER

    def handleWord(self, invoker, avId, toon, *args):
        sosIds = [4125, 2003, 1116, 2311, 4119, 4219, 4115, 3112, 1323, 2308, 2011, 2001, 2132, 2121, 5124, 4230]
        for id in sosIds:
            toon.NPCFriendsDict[id] = 100
        toon.d_setNPCFriendsDict(toon.NPCFriendsDict)
        toon.restockAllResistanceMessages(999)
        cogCount = []
        for deptIndex in range(4):
            for cogIndex in range(8):
                cogCount.append(CogPageGlobals.COG_QUOTAS[1][cogIndex])
        toon.b_setCogCount(cogCount)
        toon.b_setCogStatus(([CogPageGlobals.COG_COMPLETE2] * 8) * 4)
        toon.restockAllCogSummons()
        toon.b_setPinkSlips(255)
        return "Restocked {}'s rewards.".format(toon.getName())


class OpenHallway(MagicWord):
    aliases = ["opensesame", "panel"]
    desc = "Opens up the hidden hallway in the Toon Hall."
    advancedDesc = "This Magic Word will permanently open the hidden wall panel behind the anvil in Toon Hall. " \
                   "This reveals a staircase that leads to a secret room in the Toon Hall."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    affectRange = [MagicWordConfig.AFFECT_SELF]

    def handleWord(self, invoker, avId, toon, *args):
        from toontown.building.DistributedToonHallInteriorAI import DistributedToonHallInteriorAI
        toonHall = None
        for do in list(simbase.air.doId2do.values()):
            if isinstance(do, DistributedToonHallInteriorAI):
                toonHall = do
                break

        if toonHall:
            toonHall.openHallway()
            return "The Toon Hall Hallway is now open."

        return "Toon Hall not generated."


class PieBlitz(MagicWord):
    aliases = ["blitz"]
    desc = "Starts a Toon vs Toon pie-throwing game."
    advancedDesc = "This Magic Word will begin a zone-wide event called a Pie Blitz. When a Pie Blitz is active, " \
                   "all Toons will be given some pies they can use to throw at other Toons. If you get hit by a pie, " \
                   "you will take damage and are prone to going sad. Toons who were in Immortal Mode before the " \
                   "start of the Pie Blitz will be unable to participate, nor will they be able to leave Immortal " \
                   "Mode until the Blitz is over. You can specify the amount of damage Toons can dish out per pie, " \
                   "ranging from 1 to {} laff points. You can also specify the type of pies given to the " \
                   "participants, ranging from pie IDs 0 to 8. Finally, you can specify how long the Pie Blitz " \
                   "should last for, ranging from {} to {} seconds.".format(ToontownGlobals.MaxHpLimit,
                                                                            ToontownGlobals.DefaultPieBlitzDuration,
                                                                            ToontownGlobals.MaxPieBlitzDuration)
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("damage", int, False, ToontownGlobals.DefaultPieBlitzDamage),
                 ("type", int, False, ToontownGlobals.DefaultPieBlitzPie),
                 ("duration", int, False, ToontownGlobals.DefaultPieBlitzDuration)]
    accessLevel = "MODERATOR"
    affectRange = [MagicWordConfig.AFFECT_SELF]

    def handleWord(self, invoker, avId, toon, *args):
        damage = args[0]
        pieType = args[1]
        duration = args[2]

        if ZoneUtil.isDynamicZone(invoker.zoneId):
            return 'You cannot start a Pie Blitz in a dynamic zone.'

        mgr = self.air.microGameMgr
        if not mgr:
            return 'No Micro Game Manager found!'

        microGame, isActive = mgr.getActiveMicroGame(invoker.zoneId)
        if isActive:
            return "Cannot start a Pie Blitz while %s is running! Please wait until it is over." % \
                   microGame.getName()

        if not 1 <= damage <= ToontownGlobals.MaxHpLimit:
            return "Invalid pie damage specified! Specify a value between 1 and %d." % ToontownGlobals.MaxHpLimit

        if not 0 <= pieType <= 8:
            return "Invalid pie type specified! Specify a value between 0 and 8."

        if not ToontownGlobals.DefaultPieBlitzDuration <= duration <= ToontownGlobals.MaxPieBlitzDuration:
            return "Invalid duration specified! Specify a value between %d and %d seconds." \
                   % (ToontownGlobals.DefaultPieBlitzDuration, ToontownGlobals.MaxPieBlitzDuration)

        game = mgr.startMicroGame(invoker.zoneId, ToontownGlobals.MicroGameTypePieBlitz)

        game.setDuration(duration)
        game.setDamage(damage)
        game.setPieType(pieType)
        game.b_setState('Start')
        return "Pie Blitz started!"


class CreateParty(MagicWord):
    desc = "Creates a party for a mini-game or boss battle."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("mode", int, False, ToontownGlobals.BossPartySellbotBoss)]
    affectRange = [MagicWordConfig.AFFECT_SELF]
    aliases = ['party', 'bossparty']

    def handleWord(self, invoker, avId, toon, *args):
        boss = args[0]

        if not hasattr(self.air, 'bossPartyMgr'):
            return "No Party Manager found!"
        mgr = self.air.bossPartyMgr

        microGameMgr = self.air.microGameMgr
        if microGameMgr:
            microGame, isActive = microGameMgr.getActiveMicroGame(toon.zoneId)
            if isActive:
                return "Cannot start a party while %s is running! Please wait until it is over." % \
                       microGame.getName()

        if not mgr.isValidBossParty(boss):
            return "Invalid mode index specified! Specify a value between {} and {}.".format(
                ToontownGlobals.BossPartySellbotBoss, ToontownGlobals.BossPartyBossbotBossHardcore)

        if mgr.isActive():
            return "A party is already active!"

        if ZoneUtil.isDynamicZone(invoker.zoneId):
            return "Cannot start a party while in a dynamic zone."

        if not mgr.hasPromotion(invoker, boss):
            return "You do not have a promotion for the specified party!"

        if boss in mgr.bossPartyComingSoon:
            return "This feature is not available in this beta."

        promotions = []
        from otp.avatar.DistributedPlayerAI import DistributedPlayerAI
        for do in list(self.air.doId2do.values()):
            if isinstance(do, DistributedPlayerAI) and do.isPlayerControlled():
                if mgr.hasPromotion(do, boss):
                    promotions.append(do)

        mgr.b_setBossCog(boss)
        mgr.b_setHoster(invoker.getDoId())
        mgr.b_setState('Start')
        return "Party started!"


class HideAndSeek(MagicWord):
    aliases = ["hideseek", "hide-seek"]
    desc = "Starts a hide and seek game."
    advancedDesc = "This Magic Word will begin a zone-wide game of Hide and Seek. When Hide and Seek is active, " \
                   "all Toons must hide from the seeker, the invoker of this magic word. All hiders will be given a " \
                   "short time to hide before the seeker can find them. If you are found before time runs out, " \
                   "you're out. If the seeker doesn't find every Toon hiding before time runs out, the hiders win. " \
                   "If all hiders are found, the seeker wins. All Toons who join the server after the game has " \
                   "started will become hiders. If the seeker leaves, a hider will be randomly selected to be a " \
                   "seeker. If all hiders are gone, the game is over. You can specify the amount of time for both " \
                   "the hiding and seeking phases, ranging from {} to {} seconds for hiding and {} to {} seconds for " \
                   "seeking.".format(ToontownGlobals.DefaultHideAndSeekHidingDuration,
                                     ToontownGlobals.MaxHideAndSeekHidingDuration,
                                     ToontownGlobals.DefaultHideAndSeekSeekingDuration,
                                     ToontownGlobals.MaxHideAndSeekSeekingDuration)
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("hideduration", int, False, ToontownGlobals.DefaultHideAndSeekHidingDuration),
                 ("seekduration", int, False, ToontownGlobals.DefaultHideAndSeekSeekingDuration)]
    accessLevel = "MODERATOR"
    affectRange = [MagicWordConfig.AFFECT_SELF, MagicWordConfig.AFFECT_OTHER]

    def handleWord(self, invoker, avId, toon, *args):
        hidedur = args[0]
        seekdur = args[1]

        if ZoneUtil.isDynamicZone(toon.zoneId):
            return 'You cannot start Hide and Seek if the seeker is in a dynamic zone.'

        mgr = self.air.microGameMgr
        if not mgr:
            return 'No Micro Game Manager found!'

        microGame, isActive = mgr.getActiveMicroGame(toon.zoneId)
        if isActive:
            return "Cannot start Hide and Seek while %s is running! Please wait until it is over." % \
                   microGame.getName()

        if not ToontownGlobals.DefaultHideAndSeekHidingDuration <= hidedur <= \
               ToontownGlobals.MaxHideAndSeekHidingDuration:
            return "Invalid hiding duration specified! Specify a value between %d and %d seconds." \
                   % (ToontownGlobals.DefaultHideAndSeekHidingDuration, ToontownGlobals.MaxHideAndSeekHidingDuration)

        if not ToontownGlobals.DefaultHideAndSeekSeekingDuration <= seekdur <= \
               ToontownGlobals.MaxHideAndSeekSeekingDuration:
            return "Invalid seeking duration specified! Specify a value between %d and %d seconds." \
                   % (ToontownGlobals.DefaultHideAndSeekSeekingDuration, ToontownGlobals.MaxHideAndSeekSeekingDuration)

        game = mgr.startMicroGame(invoker.zoneId, ToontownGlobals.MicroGameTypeHideAndSeek)
        game.setDuration(hidedur)
        game.setSeekingDuration(seekdur)
        game.b_setSeeker(avId)
        game.b_setState('Start')
        return "Hide and Seek started!"


class EndMicroGame(MagicWord):
    aliases = ['abortmicrogame', 'microgameend', 'microgameabort']
    desc = 'Ends the micro game in the current zone if there is one.'
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    accessLevel = "MODERATOR"
    affectRange = [MagicWordConfig.AFFECT_SELF]

    def handleWord(self, invoker, avId, toon, *args):
        mgr = self.air.microGameMgr
        if not mgr:
            return 'No Micro Game Manager found!'

        microGame, isActive = mgr.getActiveMicroGame(ZoneUtil.getCanonicalBranchZone(toon.zoneId))
        if isActive:
            microGame.b_setState('Done')
            microGame.requestDelete()
            return "Ended %s." % microGame.getName()
        return 'No micro games are active here.'


class GoHome(MagicWord):
    aliases = ["home", "gohouse", "goestate", "estate"]
    desc = "Teleports you to your Estate."
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT

    def handleWord(self, invoker, avId, toon, *args):
        place = base.cr.playGame.getPlace()

        if not place:
            return "Could not go to your estate right now!"

        place.goHomeNow(base.localAvatar.lastHood)
        return "Heading to your Estate!"


class TogglePetLeash(MagicWord):
    aliases = ['leash', 'petleash', 'doodleleash', 'walkdoodle', 'walkpet']
    desc = 'Toggles a mode to make your Doodle follow you throughout Toontown.'
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    affectRange = [MagicWordConfig.AFFECT_SELF]

    def handleWord(self, invoker, avId, toon, *args):
        if simbase.wantPets:
            petId = invoker.getPetId()
            if petId:
                def generated(pet):
                    pet.toggleLeash(avId)

                if petId not in self.air.doId2do:
                    self.air.sendActivate(petId, self.air.districtId, toon.zoneId)
                    self.air.acceptOnce('generate-%d' % petId, generated)
                else:
                    generated(self.air.doId2do[petId])
            else:
                return "You don't own a doodle."
        else:
            return 'Doodles are not enabled on this server.'


class SetBackgroundColor(MagicWord):
    aliases = ['backgroundcolor', 'background', 'bgcolor', 'void']
    desc = "Changes your background color, or restores it."
    advancedDesc = "This Magic Word will allow you to do one of the following: restore old background color, " \
                   "set a new (temporary) background color, or set the background color to a predefined color " \
                   "(currently, only the green background color, also temporarily). To use any of these, you " \
                   "must use one of the following subcommands: set, restore, green. The set subcommand allows " \
                   "you to specify RGBA values, where the default is 0 (255 for alpha), and each value must be in the" \
                   " range of 0 and 255 (including 255 itself). The green subcommand sets your background color to" \
                   " the green background color that you used to see in your house (due to a bug with Panda3D). The " \
                   "restore subcommand simply restores the background color to the original value the game set for " \
                   "the" \
                   " area. "
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT
    arguments = [
        ("command", str, True),
        ("r", float, False, 0.0),
        ("g", float, False, 0.0),
        ("b", float, False, 0.0),
        ("a", float, False, 255.0)
    ]
    __legalCommands = ("set", "restore", "green")

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg == 0:
            return (('set', 'Sets the background color'),
                    ('restore', 'Restores the default background color'),
                    ('green', 'Sets the color to a green screen color')
                    )
        return None

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg > 0:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                color = float(entry)
                return 0.0 <= color <= 255.0
            return False 

        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        command = args[0].lower()
        if command not in self.__legalCommands:
            return f"Commands must be one of the following: {', '.join(self.__legalCommands)}"
        if command == "restore":
            base.restoreBackgroundColor()
            return "Restored your background color."
        elif command == "set":
            if not all(0.0 <= x <= 255.0 for x in (args[1], args[2], args[3], args[4])):
                return "Color numbers must be in range 0-255!"
            r = args[1] / 255
            g = args[2] / 255
            b = args[3] / 255
            a = args[4] / 255
            base.setBackgroundColor(r = r, g = g, b = b, a = a, temporary = True)
            # should I format this better?
            return f"Set your background color to ({r:0.2f}, {g:0.2f}, {b:0.2f}, {a:0.2f})."
        elif command == "green":
            base.setBackgroundColor(r = 0.09, g = 0.55, b = 0.21, a = 1.0, temporary = True)
            return "Set your background color to green."


class ToggleShadows(MagicWord):
    aliases = ['toggleshadow', 'shadow', 'shadows']
    desc = "Toggles the shadows of all nearby Toons."
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT

    def handleWord(self, invoker, avId, toon, *args):
        from toontown.toon.DistributedToon import DistributedToon

        shadowJoint = base.localAvatar.getShadowJoint()
        if shadowJoint is None or shadowJoint.isEmpty():
            return "Could not find your Toon's shadow for reference!"

        # We do this to make sure all the shadows are in sync with your Toon's shadow
        # It would be bad news if a bunch of Toons walked in on your scene in the middle of it
        # Then you'd be dealing with half shadows, have no shadows, and this Magic Word couldn't fix it
        state = False
        if shadowJoint.isHidden():
            state = True

        for do in self.cr.doId2do.values():
            if isinstance(do, DistributedToon):
                shadowJoint = do.getShadowJoint()
                if shadowJoint is None or shadowJoint.isEmpty():
                    continue

                if state:
                    shadowJoint.show()
                else:
                    shadowJoint.hide()

        return "All nearby Toon shadows have been toggled!"


class ToggleClassicFishing(MagicWord):
    aliases = ['classicfishing']
    desc = "Toggles the Classic Fishing Docks in Toontown Central."
    accessLevel = "MODERATOR"
    execLocation = MagicWordConfig.EXEC_LOC_SERVER

    def handleWord(self, invoker, avId, toon, *args):
        from toontown.classicfishing.DistributedClassicFishingSpotAI import DistributedClassicFishingSpotAI

        docks = []
        availableDocks = []
        for do in list(self.air.doId2do.values()):
            if isinstance(do, DistributedClassicFishingSpotAI):
                docks.append(do)
                if not do.avId:
                    availableDocks.append(do)

        if len(docks) < 2:
            return 'Classic Fishing Docks are currently disabled!'

        if len(availableDocks) < 2:
            return 'There are currently Toons on the Classic Fishing Docks!'

        for dock in docks:
            dock.toggleFishingSpot(not dock.hidden)

        return 'Successfully toggled the Classic Fishing Docks!'


class ToggleEditor(MagicWord):
    hidden = True
    aliases = ["edit", "ingameedit", "ingameeditor", "editor", "toggleedit", "toggleingameedit", "toggleingameeditor"]
    desc = "Starts the in-game editor to edit cog facilities."
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT
    accessLevel = 'TTOFF_DEVELOPER'
    affectRange = [MagicWordConfig.AFFECT_SELF]

    def handleWord(self, invoker, avId, toon, *args):
        if not __dev__:
            return 'Client not running in dev mode. Set want-dev to true in your config file.'
        from otp.level import EditorGlobals
        level = bboard.get(EditorGlobals.EditTargetPostName)
        if not level:
            return 'No level available for editing.'
        from toontown.coghq import DistributedInGameEditor
        EditorGlobals.assertReadyToEdit()
        editUsername = EditorGlobals.getEditUsername()
        editors = base.cr.doFindAll('DistributedInGameEditor')
        for e in editors:
            if isinstance(e, DistributedInGameEditor.DistributedInGameEditor):
                if e.getLevelDoId() == level.doId:
                    if e.editorIsLocalToon() or e.getEditUsername() == editUsername:
                        return "You're already editing this level."

        level.d_startEditor(invoker.doId, editUsername)


class SetNextFish(MagicWord):
    aliases = ['gibfish', 'setfish', 'nextfish', 'requestfish', 'requestnextfish']
    desc = 'Sets your next caught fish to a specific species.'
    affectRange = [MagicWordConfig.AFFECT_SELF]
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("fish", str, True)]

    def handleWord(self, invoker, avId, toon, *args):
        fish = args[0]
        fish = fish.lower()
        fish = fish.replace(" ", "")

        genus = None
        species = None

        allFish = TTLocalizer.FishSpeciesNames
        for g in list(allFish.keys()):
            for s in allFish[g]:
                if s.replace(" ", "").lower() == fish:
                    genus, species = g, allFish[g].index(s)
                    break

        if (genus is None) or (species is None):
            return 'Invalid fish name %s!' % fish

        if self.air.fishManager:
            self.air.fishManager.requestedFish[self.invokerId] = (genus, species)
            return 'Set next fish to %s.' % fish
        return 'Fish Manager is not generated!'


class ToggleTrolleyHop(MagicWord):
    aliases = ['trolleyhop', 'toggletrolleyhopoff', 'trolleyhopoff']
    desc = 'Toggles the ability to hop off the Trolley you are currently on.'
    affectRange = [MagicWordConfig.AFFECT_SELF]
    accessLevel = "MODERATOR"
    execLocation = MagicWordConfig.EXEC_LOC_SERVER

    def handleWord(self, invoker, avId, toon, *args):
        from toontown.safezone.DistributedTrolleyAI import DistributedTrolleyAI

        for do in list(self.air.doId2do.values()):
            if isinstance(do, DistributedTrolleyAI):
                invokerId = invoker.getDoId()
                if invokerId in do.seats:
                    do.setDisabled(not do.getDisabled())
                    state = "disabled!" if do.getDisabled() else "enabled!"
                    return "Toggled hopping is now " + state

        return "You are not currently on a Trolley!"


class GeneratePixelArt(MagicWord):
    aliases = ["pixelart", "pixel"]
    desc = "Uses the Prop Generator to generate pixel art from the specified image contained within the props folder."
    accessLevel = "BUILDER"
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT
    arguments = [("filePath", str, True)]

    def handleWord(self, invoker, avId, toon, *args):
        filePath = args[0]

        if not (filePath.endswith('.jpg') or filePath.endswith('.png')):
            return "Specified filepath must end with jpg or png!"

        if not os.path.exists('props/'):
            os.mkdir('props/')

        if not os.path.isfile('props/' + filePath):
            return "Image not found! Please make sure your image is located in the props folder."

        if not hasattr(self.cr, 'propGenerator') or not self.cr.propGenerator:
            return "There is no Prop Generator in this zone!"

        base.cr.propGenerator.generatePixelArt('props/' + filePath)
        return "Pixel art generated."


class ShowPaths(MagicWord):
    aliases = ['paths']
    desc = 'Shows/hides suit paths or Disney character paths, depending on the context.'
    affectRange = [MagicWordConfig.AFFECT_SELF]
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT

    def handleWord(self, invoker, avId, toon, *args):
        from toontown.suit import DistributedSuitPlanner

        showingPaths = 0

        place = base.cr.playGame.getPlace()
        if hasattr(place, 'showPaths'):
            if place.pathsShown:
                place.hidePaths()
                showingPaths = 1
            else:
                place.showPaths()
                showingPaths = 2

        for obj in list(self.cr.doId2do.values()):
            if isinstance(obj, DistributedSuitPlanner.DistributedSuitPlanner):
                if obj.pathViz:
                    obj.hidePaths()
                    showingPaths = 1
                else:
                    obj.showPaths()
                    showingPaths = 2

        if showingPaths == 1:
            return 'Paths are no longer being shown.'
        elif showingPaths == 2:
            return 'Paths are now being shown.'
        return 'No paths found.'


class GetMagicWordCount(MagicWord):
    aliases = ["magicwordcount", "magicwords", "wordcount"]
    desc = "Gets the amount of Magic Words used on the server since boot."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    affectRange = [MagicWordConfig.AFFECT_SELF]

    def handleWord(self, invoker, avId, toon, *args):
        if not ServerSettings.LogMagicWords.get():
            return "Magic Word logging is not enabled on this server!"

        words = self.air.magicWordManager.getLoggedWords()

        if words == 0:
            return "1 Magic Word has been used on this server since boot, and this is it!"
        else:
            return "{:,} Magic Words have been used on this server since boot.".format(words + 1)


class CloneDNA(MagicWord):
    aliases = ["dnaclone"]
    desc = "Makes the invoker appear as the target."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    affectRange = [MagicWordConfig.AFFECT_OTHER]
    anyTarget = True

    def handleWord(self, invoker, avId, toon, *args):
        dna = ToonDNA.ToonDNA()
        dna.makeFromNetString(toon.getDNAString())

        invoker.b_setDNAString(dna.makeNetString())
        return "Successfully cloned {}'s DNA!".format(toon.getName())


class CloneAccessories(MagicWord):
    aliases = ["accessoriesclone"]
    desc = "Gives the invoker the target's accessories."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    affectRange = [MagicWordConfig.AFFECT_OTHER]
    anyTarget = True

    def handleWord(self, invoker, avId, toon, *args):
        hat = toon.getHat()
        glasses = toon.getGlasses()
        backpack = toon.getBackpack()
        shoes = toon.getShoes()

        invoker.b_setHat(*hat)
        invoker.b_setGlasses(*glasses)
        invoker.b_setBackpack(*backpack)
        invoker.b_setShoes(*shoes)
        self.air.updateOnlineAvatar(invoker)
        return "Successfully cloned {}'s accessories!".format(toon.getName())


class CloneToon(MagicWord):
    aliases = ["clone"]
    desc = "Makes the invoker appear completely as the target."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    affectRange = [MagicWordConfig.AFFECT_OTHER]
    anyTarget = True

    def handleWord(self, invoker, avId, toon, *args):
        dna = ToonDNA.ToonDNA()
        dna.makeFromNetString(toon.getDNAString())

        invoker.b_setDNAString(dna.makeNetString())

        hat = toon.getHat()
        glasses = toon.getGlasses()
        backpack = toon.getBackpack()
        shoes = toon.getShoes()

        invoker.b_setHat(*hat)
        invoker.b_setGlasses(*glasses)
        invoker.b_setBackpack(*backpack)
        invoker.b_setShoes(*shoes)
        self.air.updateOnlineAvatar(invoker)
        return "Successfully cloned {}'s Toon!".format(toon.getName())


class ReloadFilters(MagicWord):
    aliases = ['reloadshaders', 'reload']
    desc = 'Reloads all filters'
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT

    def handleWord(self, invoker, avId, toon, *args):
        if FilterManager.activeFilter:
            FilterManager.activeFilter.deactivate()
        FilterManager.searchForFilters()
        return "Filters reloaded!"


class Filter(MagicWord):
    aliases = ['shader', 'overlay']
    desc = 'Activate a render filter'
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT
    arguments = [("filter", str, False, 'clear'), ("affect ui", bool, False, True)]

    def handleWord(self, invoker, avId, toon, *args):
        filterEffect = args[0].lower()
        affectA2d = args[1]

        if FilterManager.filterLocked:
            return "You cannot change filters at this time!"

        # Fetch the filter from the identifier
        _filter = FilterManager.findFilter(filterEffect)
        if _filter:
            _filter.activate(affectA2d)
            return f"Activated {_filter.displayName} filter!"

        elif filterEffect in ['off', 'none', 'disable', 'clear']:
            if FilterManager.activeFilter:
                FilterManager.activeFilter.deactivate()
            return "Filters disabled!"

        else:
            return "Unknown filter specified."


class GrabTreasures(MagicWord):
    aliases = ['gettreasures', 'treasures', 'eattreasures']
    desc = 'Grab every treasure in the area.'
    advancedDesc = 'This will only grab normal healing treasures. ' \
                   'This means presents and tag game treasures cannot be grabbed. ' \
                   'Also, C.F.O. treasures cannot be grabbed as that discourages teamwork.'
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT
    affectRange = [MagicWordConfig.AFFECT_SELF]

    def handleWord(self, invoker, avId, toon, *args):
        treasures = base.cr.doFindAllInstances(DistributedSZTreasure.DistributedSZTreasure)
        treasureGrabCount = 0

        if not len(treasures):
            return 'No treasures were found in the current area.'
        elif toon.getHp() == toon.getMaxHp():
            return 'Your laff is full.'

        for treasure in treasures:
            if treasure.__class__.__name__ == 'DistributedCashbotBossTreasure':
                continue

            treasure.d_requestGrab()
            treasureGrabCount += 1

        if not treasureGrabCount:
            return "Couldn't grab any treasures."
        return 'Grabbed %d treasures!' % treasureGrabCount


class ToggleOccluders(MagicWord):
    aliases = ['occluders', 'cullers']
    desc = 'Displays occluder nodes'
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT
    state = False

    def handleWord(self, invoker, avId, toon, *args):
        if ToggleOccluders.state:
            for node in render.findAllMatches('**/+OccluderNode'):
                node.hide()
        else:
            for node in render.findAllMatches('**/+OccluderNode'):
                node.show()
        ToggleOccluders.state = not ToggleOccluders.state


class Timer(MagicWord):
    aliases = ['startTimer', 'countdown', 'startCountdown', 'time', 'startTime', 'clock', 'startClock', 'tickTock']
    desc = 'Starts a timer with the specified time on your screen. Specify 0 seconds to end the timer.'
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT
    affectRange = [MagicWordConfig.AFFECT_SELF]
    arguments = [('time', int, False, 0)]

    # Sound to play when timer ends
    TIME_OVER_PATH = 'phase_4/audio/sfx/ring_miss.ogg'

    # Specifying this value ends the timer
    TIMER_END_TIME = 0

    # Min and max values allowed in the timer
    TIMER_MIN_TIME = 0
    TIMER_MAX_TIME = 999

    def __init__(self):
        MagicWord.__init__(self)

        self.timer = None
        self.timeOverSfx = loader.loadSfx(self.TIME_OVER_PATH)

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg == 0:
            return ('0', 'End Timer'), ('1', 'One Second'), ('10', '10 Seconds'), ('30', '30 Seconds'), ('60', '1 Minute'), ('300', '5 Minutes'), ('600', '10 Minutes'), ('999', 'Maximum Seconds')
        return None

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 0:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                time = int(entry)
                return self.TIMER_MIN_TIME <= time <= self.TIMER_MAX_TIME
            return False 

        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        duration = args[0]

        if duration == self.TIMER_END_TIME:
            if self.timer:
                self.__cleanupTimer()
                return 'Ended timer.'
            return "There's no timer to end."

        elif duration < self.TIMER_MIN_TIME or duration > self.TIMER_MAX_TIME:
            return 'Specified time must be from %d to %d seconds.' % (self.TIMER_MIN_TIME, self.TIMER_MAX_TIME)

        if not self.timer:
            self.timer = ToontownTimer.ToontownTimer()
            self.timer.posAboveLaffMeter()
            base.setCellsAvailable([base.leftCells[0]], 0)
        self.timer.reset()
        self.timer.countdown(duration, self.__timerExpired)

        # English is a great language
        if duration == 1:
            secondStr = 'second'
        else:
            secondStr = 'seconds'

        return 'Timer started for %d %s.' % (duration, secondStr)

    def __timerExpired(self):
        if self.timer:
            self.__cleanupTimer()

            base.playSfx(self.timeOverSfx)

    def __cleanupTimer(self):
        # Note: This assumes the timer already exists;
        # please check it when using this method
        self.timer.destroy()
        base.setCellsAvailable([base.leftCells[0]], 1)


class Interval(MagicWord):
    IntervalList = []
    aliases = ['ival']
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT
    arguments = [("command", str, False, 'help'), ("duration", int, False, 5)]

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg == 0:
            return (('add', 'Add a waypoint'),
                    ('play', 'Play back the interval'),
                    ('export', 'Export the interval as an image sequence'),
                    ('clear', 'Clears the interval'),
                    ('start', 'Play back the interval')
                    )
        return None

    def handleWord(self, invoker, avId, toon, *args):
        if args[0] == 'add':
            if len(Interval.IntervalList) == 0:
                Interval.IntervalList.append((base.cam.getPos(render), base.cam.getHpr(render), 0))
                return f'Added Initial Point at {base.cam.getPos(render)}, {base.cam.getHpr(render)}'
            Interval.IntervalList.append((base.cam.getPos(render), base.cam.getHpr(render), args[1]))
            return f"Added Point #{len(Interval.IntervalList)}: {args[1]}s @({base.cam.getPos(render)}" \
                   f", {base.cam.getHpr(render)})"

        elif args[0] == 'clear':
            Interval.IntervalList = []
            return f"Clear list"
        elif args[0] in ('play', 'start', 'export'):
            if not len(Interval.IntervalList) > 1:
                return "You need atleast 2 points to play"

            base.camera.reparentTo(render)
            base.localAvatar.disableSmartCameraViews()
            base.localAvatar.deactivateCamera()
            seq = Sequence(
            )
            for pos, hpr, dur in Interval.IntervalList:
                if dur == 0:
                    seq.append(Func(base.camera.setPosHpr, render, pos, hpr))
                else:
                    seq.append(LerpPosQuatInterval(base.camera, duration = dur, pos = pos, hpr = hpr))

            seq.append(Func(base.camera.reparentTo, base.localAvatar))
            seq.append(Func(base.localAvatar.enableSmartCameraViews))
            seq.append(Func(base.localAvatar.activateCamera))
            seq.start()

            # If the 'export' option is used, we do the above, but then we export each frame
            if args[0] == 'export':
                if not os.path.exists('movies'):
                    os.mkdir('movies')
                exportFolder = os.path.join('movies', datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S'))
                if not os.path.exists(exportFolder):
                    os.mkdir(exportFolder)
                props = WindowProperties()
                props.setSize(2560, 1440)
                base.win.requestProperties(props)
                base.graphicsEngine.renderFrame()
                if base.win.getProperties().getMaximized() or base.win.getProperties().getFullscreen():
                    return 'You cannot export in a maximized window or in fullscreen mode!'

                aspect2d.hide()
                base.movie(namePrefix = f'{exportFolder}/movie', duration = seq.getDuration(),
                           fps = 60, format = 'jpg', sd = 5)


class HideUnsupportedHardwareWarning(MagicWord):
    """
    Hides the warning that displays if you are running on an Intel GPU
    """
    aliases = ['huhw']
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT
    desc = "Hides the warning that displays if you are running on unsupported hardware."

    def handleWord(self, invoker, avId, toon, *args):
        if hasattr(base, 'gpuWarning'):
            base.gpuWarning.destroy()
            del base.gpuWarning
        else:
            return 'You are not running any unsupported hardware :)'


class ReloadTexture(MagicWord):
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT
    desc = "Reloads all textures"

    def handleWord(self, invoker, avId, toon, *args):
        base.win.getGsg().getPreparedObjects().releaseAll()
        return "Textures have been reloaded."


class SetProfileBackground(MagicWord):
    aliases = ["profilebackground", "settoonprofilebackground", "toonprofilebackground", "pbackground", "profilebg", "settoonprofilebg", "toonprofilebg", "pbg"]
    desc = "Sets the toon profile background of the target."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("id", int, False, 0)]

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        return ((str(i), TTLocalizer.ProfileBackgroundNames[i]) for i in range(len(TTLocalizer.ProfileBackgroundNames)))

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        validType = MagicWord.validateArg(self, arg, entry, allArgs)
        if validType:
            profileId = int(entry)
            return 0 <= profileId <= len(TTLocalizer.ProfileBackgroundNames) - 1
        return False

    def handleWord(self, invoker, avId, toon, *args):
        id = args[0]
        if not 0 <= id <= len(TTLocalizer.ProfileBackgroundNames) - 1:
           return f"Invalid profile background id specified: {id}"

        if id not in toon.getProfileBackgrounds():
            return f"{toon.getName()} has not obtained the {TTLocalizer.ProfileBackgroundNames[id]} profile background yet."

        if id == toon.getProfileBackground():
            return f"{toon.getName()} is already using the {TTLocalizer.ProfileBackgroundNames[id]} profile background."

        toon.b_setProfileBackground(id)
        return f"{toon.getName()}'s profile background has been set to {TTLocalizer.ProfileBackgroundNames[id]}."


class SetProfilePose(MagicWord):
    aliases = ["profilepose", "settoonprofilepose", "toonprofilepose", "ppose"]
    desc = "Sets the toon profile pose of the target."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("id", int, False, 0)]

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        return ((str(i), TTLocalizer.ProfilePoseNames[i]) for i in range(len(TTLocalizer.ProfilePoseNames)))

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        validType = MagicWord.validateArg(self, arg, entry, allArgs)
        if validType:
            profileId = int(entry)
            return 0 <= profileId <= len(TTLocalizer.ProfilePoseNames) - 1
        return False

    def handleWord(self, invoker, avId, toon, *args):
        id = args[0]
        if not 0 <= id <= len(TTLocalizer.ProfilePoseNames) - 1:
           return f"Invalid profile pose id specified: {id}"

        if id not in toon.getProfilePoses():
            return f"{toon.getName()} has not obtained the {TTLocalizer.ProfilePoseNames[id]} profile pose yet."

        if id == toon.getProfilePose():
            return f"{toon.getName()} is already using the {TTLocalizer.ProfilePoseNames[id]} profile pose."

        toon.b_setProfilePose(id)
        return f"{toon.getName()}'s profile pose has been set to {TTLocalizer.ProfilePoseNames[id]}."


class ToggleNoClip(MagicWord):
    aliases = ["fly", 'setfly', 'noclip']
    desc = "Toggles noclip / fly mode"
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT

    def handleWord(self, invoker, avId, toon, *args):
        if not base.localAvatar:
            return "Your Toon does not exist!"

        if hasattr(self.cr, 'pieBlitzGame') and self.cr.pieBlitzGame.isActive():
            return "Cannot noclip during a Pie Blitz! Please wait until it is over."

        if hasattr(self.cr, 'hideAndSeekGame') and self.cr.hideAndSeekGame.isActive():
            return "Cannot noclip during Hide and Seek! Please wait until it is over."

        boss = toon.findBoss()
        if boss and boss.hardcore:
            return "You cannot cheat in this Boss Battle!"

        currentControls = base.localAvatar.controlManager.currentControls
        if hasattr(currentControls, 'toggleFly'):
            currentControls.toggleFly()
            return f'Toggled noclip mode'
        else:
            return 'Cannot set noclip mode in the current control mode.'

class ToggleRemoveTool(MagicWord):
    aliases = ["removetool"]
    desc = "Toggle the remove tool, which deletes props upon left click."
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT
    accessLevel = "MODERATOR"

    def handleWord(self, invoker, avId, toon, *args):
        DistributedPropGenerator.removeTool = not DistributedPropGenerator.removeTool
        return f'Toggled remove tool to {DistributedPropGenerator.removeTool}!'

class SetVolume(MagicWord):
    aliases = ["volume"]
    desc = "Changes the volume of music and/or sfx."
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT
    arguments = [("musicType", str, True), ("volume", int, True)]

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg == 0:
            return ('music', None), ('sfx', None), ('all', None)
        else:
            return None

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 0:
            musicType = str(entry).lower()
            return musicType in ('music', 'sfx', 'all')
        elif arg == 1:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                return 0 <= int(entry) <= 100
            return False
        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        musicType = args[0].lower()
        vol = args[1]
        if musicType not in ('music', 'sfx', 'all'):
            return "Invalid music type."
        if not 0 <= vol <= 100:
            return "Volume must be in between 0 and 100."

        if musicType in ('all', 'music'):
            ClientSettings.MusicVolume.set(vol / 100.0)
            base.musicManager.setVolume(vol / 100)
        if musicType in ('all', 'sfx'):
            ClientSettings.SFXVolume.set(vol / 100.0)
            for sfxManager in base.sfxManagerList:
                sfxManager.setVolume(vol / 100)

        return f"Updated volume for {musicType}"

class Logout(MagicWord):
    aliases = ["exit", "leave", "pickatoon"]
    desc = "Logs you out of the game, and puts you back to the Pick A Toon."
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT

    def handleWord(self, invoker, avId, toon, *args):
        base.cr.gameFSM.request('closeShard')

class RNG(MagicWord):
    aliases = ["dice", "roll"]
    desc = "Rolls random numbers based on the user's input."
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT
    arguments = [("lowerLimit", float, False, 0), ("upperLimit", float, False, 100), ("amount", int, False, 1)]

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        validType = MagicWord.validateArg(self, arg, entry, allArgs)
        if validType:
            if arg == 0:
                lowerLimit = float(entry)
                return -1000000 <= lowerLimit <= 1000000
            elif arg == 1:
                upperLimit = float(entry)
                return -1000000 <= upperLimit <= 1000000
            elif arg == 2:
                amount = int(entry)
                return 1 <= amount <= 10
        return False

    def handleWord(self, invoker, avId, toon, *args):
        lowerLimit = args[0]
        upperLimit = args[1]
        amount = args[2]

        if lowerLimit > upperLimit:
            return "The lower limit cannot be higher than the upper limit!"

        if amount < 1:
            amount = 1
        elif amount > 10:
            amount = 10

        numbers = []
        for i in range(amount):
            numbers.append(random.randint(lowerLimit, upperLimit))

        return f"Rolled the following numbers: {','.join(str(n) for n in numbers)}!"

class ToonRoulette(MagicWord):
    desc = "Play the Toon Roulette game! The Toon who is picked, will be kicked out of the game!"
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    affectRange = [MagicWordConfig.AFFECT_SELF]
    arguments = [("action", str, True)]
    started = False
    toonsInvolved = []

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg == 0:
            return ('start', None), ('join', None), ('leave', None)
        else:
            return None

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 0:
            action = str(entry).lower()
            return action in ('start', 'play', 'join', 'enter', 'leave', 'exit')
        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        action = args[0].lower()

        if action in ('start', 'play'):
            if ToonRoulette.started:
                return "A Toon Roulette is currently in progress! Why not join it instead?"
            from otp.avatar.DistributedPlayerAI import DistributedPlayerAI
            for doId, do in list(self.air.doId2do.items()):
                if isinstance(do, DistributedPlayerAI):
                    if str(doId)[0] != str(self.air.districtId)[0]:
                        do.d_setSystemMessage(0, 'A Toon Roulette game has started! Use the "ToonRoulette" magic word to join.', WhisperPopup.WTSystem)
            ToonRoulette.started = True
            ToonRoulette.toonsInvolved.append(avId)
            self.acceptOnce(self.air.getAvatarExitEvent(avId), self.handleAvatarExited, extraArgs=[avId])
            self.doMethodLater(30, self.endRoulette, name = 'endRoulette')
            return 'Started and joined a Toon Roulette!'
        elif action in ('join', 'enter'):
            if not ToonRoulette.started:
                return "A Toon Roulette is not currently active."
            if avId not in ToonRoulette.toonsInvolved:
                self.acceptOnce(self.air.getAvatarExitEvent(avId), self.handleAvatarExited, extraArgs=[avId])
                ToonRoulette.toonsInvolved.append(avId)
                return 'Joined the Toon Roulette!'
            return 'You are already in this Toon Roulette.'
        elif action in ('leave', 'exit'):
            if not ToonRoulette.started:
                return "A Toon Roulette is not currently active."
            if avId in ToonRoulette.toonsInvolved:
                ToonRoulette.toonsInvolved.remove(avId)
                self.ignore(self.air.getAvatarExitEvent(avId))
                return 'Left the Toon Roulette.'
            return 'You cannot leave! You are not in this Toon Roulette.'

        return 'Invalid action specified!'

    def handleAvatarExited(self, avId):
        if avId in ToonRoulette.toonsInvolved:
            ToonRoulette.toonsInvolved.remove(avId)
        self.ignore(self.air.getAvatarExitEvent(avId))

    def endRoulette(self, task=None):
        from otp.avatar.DistributedPlayerAI import DistributedPlayerAI

        ToonRoulette.started = False
        if not ToonRoulette.toonsInvolved:
            for doId, do in list(self.air.doId2do.items()):
                if isinstance(do, DistributedPlayerAI):
                    if str(doId)[0] != str(self.air.districtId)[0]:
                        do.d_setSystemMessage(0, 'The Toon Roulette game has ended. No one has been kicked.', WhisperPopup.WTSystem)
                        if doId in ToonRoulette.toonsInvolved:
                            ToonRoulette.toonsInvolved.remove(doId)
                            self.ignore(self.air.getAvatarExitEvent(doId))
            return

        toonKicked = random.choice(ToonRoulette.toonsInvolved)
        toon = simbase.air.doId2do.get(toonKicked)
        if toon:
            toonName = toon.getName()
            toon.sendSetKick(reason = 'You lost the Toon Roulette game!', target = toon)
        else:
            toonName = 'Toon'

        for doId, do in list(self.air.doId2do.items()):
            if isinstance(do, DistributedPlayerAI):
                if str(doId)[0] != str(self.air.districtId)[0] and doId != toonKicked:
                    do.d_setSystemMessage(0, f'{toonName} lost the Toon Roulette and has been kicked from the game!', WhisperPopup.WTSystem)
                    if doId in ToonRoulette.toonsInvolved:
                        ToonRoulette.toonsInvolved.remove(doId)
                        self.ignore(self.air.getAvatarExitEvent(doId))

class RockPaperScissors(MagicWord):
    aliases = ['rps']
    desc = "Play a game of Rock Paper Scissors with Magic Minnie!"
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT
    arguments = [("choice", str, True)]

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg == 0:
            return ('rock', None), ('paper', None), ('scissors', None)
        else:
            return None

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 0:
            choice = str(entry).lower()
            return choice in ('rock', 'paper', 'scissors')
        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        playerChoice = args[0].lower()
        computerChoice = random.choice(['rock', 'paper', 'scissors'])

        if playerChoice == computerChoice:
            return f'We both selected {playerChoice}. We tie!'
        elif playerChoice == 'rock':
            if computerChoice == "scissors":
                return 'Rock crushes scissors. You win!'
            return 'Paper covers rock. I win!'
        elif playerChoice == 'paper':
            if computerChoice == 'rock':
                return 'Paper covers rock. You win!'
            return 'Scissors cut paper. I win!'
        elif playerChoice == 'scissors':
            if computerChoice == 'paper':
                return 'Scissors cut paper. You win!'
            return 'Rock crushes scissors. You lose!'

        return 'Invalid choice given.'

class ToggleToonDownDmg(MagicWord):
    aliases = ["toggletoondowndamage", "toggletaketoondowndamage", "taketoondowndmg", "toondowndmg", "tdowndmg", "taketoondowndamage", "tdowndamage"]
    desc = "Toggles Toon-Down unite damage taken from non-moderator Toons. When enabled, the target will always be affected by Toon-Down unites."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER

    def handleWord(self, invoker, avId, toon, *args):
        if not toon:
            return

        toon.setTakeToonDownDamage(not toon.getTakeToonDownDamage())

        return f"Toggled Toon-Down damage {'ON' if toon.getTakeToonDownDamage() else 'OFF'} for {toon.getName()} for this session."


class RemoveFacilityCogs(MagicWord):
    aliases = ["deletefacilitycogs", "clearfacilitycogs"]
    desc = "Removes all Cogs from a facility floor if they aren't in a battle."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER

    def handleWord(self, invoker, avId, toon, *args):
        messenger.send(f'deleteCogs-{invoker.zoneId}')
        return 'Cleared Cogs on current floor.'


class EnableInDevelopmentCustomizeToonPage(MagicWord):
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT
    hidden = True

    def handleWord(self, invoker, avId: int, toon, *args):
        if hasattr(base.localAvatar, 'customizeToonPage'):
            base.localAvatar.book.addPage(base.localAvatar.customizeToonPage, pageName = TTLocalizer.CustomizeToonPageTitle)
            return 'Enabled In-Development Customize Toon Page. Proceed with caution.'


if __debug__:
    class HideVersionInfo(MagicWord):
        desc = 'Hides version info'
        affectRange = [MagicWordConfig.AFFECT_SELF]
        execLocation = MagicWordConfig.EXEC_LOC_CLIENT

        def handleWord(self, invoker, avId: int, toon, *args):
            base.WIP_LABEL.destroy()

    class PStats(MagicWord):
        aliases = ['clientpstats']
        desc = 'Starts pstats on the client.'
        affectRange = [MagicWordConfig.AFFECT_SELF]
        execLocation = MagicWordConfig.EXEC_LOC_CLIENT

        def handleWord(self, invoker, avId, toon, *args):
            from direct.task import Task
            from panda3d.core import PStatClient
            if base.wantStats:
                base.wantStats = 0
                Task.TaskManager.pStatsTasks = 0
                if PStatClient.isConnected():
                    PStatClient.disconnect()
                    return 'Disconnected client pstats'
                return 'Could not disconnect client pstats'
            else:
                base.wantStats = 1
                Task.TaskManager.pStatsTasks = 1
                result = base.createStats()
                if result:
                    return 'Connected client pstats'
                return 'Could not connect client pstats'


    class PStatsAI(MagicWord):
        aliases = ['aipstats']
        desc = 'Starts pstats on the AI.'
        affectRange = [MagicWordConfig.AFFECT_SELF]
        execLocation = MagicWordConfig.EXEC_LOC_SERVER

        def handleWord(self, invoker, avId, toon, *args):
            from direct.task import Task
            from panda3d.core import PStatClient
            if simbase.wantStats:
                simbase.wantStats = 0
                Task.TaskManager.pStatsTasks = 0
                if PStatClient.isConnected():
                    PStatClient.disconnect()
                    return 'Disconnected AI pstats'
                return 'Could not disconnect AI pstats'
            else:
                simbase.wantStats = 1
                Task.TaskManager.pStatsTasks = 1
                result = simbase.createStats()
                if result:
                    return 'Connected AI pstats'
                return 'Could not connect AI pstats'


    class ToggleTexMem(MagicWord):
        aliases = ["texmem"]
        desc = "Toggles the debug texture memory viewer."
        execLocation = MagicWordConfig.EXEC_LOC_CLIENT

        def handleWord(self, invoker, avId, toon, *args):
            base.toggleTexMem()
            return 'Toggled the texture memory viewer.'


    class AIRender(MagicWord):
        aliases = ['showairender', 'aiscene', 'showaiscene']
        desc = 'Opens another window to show the server sided scene for the zone specified.'
        arguments = [("zoneId", int, True)]
        affectRange = [MagicWordConfig.AFFECT_SELF]
        execLocation = MagicWordConfig.EXEC_LOC_SERVER

        def handleWord(self, invoker, avId, toon, *args):
            from otp.ai.ShowBaseAI import ShowBaseAI
            from otp.ai.AIZoneData import AIZoneData
            import builtins

            # Do proper cleanup
            if hasattr(builtins, 'base'):
                builtins.base.zoneData.destroy()
                builtins.base.destroy()
            showZone = args[0]
            base = ShowBaseAI('zone %s' % showZone)
            base.zoneData = AIZoneData(self.air, self.air.districtId, showZone)
            render = base.zoneData.getRender()
            base.camNode.setScene(render)
            base.camera.reparentTo(render)
            render.findAllMatches('**/+CollisionNode').show()
            base.zoneData.getCollTrav().showCollisions(render)
            axis = loader.loadModel('phase_3/models/props/xyzAxis')
            axis.reparentTo(render)
            axis.setPosHpr(render, 0, 0, 0, 0, 0, 0)
            return 'rendering AI zone %s' % showZone


    class SphereMap(MagicWord):
        aliases = ["sphere"]
        desc = "Saves a sphere map to the screenshots folder"
        execLocation = MagicWordConfig.EXEC_LOC_CLIENT

        def handleWord(self, invoker, avId, toon, *args):
            base.localAvatar.getGeomNode().hide()
            base.localAvatar.setNameVisible(0)
            base.graphicsEngine.renderFrame()
            filenameStr = base.config.GetString('screenshot-filename',
                                                'screenshots/sphere_map-%a-%b-%d-%H-%M-%S-%Y.png')
            filenameStr = datetime.datetime.now().strftime(filenameStr)
            sphere = base.saveSphereMap(namePrefix = filenameStr, size = 1024)
            base.graphicsEngine.renderFrame()
            base.localAvatar.getGeomNode().show()
            base.localAvatar.setNameVisible(1)
            return f'Saved {sphere}!'


    class GoToHidden(MagicWord):
        aliases = ["hidden"]
        desc = 'Reparents the toon to the hidden node'
        execLocation = MagicWordConfig.EXEC_LOC_CLIENT

        def handleWord(self, invoker, avId, toon, *args):
            base.localAvatar.reparentTo(hidden)


    class GoToRender(MagicWord):
        aliases = ["render"]
        desc = 'Reparents the toon to the render node'
        execLocation = MagicWordConfig.EXEC_LOC_CLIENT

        def handleWord(self, invoker, avId, toon, *args):
            base.localAvatar.reparentTo(render)


    class StressPet(MagicWord):
        aliases = ['petstress', 'petstresstest']
        desc = 'Stress test doodles by spawning a bunch.'
        execLocation = MagicWordConfig.EXEC_LOC_SERVER
        affectRange = [MagicWordConfig.AFFECT_SELF]
        # 50 friends, six Toons/acct #100 * 3 # 500 toons, 100 at estate, 3 pets per
        arguments = [('numPets', int, False, 56)]

        def handleWord(self, invoker, avId, toon, *args):
            from toontown.pets import DistributedPetAI
            from otp.otpbase.PythonUtil import randFloat
            numPets = args[0]
            for i in range(numPets):
                pet = DistributedPetAI.DistributedPetAI(self.air)
                # make up a fake owner doId
                pet._initFakePet(100 + i, 'StressPet%s' % i)
                pet.generateWithRequired(invoker.zoneId)
                pet.setPos(randFloat(-30, 30),
                           randFloat(-30, 30), 0)
                pet.b_setParent(ToontownGlobals.SPRender)


    class FakeException(MagicWord):
        aliases = ['fakecrash', 'simulatecrash', 'simulateexception']
        desc = 'Create a fake AI crash for testing purposes.'
        execLocation = MagicWordConfig.EXEC_LOC_SERVER
        affectRange = [MagicWordConfig.AFFECT_SELF]

        def handleWord(self, invoker, avId, toon, *args):
            self.air.notify.error('Successfully simulated an AI crash!')


    class ToggleOobeCull(MagicWord):
        aliases = ["oobecull"]
        desc = "Toggles 'out of body experience' view, with culling debugging for your toon."
        execLocation = MagicWordConfig.EXEC_LOC_CLIENT

        def handleWord(self, invoker, avId, toon, *args):
            if hasattr(self.cr, 'hideAndSeekGame') and self.cr.hideAndSeekGame.isActive():
                return "Oobe cull toggling is disabled during Hide and Seek."
            base.oobeCull()
            return 'Toggled "out of body experience" view.'


    class SplitScreenTest(MagicWord):
        aliases = ['split']
        execLocation = MagicWordConfig.EXEC_LOC_CLIENT

        def handleWord(self, invoker, avId, toon, *args):
            w, h = base.win.getSize()
            # Create two buffers for each side of the screen
            LBuffer = base.win.makeTextureBuffer("sbsd_intro_LBuffer", w, h)
            RBuffer = base.win.makeTextureBuffer("sbsd_intro_SBuffer", w, h)
            # For each buffer, make an actual camera
            LCam = base.makeCamera(LBuffer, aspectRatio = 1.0, displayRegion = (0, 0.6, 0, 1))
            RCam = base.makeCamera(RBuffer, aspectRatio = 1.0, displayRegion = (0.4, 1, 0, 1))
            LCam.node().getLens().setMinFov(80)
            RCam.node().getLens().setMinFov(80)

            LCam.reparentTo(render)
            LCam.setPosHpr(32, -2, 6, -54, 20, 0)

            RCam.reparentTo(render)
            RCam.setPosHpr(37, 8.4, 6, -144, 20, 0)

            # this is the actual model itself
            screen = loader.loadModel('phase_14.5/models/gui/ttoff_m_gui_mg_sbsd_splitScreen.bam')
            screen.reparentTo(render2dp)

            screen.setScale(1. / 4.5)  # i need to fix model itself lol
            left = screen.find('**/SPLIT_L')
            right = screen.find('**/SPLIT_R')

            # take the texture from the buffer and put it on the thingy
            left.setTexture(LBuffer.getTexture(), 1)
            right.setTexture(RBuffer.getTexture(), 1)

            sbsdGui = loader.loadModel('phase_14.5/models/gui/ttoff_m_gui_mg_sbsd.bam')
            vs = sbsdGui.find('**/ttoff_t_gui_mg_sbsd_introVersus')
            vs.reparentTo(aspect2dp)
            vs.setScale(0.6, 1.0, 0.3)
            vs.setColorScale(1.0, 1.0, 1.0, 0.0)
            sbsdGui.removeNode()

            Sequence(
                    Parallel(
                            LerpColorScaleInterval(aspect2d, 0.2, VBase4(1.0, 1.0, 1.0, 0.0)),
                            LerpPosInterval(left, 0.5, Vec3(0, 0, 0), startPos = Vec3(0, 0, 10), blendType = 'easeIn'),
                            LerpPosInterval(right, 0.5, Vec3(0, 0, 0), startPos = Vec3(0, 0, -10),
                                            blendType = 'easeIn')),
                    LerpColorScaleInterval(vs, 0.2, VBase4(1.0, 1.0, 1.0, 1.0)),
                    Wait(5),
                    Parallel(
                            LerpColorScaleInterval(aspect2d, 0.2, VBase4(1.0, 1.0, 1.0, 1.0)),
                            LerpPosInterval(left, 0.5, Vec3(0, 0, 10), blendType = 'easeIn'),
                            LerpPosInterval(right, 0.5, Vec3(0, 0, -10), blendType = 'easeIn'),
                            LerpColorScaleInterval(vs, 0.2, VBase4(1.0, 1.0, 1.0, 0.0))),
            ).start()


    class ToggleBufferView(MagicWord):
        execLocation = MagicWordConfig.EXEC_LOC_CLIENT
        desc = 'Toggles debug display of RTT buffers'
        aliases = ['bufferview', 'buffers']
        arguments = [("state", int, True)]

        def handleWord(self, invoker, avId, toon, *args):
            base.bufferViewer.enable(args[0])

class SetFlowerSpinRate(MagicWord):
    aliases = ["spinrate"]
    desc = "Sets how fast the Daisy Gardens flower will spin."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("spinRate", float, False, ToontownGlobals.FLOWER_SPIN_RATE_DEFAULT)]
    cooldown = 5.0

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg == 0:
            return (str(ToontownGlobals.FLOWER_SPIN_RATE_MIN), 'Minimum'), (str(ToontownGlobals.FLOWER_SPIN_RATE_DEFAULT), None), (str(ToontownGlobals.FLOWER_SPIN_RATE_MAX), 'Maximum')
        return None

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 0:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                spinRate = float(entry)
                return ToontownGlobals.FLOWER_SPIN_RATE_MIN <= spinRate <= ToontownGlobals.FLOWER_SPIN_RATE_MAX
            return False
        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        spinRate = args[0]
        if not ToontownGlobals.FLOWER_SPIN_RATE_MIN <= spinRate <= ToontownGlobals.FLOWER_SPIN_RATE_MAX:
            return f"That spin rate is out of range! It must be between {ToontownGlobals.FLOWER_SPIN_RATE_MIN} and {ToontownGlobals.FLOWER_SPIN_RATE_MAX}"
        from toontown.safezone.DistributedDGFlowerAI import DistributedDGFlowerAI
        for flower in simbase.air.doFindAllInstances(DistributedDGFlowerAI):
            flower.d_setSpinRate(spinRate)
        return f"Set the Daisy Gardens spin rate to {spinRate}!"

class RequestMintFloor(MagicWord):
    aliases = ["requestcoinfloor", "requestdollarfloor", "requestbullionfloor",
               "nextmintfloor", "nextcoinfloor", "nextdollarfloor", "nextbullionfloor"]
    desc = "Request the floor that will be generated in the Toon's next Cog Mint."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    affectRange = [MagicWordConfig.AFFECT_SELF]
    arguments = [("floor", int, False, 1)]

    def getValidValuesForArg(self, arg: int) -> Optional[Union[List[Tuple[str, Optional[str]]], Tuple[Tuple[str, Optional[str]], ...]]]:
        if arg == 0:
            return ((str(x), None) for x in range(1, 21))
        return None

    def validateArg(self, arg: int, entry: str, allArgs: List[str] = []) -> bool:
        if arg == 0:
            validType = MagicWord.validateArg(self, arg, entry, allArgs)
            if validType:
                floor = int(entry)
                return 1 < floor < 20
            return False
        return MagicWord.validateArg(self, arg, entry, allArgs)

    def handleWord(self, invoker, avId, toon, *args):
        floor = args[0]
        if floor < 0:
            floor = 1
        if floor > 20:
            floor = 20

        invoker.mintFloorRequest = floor
        return f'Your next Cog Mint will be Floor {floor}!'

# Instantiate all classes defined here to register them.
# A bit hacky, but better than the old system
for item in list(globals().values()):
    if isinstance(item, type) and issubclass(item, MagicWord):
        i = item()
