#!/usr/bin/python3

import time
import logger
import atexit
from collections import OrderedDict
import subprocess, sys

class motorset():
    """
    Creates a set of motors identified by their names.
    
    After setup many methods use the set of motors defined by the type of the mlist - see below.
    
    Other methods to provide co-ordinated actions, such as turning or attempting to keep straight will
    be defined at this level.
    
    The mlist parameter (common to many commands that directly control a motor)

    default                 : (None) All motors are used
    string                  : (name of motor) Only the motor identified by the name is used
    tuple, list, array...   : each entry is the name of a motor, all motors named are used
    """
    def __init__(self, motordefs=None, quadmonitor=None):
        """
        Sets up motors from a list of dicts, each dict defines the details of an individual motor.
        
        quadparams is used to start a separate process that monitors 1 or more quad encoders used for feedback control.
        
        see config_h_bridge.py or config_adafruit_dc_sm_hat.py for details
        """
        self.sharedServices={}
        self.motors=OrderedDict()
        if quadmonitor is None:
            self.quadmon=None
        else:
            qd={}
            for mdef in motordefs:
                if 'rotationsense' in mdef and 'pins' in mdef['rotationsense'] and len(mdef['rotationsense']['pins'])==2:
                    qd[mdef['name']]=mdef['rotationsense']['pins']
            if qd:
                print('qesetup', qd)
                self.quadmon=logger.makeClassInstance(motorquads=qd, **quadmonitor)
            else:
                self.quadmon=None

        for mdef in motordefs:
            self.motors[mdef['name']] = logger.makeClassInstance(parent=self, **mdef)
        atexit.register(self.close)

    def needservice(self, sname, className, **servargs):
        """
        called by motor instances if it uses a single instance of something
        
        sname       : the (unique) name by which we know the service - used as the key into self.sharedServices to check 
                      if we already have the service

        className   : the module and class needed to setup the service - see logger.makeClassInstance
        
        **servargs  : all the other params needed to make the service if it's not already there. In particular must have
        """
        if not sname in self.sharedServices:
            serv=logger.makeClassInstance(className=className, **servargs)
            self.sharedServices[sname]=serv
        return self.sharedServices[sname]

    def lastMotorPosition(self, mlist=None):
        """
        fetches last known position for the specified motors (see class help for mlist param)
        """
        return self._listcall(mlist, 'lastPosition')

    def lastMotorRPM(self, mlist=None):
        """
        returns the last known RPM for the specified motors (see class help for mlist param)
        """
        return self._listcall(mlist, 'lastRPM')

    def motorInvert(self, inv, mlist=None):
        """
        return and optionlly reverse the motor direction for specified motors (see class help for mlist param)
        """
        return self._listcall(mlist, 'invert', inv)

    def motorFrequency(self, f, mlist=None):
        """
        sets the frequency used for the dutycycle (see class help for mlist param)
        
        f:    if None the frequency is unchanged
        
        returns the current frequency
        """
        return self._listcall(mlist, 'frequency', f)

    def motorDC(self, dutycycle, mlist=None):
        """
        directly sets the duty cycle of the given set of motors (see class help for mlist param)
        
        See the motor class for details of the dutycycle param.
        """
        return self._listcall(mlist, 'DC', dutycycle)

    def motorSpeedLimits(self, mlist=None):
        return self._listcall(mlist, 'speedLimits')

    def motorSpeed(self, speed, mlist=None):
        """
        returns and optionally sets the target rpm of the given set of motors (see class help for mlist param)
        
        See the motor class for details of the speed param.
        """
        return self._listcall(mlist, 'speed', speed)

    def motorFeedbackParam(self, paramdetails, mlist=None):
        """
        optionally sets a single feedback param and returns the current (new if set) value
        
        see the feedback class for details of paramdetails
        """
        return self._listcall(mlist, 'feedbackParam', paramdetails)

    def motorTargetSpeed(self, tspeed, mlist=None):
        """
        when motor feedback is available with a feedback controller, we can set a target speed.

        see motor class for details
        """
        return self._listcall(mlist, 'targetSpeed', tspeed)

    def stopMotor(self, mlist=None):
        """
        stops specified motors (see class help for mlist param)
        """
        for u in self._delist(mlist):
            u.stop()

    def close(self):
        """
        completely shuts down this instance and deletes all internal knowledge of motors
        """
        for m in self._delist(None):
            m.close()
        time.sleep(.5)
        self.motors={}
        if not self.quadmon is None:
            pass
            # self.quadmon.send_signal()?

    def ticker(self):
        """
        called at (hopefully very) regular intervals to provide feedback control for the motors
        
        """
        for m in self.motors.values():
            m.ticker()

    def odef(self):
        """
        returns a dict that allows the class to be reconstructed as well as the current state?
        """
        return {'motordefs': [m.odef() for m in self.motors.values()]}

#######################################################################################
# INTERNAL STUFF
    def _delist(self, units):
        """
        internal routine converts / validates units param to list of motors
        """ 
        if units is None:
            return tuple(self.motors.values())
        elif isinstance(units,str):
            if units in self.motors:
                return (self.motors[units],)
            else:
                raise ValueError('%s is not a known motor name' % units)
        else:
            for u in units:
                if not u in self.motors:
                    self.stopMotor()
                    raise ValueError('%s is not a known motor name' % str(u))
            return [self.motors[m] for m in units]

    def _listcall(self, units, method, *args, **kwargs):
        if units is None:
            return {m.name: getattr(m, method)(*args, **kwargs) for m in self.motors.values()}
        elif isinstance(units, str):
            return getattr(self.motors[units], method)(*args, **kwargs)
        else:
            return {m: getattr(self.motors[m], method)(*args, **kwargs) for m in units}
