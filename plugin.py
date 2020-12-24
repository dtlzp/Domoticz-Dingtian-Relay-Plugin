# Dingtian Relay Python Plugin for Domoticz
#
# Author: lzp@dingtian-tech.com
#
"""
<plugin key="DingtianRelay" name="Dingtian Relay" author="dingtian-tech" version="1.2.0" wikilink="https://github.com/dtlzp/Domoticz-Dingtian-Relay-Plugin" externallink="https://www.dingtian-tech/en_us/product.html?tab=relay">
    <description>
        Dingtian-tech Relay Domoticz Plugin.<br />
        Parity Mutux:<br />
        {R1:ON,R2:OFF}/{R1:OFF,R2:ON}<br />
        {R3:ON,R4:OFF}/{R3:OFF,R4:ON}<br />
        {R5:ON,R6:OFF}/{R5:OFF,R6:ON}<br />
        {R7:ON,R8:OFF}/{R7:OFF,R8:ON}<br />
    </description>
    <params>
        <param field="Address" label="IP Address" required="true" width="200px"/>
        <param field="Port" label="Port" width="50px" required="true" default="60001"/>
        <param field="Mode1" label="Channel Count" width="50px">
            <options>
                <option label="2" value="2" default="true"/>
                <option label="4" value="4"/>
                <option label="8" value="8"/>
            </options>
        </param>
        <param field="Password" label="Password" width="100px" required="true" default="0"/>
        <param field="Mode2" label="Parity Mutex" width="75px">
            <options>
                <option label="True" value="Yes"/>
                <option label="False" value="No" default="true" />
            </options>
        </param>
        <param field="Mode3" label="Debug" width="75px">
            <options>
                <option label="True" value="Debug"/>
                <option label="False" value="Normal" default="true" />
            </options>
        </param>
    </params>
</plugin>
"""
import Domoticz
import datetime
import struct

class BasePlugin:
    channel_count = 0
    relay = {}
    rinput = {}

    BeaconConn = None
    BeaconConnS = None
    last_times = 0
    lastHeartbeat = datetime.datetime.now()
    device_alive = False
    dtr_debug = 0
    parity_mutex = False
    password = 0

    def __init__(self):
        self.var = 1.2
        return

    def onStart(self):
        if Parameters["Mode3"] == "Debug":
            self.dtr_debug = 1

        if Parameters["Mode2"] == "Yes":
            self.parity_mutex = True

        Domoticz.Log("onStart called")

        self.password = int(Parameters["Password"])

        self.channel_count = int(Parameters["Mode1"])+1
        offset = 1
        if ( 0 == len(Devices) ):
            for i in range(1, self.channel_count):
                Domoticz.Device(Name="RELAY"+chr(0x30+i), Unit=offset, TypeName="Switch",  Image=0).Create()
                offset = offset + 1
            for i in range(1, self.channel_count):
                Domoticz.Device(Name="INPUT"+chr(0x30+i), Unit=offset, TypeName="Switch",  Image=0).Create()
                offset = offset + 1
        else:
            for i in range(1, self.channel_count):
                self.relay[i] = Devices[offset].nValue
                offset = offset + 1
            for i in range(1, self.channel_count):
                self.rinput[i] = Devices[offset].nValue
                offset = offset + 1

        port = int(Parameters["Port"])
        if 1 == self.dtr_debug:
            Domoticz.Log("onStart Connection to " + Parameters["Address"] + ":" + str(port))
        self.BeaconConn = Domoticz.Connection(Name="RELAYUDPR", Transport="UDP/IP", Address=Parameters["Address"], Port=str(port))
        self.BeaconConn.Listen()
        port = port - 1
        if 1 == self.dtr_debug:
            Domoticz.Log("onStart Connection to " + Parameters["Address"] + ":" + str(port))
        self.BeaconConnS = Domoticz.Connection(Name="RELAYUDPS", Transport="UDP/IP", Address=Parameters["Address"], Port=str(port))
        if 1 == self.dtr_debug:
            Domoticz.Log("onStart Listen from " + Parameters["Address"] + ":" + Parameters["Port"] + " channel_count=" + str(self.channel_count))

    def onStop(self):
        Domoticz.Log("onStop called")

    def onConnect(self, Connection, Status, Description):
        Domoticz.Log("onConnect called")
        if( 0 != Status ):
            self.BeaconConn = None
            self.device_alive = False
            Domoticz.Error("Failed to connect ("+str(Status)+") to: "+Connection.Address+":"+Connection.Port+" with error: "+Description)
            return
        if( 0 == Status ):
            self.BeaconConn.Send(Message="00")
            b_cmd = struct.pack("<4BH", 0xFF, 0xAA, 0, 1, self.password)
            self.BeaconConnS.Send(Message=b_cmd)

    def onMessage(self, Connection, Data):
        strData = Data.decode("utf-8", "ignore")
        if 1 == self.dtr_debug:
            Domoticz.Log("onMessage called with Data: "+str(strData)+" len(Data)="+str(len(strData))+" "+Connection.Address+":"+Connection.Port)
        self.device_alive = True
        self.last_times = 0
        self.lastHeartbeat = datetime.datetime.now()
        strlist = strData.split(':')
        str_val = strlist[0]
        for i in range(1, self.channel_count):
            self.relay[i] = int(str_val[i-1])
        str_val = strlist[1]
        for i in range(1, self.channel_count):
            self.rinput[i] = int(not int(str_val[i-1]))
        str_val = strlist[2]
        if 1 == self.dtr_debug:
            Domoticz.Log("onMessage channel_cnt:" + str_val)
        self.SyncDevices()
        if 1 == self.dtr_debug:
            Domoticz.Log("onMessage end")

    def onCommand(self, Unit, Command, Level, Hue):
        Domoticz.Log("onCommand called for Unit " + str(Unit) + ": Command " + str(Command) + ", Level: " + str(Level) + ", Hue: " + str(Hue))

        Command = Command.strip()
        action, sep, params = Command.partition(' ')
        action = action.capitalize()
        params = params.capitalize()

        size = struct.calcsize("<4BH2B")
        relay_index = int(Unit)
        relay_index = relay_index - 1
        if 1 == self.dtr_debug:
            Domoticz.Log("action=" + action + ",params=" + params + ",pack_size=" + str(size) + ",relay_index=" + str(relay_index))

        bit = 0
        if (action == "On"):
            bit = 1

        mask = 1   << relay_index
        setv = bit << relay_index
        if True == self.parity_mutex:
            if relay_index&1:
                relay_index=relay_index-1
            else:
                relay_index=relay_index+1
            bit = 0
            mask = mask | (1   << relay_index)
            setv = setv | (bit << relay_index)
        if 1 == self.dtr_debug:
            Domoticz.Log("password=" + hex(self.password) + ",mask=" + hex(mask) + ",setv=" + hex(setv))

        b_cmd = struct.pack("<4BH2B", 0xFF, 0xAA, 0, 1, self.password, mask, setv)
        self.BeaconConnS.Send(Message=b_cmd)
        if 1 == self.dtr_debug:
            Domoticz.Log("onCommand end")

    def onNotification(self, Name, Subject, Text, Status, Priority, Sound, ImageFile):
        Domoticz.Log("Notification: " + Name + "," + Subject + "," + Text + "," + Status + "," + str(Priority) + "," + Sound + "," + ImageFile)

    def onDisconnect(self, Connection):
        Domoticz.Log("onDisconnect called")

    def onHeartbeat(self):
        if 1 == self.dtr_debug:
            Domoticz.Log("onHeartbeat called")
        if (self.last_times > 5):
            Domoticz.Error(self.BeaconConn.Name+" has not responded to 5 pings, terminating connection.")
            self.device_alive = False
            self.last_times = 0
            self.SyncDevices()
        self.last_times = self.last_times + 1
        self.lastHeartbeat = datetime.datetime.now()

    def SyncDevices(self):
        on_off = ("Off", "On")
        offset = 1
        for i in range(1, self.channel_count):
            str_val = on_off[0]
            if( 1 == self.relay[i] ):
                str_val = on_off[1]
            UpdateDevice(offset, self.relay[i], str_val, not self.device_alive)
            offset = offset + 1
        for i in range(1, self.channel_count):
            str_val = on_off[0]
            if( 1 == self.rinput[i] ):
                str_val = on_off[1]
            UpdateDevice(offset, self.rinput[i], str_val, not self.device_alive)
            offset = offset + 1

# user funciton start
def UpdateDevice(Unit, nValue, sValue, TimedOut):
    if (Unit in Devices):
        if (Devices[Unit].nValue != nValue) or (Devices[Unit].sValue != sValue) or (Devices[Unit].TimedOut != TimedOut):
            Devices[Unit].Update(nValue=nValue, sValue=str(sValue), TimedOut=TimedOut)
            Domoticz.Log("Update "+str(nValue)+":'"+str(sValue)+"' ("+Devices[Unit].Name+")")
    return
# user funciton end

global _plugin
_plugin = BasePlugin()

def onStart():
    global _plugin
    _plugin.onStart()

def onStop():
    global _plugin
    _plugin.onStop()

def onConnect(Connection, Status, Description):
    global _plugin
    _plugin.onConnect(Connection, Status, Description)

def onMessage(Connection, Data):
    global _plugin
    _plugin.onMessage(Connection, Data)

def onCommand(Unit, Command, Level, Hue):
    global _plugin
    _plugin.onCommand(Unit, Command, Level, Hue)

def onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile):
    global _plugin
    _plugin.onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile)

def onDisconnect(Connection):
    global _plugin
    _plugin.onDisconnect(Connection)

def onHeartbeat():
    global _plugin
    _plugin.onHeartbeat()

    # Generic helper functions
def DumpConfigToLog():
    for x in Parameters:
        if Parameters[x] != "":
            Domoticz.Debug( "'" + x + "':'" + str(Parameters[x]) + "'")
    Domoticz.Debug("Device count: " + str(len(Devices)))
    for x in Devices:
        Domoticz.Debug("Device:           " + str(x) + " - " + str(Devices[x]))
        Domoticz.Debug("Device ID:       '" + str(Devices[x].ID) + "'")
        Domoticz.Debug("Device Name:     '" + Devices[x].Name + "'")
        Domoticz.Debug("Device nValue:    " + str(Devices[x].nValue))
        Domoticz.Debug("Device sValue:   '" + Devices[x].sValue + "'")
        Domoticz.Debug("Device LastLevel: " + str(Devices[x].LastLevel))
    return
