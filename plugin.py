# Dingtian Relay Python Plugin for Domoticz
#
# Author: lzp@dingtian-tech.com
#
"""
<plugin key="DingtianRelay" name="Dingtian Relay" author="dingtian-tech" version="1.3.1" wikilink="https://github.com/dtlzp/Domoticz-Dingtian-Relay-Plugin" externallink="https://www.dingtian-tech.com/en_us/product.html?tab=relay">
    <description>
        Dingtian-tech Relay Domoticz Plugin.<br />
        Parity Mutux:<br />
        {R1:ON,R2:OFF}/{R1:OFF,R2:ON}<br />
        {R3:ON,R4:OFF}/{R3:OFF,R4:ON}<br />
        {R5:ON,R6:OFF}/{R5:OFF,R6:ON}<br />
        {R7:ON,R8:OFF}/{R7:OFF,R8:ON}<br />
    </description>
    <params>
        <param field="Mode1" label="Firmware Version" width="100px">
            <options>
                <option label="< V2.17.x" value="False"/>
                <option label=">= V2.17.x" value="True" default="true"/>
            </options>
        </param>
        <param field="Address" label="IP Address" required="true" width="200px"/>
        <param field="Port" label="Port" width="50px" required="true" default="60001"/>
        <param field="Mode2" label="Channel Count" width="50px">
            <options>
                <option label="2" value="2" default="true"/>
                <option label="4" value="4"/>
                <option label="8" value="8"/>
                <option label="16" value="16"/>
                <option label="32" value="32"/>
            </options>
        </param>
        <param field="Password" label="Password" width="100px" required="true" default="0"/>
        <param field="Mode3" label="Parity Mutex" width="75px">
            <options>
                <option label="True" value="Yes"/>
                <option label="False" value="No" default="true" />
            </options>
        </param>
        <param field="Mode4" label="Debug" width="75px">
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
    fv2_17_x = False
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
    ip_addr = None

    def __init__(self):
        self.var = 1.3
        return

    def onStart(self):
        if Parameters["Mode1"] == "True":
            self.fv2_17_x = True

        if Parameters["Mode4"] == "Debug":
            self.dtr_debug = 1

        if Parameters["Mode3"] == "Yes":
            self.parity_mutex = True

        self.print_log(1, "onStart called")

        self.password = int(Parameters["Password"])

        self.channel_count = int(Parameters["Mode2"])+1
        offset = 1
        if ( 0 == len(Devices) ):
            for i in range(1, self.channel_count):
                Domoticz.Device(Name="RELAY"+str(i), Unit=offset, TypeName="Switch",  Image=0).Create()
                offset = offset + 1
            if True == self.fv2_17_x:
                for i in range(1, self.channel_count):
                    Domoticz.Device(Name="INPUT"+str(i), Unit=offset, TypeName="Switch",  Image=0).Create()
                    offset = offset + 1
        else:
            for i in range(1, self.channel_count):
                self.relay[i] = Devices[offset].nValue
                offset = offset + 1
            if True == self.fv2_17_x:
                for i in range(1, self.channel_count):
                    self.rinput[i] = Devices[offset].nValue
                    offset = offset + 1

        self.ip_addr = Parameters["Address"]
        port = int(Parameters["Port"])
        self.print_log(1, "onStart Connection to " + self.ip_addr + ":" + str(port))
        self.BeaconConn = Domoticz.Connection(Name="RELAYUDPR", Transport="UDP/IP", Address=self.ip_addr, Port=str(port))
        self.BeaconConn.Listen()
        port = port - 1
        self.print_log(1, "onStart Connection to " + self.ip_addr + ":" + str(port))
        self.BeaconConnS = Domoticz.Connection(Name="RELAYUDPS", Transport="UDP/IP", Address=self.ip_addr, Port=str(port))
        self.print_log(1, "onStart Listen from " + self.ip_addr + ":" + str(port) + " channel_count=" + str(self.channel_count))

    def onStop(self):
        self.print_log(1, "onStop called")

    def onConnect(self, Connection, Status, Description):
        self.print_log(1, "onConnect called")
        if( 0 != Status ):
            self.BeaconConn = None
            self.device_alive = False
            self.print_log(0, "Failed to connect ("+str(Status)+") to: "+Connection.Address+":"+Connection.Port+" with error: "+Description)
            return
        if( 0 == Status ):
            self.BeaconConn.Send(Message="00")
            b_cmd = struct.pack("<4BH", 0xFF, 0xAA, 0, 4, self.password)
            self.BeaconConnS.Send(Message=b_cmd)

    def check_keepalive(self, str_list):
        if True == self.fv2_17_x:
            if 3 != len(str_list):
                self.print_log(0, "check_keepalive 2_17_x error str_list: " + str_list)
                return False

            cnt = int(str_list[2])
            cnt = cnt + 1
            if cnt != self.channel_count:
                self.print_log(0, "check_keepalive 2_17_x error channel_count " + str(cnt-1) + "!=" + self.channel_count)
                return False

            str_val = str_list[0]
            if len(str_val) != (self.channel_count-1):
                self.print_log(0, "check_keepalive 2_17_x error relay: " + str_val)
                return False
            for i in range(1, self.channel_count):
                if ('0' != str_val[i-1]) and ('1' != str_val[i-1]):
                    return False

            str_val = str_list[1]
            if len(str_val) != (self.channel_count-1):
                self.print_log(0, "check_keepalive 2_17_x error input: " + str_val)
                return False
            for i in range(1, self.channel_count):
                if ('0' != str_val[i-1]) and ('1' != str_val[i-1]):
                    return False
        else:
            if 1 != len(str_list):
                self.print_log(0, "check_keepalive 2_17_x error str_list: " + str_list)
                return False

            str_val = str_list[0]
            if len(str_val) != (self.channel_count-1):
                self.print_log(0, "check_keepalive 2_16_x error relay: " + str_val)
                return False
            for i in range(1, self.channel_count):
                if ('0' != str_val[i-1]) and ('1' != str_val[i-1]):
                    return False

        return True

    def onMessage(self, Connection, Data):
        strData = Data.decode("utf-8", "ignore")
        self.print_log(1, "onMessage called with Data: "+str(strData)+" len(Data)="+str(len(strData))+" "+Connection.Address+":"+Connection.Port)

        if Connection.Address != self.ip_addr:
            self.print_log(0, "onMessage diff ip " + self.ip_addr + ":" + Connection.Address)
            return

        self.device_alive = True
        self.last_times = 0
        self.lastHeartbeat = datetime.datetime.now()
        strlist = strData.split(':')
        self.print_log(1, "onMessage start check_keepalive")
        ret = self.check_keepalive(strlist)
        if False == ret:
            return
        self.print_log(1, "onMessage len(strlist):" + str(len(strlist)))
        str_val = strlist[0]
        for i in range(1, self.channel_count):
            self.relay[i] = int(str_val[i-1])
        if True == self.fv2_17_x:
            str_val = strlist[1]
            for i in range(1, self.channel_count):
                self.rinput[i] = int(not int(str_val[i-1]))
            str_val = strlist[2]
            self.print_log(1, "onMessage channel_cnt:" + str_val)
        self.SyncDevices()
        self.print_log(1, "onMessage end")

    def onCommand(self, Unit, Command, Level, Hue):
        self.print_log(1, "onCommand called for Unit " + str(Unit) + ": Command " + str(Command) + ", Level: " + str(Level) + ", Hue: " + str(Hue))

        Command = Command.strip()
        action, sep, params = Command.partition(' ')
        action = action.capitalize()
        params = params.capitalize()

        if 33 == self.channel_count:
            pack_format = "<4BH2I"
        elif 17 == self.channel_count:
            pack_format = "<4BH2H"
        else:
            pack_format = "<4BH2B"

        self.print_log(1, "onCommand channel_count:" + str(self.channel_count) + " format:" + pack_format)

        size = struct.calcsize(pack_format)
        relay_index = int(Unit)
        if relay_index >= self.channel_count:
            self.print_log(1, "INPUT" + str(relay_index-self.channel_count+1) + " can't be Control")
            return
        relay_index = relay_index - 1
        self.print_log(1, "action=" + action + ",params=" + params + ",pack_size=" + str(size) + ",relay_index=" + str(relay_index))

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
        self.print_log(1, "password=" + hex(self.password) + ",mask=" + hex(mask) + ",setv=" + hex(setv))

        b_cmd = struct.pack(pack_format, 0xFF, 0xAA, 0, 1, self.password, mask, setv)
        self.BeaconConnS.Send(Message=b_cmd)
        self.print_log(1, "onCommand end")

    def onNotification(self, Name, Subject, Text, Status, Priority, Sound, ImageFile):
        self.print_log(1, "Notification: " + Name + "," + Subject + "," + Text + "," + Status + "," + str(Priority) + "," + Sound + "," + ImageFile)

    def onDisconnect(self, Connection):
        self.print_log(1, "onDisconnect called")

    def onHeartbeat(self):
        self.print_log(1, "onHeartbeat called")
        if (self.last_times > 60):
            self.print_log(0, self.BeaconConn.Name+" has not responded to 60 pings, terminating connection.")
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
            UpdateDevice(offset, self.relay[i], str_val, not self.device_alive, self.dtr_debug)
            offset = offset + 1

        if True == self.fv2_17_x:
            for i in range(1, self.channel_count):
                str_val = on_off[0]
                if( 1 == self.rinput[i] ):
                    str_val = on_off[1]
                UpdateDevice(offset, self.rinput[i], str_val, not self.device_alive, self.dtr_debug)
                offset = offset + 1

    def print_log(self, log_type, log_str):
        if 0 == log_type:
            Domoticz.Error(log_str)
            return
        if 1 == self.dtr_debug:
            Domoticz.Log(log_str)

# user funciton start
def UpdateDevice(Unit, nValue, sValue, TimedOut, DtrDebug):
    if (Unit in Devices):
        if (Devices[Unit].nValue != nValue) or (Devices[Unit].sValue != sValue) or (Devices[Unit].TimedOut != TimedOut):
            Devices[Unit].Update(nValue=nValue, sValue=str(sValue), TimedOut=TimedOut)
            if 1 == DtrDebug:
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
