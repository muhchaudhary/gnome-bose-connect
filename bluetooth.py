import socket
import os
import math
import struct
import subprocess
import pydbus

class BoseQC35ii:

    def __init__(self):
        self.name = None
        self.serialNumber = None 
        self.noiseCancellation = None
        self.deviceId = None
        self.Indexrevision = None
        self.standby = None
        self.firmwareVersion = None
        self.numDevices = None
        self.numConnectedDevices = None
        self.connectedDevicesAddrs = None

    def get_device_info(self):
        send = b'\x01\x01\x05\x00'
        mysend(send)
        myreceive(4) # recieve acknoledgement from headphones, ignore for now
        # GET NAME 
        name_len = myreceive(4)[3] # python will turn this into an int
        self.name = myreceive(name_len).decode("utf-8")
        
        throwout = myreceive(9) # skip these for now I have no idea what these do just yet

        #GET STANDBY TIME
        ack =  b'\x01\x04\x03\x01' # check if im in the correct location in the sent bytes
        check = myreceive(5)
        if check[0:4] != ack:
            print("error")
            
        self.standby = check[4]
        #print(self.standby, "Minutes until standby")

        # get noise cancel level
        ack = b'\x01\x06\x03\x02\x00\x0b'
        check = myreceive(6)
        self.noiseCancellation = check[4]
        myreceive(19) # whatever this is?

    def get_device_serial(self):
        send = b'\x00\x07\x01\x00'
        ack = b'\x00\x07\x03'
        mysend(send)
        if myreceive(3) != ack:
            print("ERROR: could not get device serial number")
            return
        
        length = int.from_bytes(myreceive(1), 'little')
        self.serialNumber = myreceive(length).decode('utf-8')

    def get_device_firmware(self):
        send = b'\x00\x05\x01\x00'
        ack = b'\x00\x05\x03\x05'
        mysend(send)
        if myreceive(len(ack)) != ack:
            print("ERROR: could not get device firmware version")
            return

        self.firmwareVersion = myreceive(5).decode('utf-8')

    def get_device_id(self):
        send = b'\x00\x03\x01\x00'
        ack = b'\x00\x03\x03\x03'
        mysend(send)
        if myreceive(4) != ack:
            print("erorr")
            return 1 
        self.deviceId = hex(int.from_bytes(myreceive(2), 'big'))  # stupid python but its okay it works
        self.Indexrevision = int.from_bytes(myreceive(1), 'little')

    def get_battery_level(self):
        send = b'\x02\x02\x01\x00'
        ack = b'\x02\x02\x03\x01'
        mysend(send)
        ret_val = myreceive(4)
        if ret_val != ack:
            print("Error, could not resolve", ack,ret_val)
            return 1
        return int.from_bytes(myreceive(1), 'big')
    
    def get_paired_devices(self):
        send = b'\x04\x04\x01\x00' # should contain information on the connected devices
        ack = b'\x04\x04\x03'
        mysend(send)
        if ack != myreceive(3):
            print("error")
        BT_ADDRESS_LEN  = 6
        self.numDevices = ((myreceive(1)[0] -1 ) // BT_ADDRESS_LEN)
        self.numConnectedDevices = int.from_bytes(myreceive(1), 'little') - 1
        #print("Number of paired devices:",self.numDevices)
        AllDeviceAddrs = []
        for i in range(self.numDevices):
            currDev = myreceive(BT_ADDRESS_LEN)
            currDevAddr = ""
            for i in currDev:
                currDevAddr += str(hex(i))[2:].upper() + ":"
            AllDeviceAddrs.append(currDevAddr[:-1])
        self.connectedDevicesAddrs = AllDeviceAddrs
    
    def set_noise_cancellation_level(self,level):
        high = b'\x01\x06\x02\x01\x01'
        low = b'\x01\x06\x02\x01\x03'
        off = b'\x01\x06\x02\x01\x00'
        if level == "high":
            mysend(high)
        elif level == "low":
            mysend(low)
        elif level == "off":
            mysend(off)
        self.noiseCancellation = myreceive(6)[4]

    def set_name(self,newName):
      return  

def get_bose_device_addrs():
    bus = pydbus.SystemBus()
    adapter = bus.get('org.bluez', '/org/bluez/hci0')
    mngr = bus.get('org.bluez', '/')

    all_bose_devices=[]
    mngd_objs = mngr.GetManagedObjects()
    for path in mngd_objs:
        con_state = mngd_objs[path].get('org.bluez.Device1', {}).get('Connected', False)
        if con_state:
            addr = mngd_objs[path].get('org.bluez.Device1', {}).get('Address')
            if "4C:87:5D" == addr[0:8]: # if bose device
                all_bose_devices.append(addr)
    return all_bose_devices

def _seconds_to_sockopt_format(seconds):
    """Convert floating point seconds value to second/useconds struct used by UNIX socket library.
    For Windows, convert to whole milliseconds.
    """
    if os.name == "nt":
        return int(seconds * 1000)
    else:
        microseconds_per_second = 1000000
        whole_seconds = int(math.floor(seconds))
        whole_microseconds = int(math.floor((seconds % 1) * microseconds_per_second))
        return struct.pack("ll", whole_seconds, whole_microseconds)

def mysend(msg):
    totalsent = 0
    while totalsent < len(msg):
        sent = sock.send(msg[totalsent:])
        if sent == 0:
            raise RuntimeError("socket connection broken")
        totalsent = totalsent + sent

def myreceive(MSGLEN):
    chunks = []
    bytes_recd = 0
    while bytes_recd < MSGLEN:
        chunk = sock.recv(min(MSGLEN - bytes_recd, 2048))
        if chunk == b'':
            raise RuntimeError("socket connection broken")
        chunks.append(chunk)
        bytes_recd = bytes_recd + len(chunk)
    return chunk 

def connect_and_init(device_num):
    ret = sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDTIMEO, _seconds_to_sockopt_format(5))
    if ret:
        print ("Could not set socket send timeout")
        return 1
    ret = sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVTIMEO, _seconds_to_sockopt_format(1))
    if ret:
        print (" could not recieve socet in time")
        return 1
    sock.connect((device[device_num],8))

    send_data = b'\x00\x01\x01\x00'
    mysend(send_data)
    myreceive(4+5) # throw away Do not use for now, contains the firmware version of something I don't understand just yet
    #get_paired = bytearray([0x04, 0x04, 0x01, 0x00])

sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
adapter = subprocess.check_output(['hciconfig']).decode('utf-8')
adapter = adapter[(adapter.find('BD Address')+12):(adapter.find('BD Address')+12+17)]
device = get_bose_device_addrs() if len(get_bose_device_addrs()) > 0 else -1

def main():
    if device == -1:
        print("No bose device(s) found")
        return 1
    for i in range(len(device)):
        connect_and_init(i)
        Device = BoseQC35ii()
        Device.get_device_info()
        print(Device.name + ": " + str(Device.get_battery_level()) + "%")
        print("Noise cancel level:", Device.noiseCancellation)
        Device.get_device_id()
        print("Device ID:",Device.deviceId)
        Device.get_paired_devices()
        print("Number of currently conencted devices:",Device.numConnectedDevices)
        print("total number of paired devices:",Device.numDevices)
        print("Connected device addrs:", Device.connectedDevicesAddrs)
        Device.get_device_serial()
        print("Serial number:", Device.serialNumber)
        Device.get_device_firmware()
        print("Firmware version:",Device.firmwareVersion)
        #Device.set_noise_cancellation_level("low")
        sock.close()

if __name__ == "__main__":
    main()  