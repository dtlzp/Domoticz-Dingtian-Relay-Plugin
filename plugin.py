# Dingtian Relay Python Plugin for Domoticz
#
# Author: lzp@dingtian-tech.com
#
"""
<plugin key="DingtianRelay" name="Dingtian Relay" author="dingtian-tech" version="1.1.0" wikilink="https://github.com/dtlzp/Domoticz-Dingtian-Relay-Plugin" externallink="https://www.dingtian-tech/en_us/product.html?tab=relay">
    <description>
        Dingtian-tech Relay Domoticz Plugin.
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
        <param field="Mode2" label="Debug" width="75px">
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

    BeaconConn = None
    BeaconConnS = None
    last_times = 0
    lastHeartbeat = datetime.datetime.now()
    device_alive = False

    def __init__(self):
        self.var = 1.0
        return

    def onStart(self):
        if Parameters["Mode2"] == "Debug":
            Domoticz.Debugging(1)
            Domoticz.Log("Debugger started, use 'telnet 127.0.0.1 4444' to connect")
            import rpdb
            rpdb.set_trace()
        Domoticz.Log("onStart called")

        self.channel_count = int(Parameters["Mode1"])+1
        if ( 0 == len(Devices) ):
            for i in range(1, self.channel_count):
                Domoticz.Device(Name="RELAY"+chr(0x30+i), Unit=i, TypeName="Switch",  Image=0).Create()
        else:
            for i in range(1, self.channel_count):
                self.relay[i] = Devices[i].nValue

        Domoticz.Log("onStart Connection to " + Parameters["Address"] + ":" + Parameters["Port"])
        self.BeaconConn = Domoticz.Connection(Name="RELAYUDPR", Transport="UDP/IP", Address=Parameters["Address"], Port=Parameters["Port"])
        self.BeaconConn.Listen()
        self.BeaconConnS = Domoticz.Connection(Name="RELAYUDPS", Transport="UDP/IP", Address=Parameters["Address"], Port="60000")
        Domoticz.Log("onStart Listen from " + Parameters["Address"] + ":" + Parameters["Port"] + " channel_count=" + str(self.channel_count))

    def onStop(self):
        Domoticz.Log("onStop called")

    def onConnect(self, Connection, Status, Description):
        Domoticz.Log("onConnect called")
        if( 0 != Status ):
            self.BeaconConn = None
            self.device_alive = False
            Domoticz.Log("Failed to connect ("+str(Status)+") to: "+Connection.Address+":"+Connection.Port+" with error: "+Description)
            return
        if( 0 == Status ):
            self.BeaconConn.Send(Message="00")

    def onMessage(self, Connection, Data):
        Domoticz.Log("onMessage called")
        Domoticz.Log("onMessage recv: "+Connection.Address+":"+Connection.Port)
        strData = Data.decode("utf-8", "ignore")
        Domoticz.Log("onMessage called with Data: "+str(strData)+" len(Data)="+str(len(strData)))
        self.device_alive = True
        self.last_times = 0
        self.lastHeartbeat = datetime.datetime.now()
        str_log = "onMessage relay: "
        for i in range(1, self.channel_count):
            self.relay[i] = int(strData[i-1])
            str_log += str(self.relay[i])
        Domoticz.Log(str_log)

        self.SyncDevices()
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
        Domoticz.Log("action=" + action + ",params=" + params + ",pack_size=" + str(size) + ",relay_index=" + str(relay_index))

        bit = 0
        if (action == "On"):
            bit = 1

        Domoticz.Log("Password:" + Parameters["Password"])

        password = int(Parameters["Password"])
        mask = 1   << relay_index
        setv = bit << relay_index
        Domoticz.Log("password=" + hex(password) + ",mask=" + hex(mask) + ",setv=" + hex(setv))

        b_cmd = struct.pack("<4BH2B", 0xFF, 0xAA, 0, 1, password, mask, setv)
        self.BeaconConnS.Send(Message=b_cmd)
        Domoticz.Log("onCommand end")

    def onNotification(self, Name, Subject, Text, Status, Priority, Sound, ImageFile):
        Domoticz.Log("Notification: " + Name + "," + Subject + "," + Text + "," + Status + "," + str(Priority) + "," + Sound + "," + ImageFile)

    def onDisconnect(self, Connection):
        Domoticz.Log("onDisconnect called")

    def onHeartbeat(self):
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
        for i in range(1, self.channel_count):
            str_val = on_off[0]
            if( 1 == self.relay[i] ):
                str_val = on_off[1]
            UpdateDevice(i, self.relay[i], str_val, not self.device_alive)

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