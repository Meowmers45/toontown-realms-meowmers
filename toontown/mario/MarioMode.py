from pathlib import Path

from direct.directnotify import DirectNotifyGlobal
from direct.showbase.InputStateGlobal import inputState
from direct.task import Task
from panda3d.core import ClockObject, NodePath

from toontown.mario.sm64 import MarioModel, MarioUnavailable


class MarioMode:
    notify = DirectNotifyGlobal.directNotify.newCategory('MarioMode')
    tickInterval = 1 / 30

    def __init__(self, toon):
        geom = toon.getGeomNode()
        if not toon.hasLOD() or geom.isEmpty():
            raise MarioUnavailable('Wait for your Toon to finish loading before using Mario mode.')

        self.toon = toon
        self.toonModel = NodePath(geom, toon.getLODNode())
        self.model = MarioModel(Path('mario').resolve())
        self.model.node.reparentTo(geom)
        self.wasHidden = self.toonModel.node().isOverallHidden()
        self.toonModel.hide()
        self.elapsed = 0
        self.toon.controlManager.setMarioControls(True)
        base.controlManager.setMarioHotkeys(True)
        self.task = taskMgr.add(self.update, toon.uniqueName('mario-pose'), sort=48)

    def update(self, task):
        # Use the existing geom parent for hide/show, teleports and tunnel transitions.
        if self.toon.firstPerson and not self.toon.cameraMode:
            self.model.node.hide()
        else:
            self.model.node.show()

        dt = ClockObject.getGlobalClock().getDt()
        self.elapsed = min(self.elapsed + dt, self.tickInterval * 3)
        controls = self.toon.controlManager
        speed, rotation, slide = controls.getSpeeds() if controls.isEnabled else (0, 0, 0)
        try:
            while self.elapsed >= self.tickInterval:
                self.elapsed -= self.tickInterval
                self.model.tick(
                    bool(speed or rotation or slide),
                    controls.isEnabled and inputState.isSet('jump'),
                    controls.isEnabled and inputState.isSet('marioPunch'),
                    controls.isEnabled and inputState.isSet('descend'),
                )
        except Exception as exc:
            self.notify.warning(f'Mario mode stopped: {exc}')
            self.toon.stopMarioMode()
            return Task.done
        return Task.cont

    def close(self):
        self.task.remove()
        self.toon.controlManager.setMarioControls(False)
        base.controlManager.setMarioHotkeys(False)
        self.model.close()
        if not self.toonModel.isEmpty() and not self.wasHidden:
            self.toonModel.show()
