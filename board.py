#!/usr/bin/python
import socket
import struct
import select
import time
import random
CMD_ACK=0
CMD_NAK=1 
CMD_CLEAR=2 # DONE
CMD_WRITE_RAW=3 # DONE
CMD_WRITE_STD=4 # DONE
CMD_WRITE_LUM_RAW=5 # DONE
CMD_WRITE_LUM_STD=6 # DONE
CMD_INTENSITY=7 # DONE
CMD_RESET=8 # DONE
CMD_READ_RAW=9
CMD_READ_LUM_RAW=10
CMD_HARDRESET=11 # DONE

LUM_MAX=8
LUM_MIN=0
DSP_HEIGHT = 20
DSP_WIDTH = 56

NET_PORT=2342
#NET_HOST="172.23.42.120"
NET_HOST="localhost"


class Simulator():
    def __init__(self, port=NET_PORT):
        self.sock = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        self.host = ("", port)
        self.clear()
        self.print_display()

    def print_display(self):
        print "%c[0;0H" % 27
        border="+"
        for i in range(DSP_WIDTH):
            border+="-"
        border+="+"
        print border
        for r in self.display:
            line="|"
            for c in r:
                if c[1]<1:
                    line+=" "
                    continue
                elif c[1]<4:
                    color=4
                elif c[1]<12:
                    color=3
                else:
                    color=7
                line+=("%c[3%sm" % (27, str(color))) + c[0]
            line+="%c[37m|" % 27
            print line
        print border

    def clear(self):
        self.display = []
        for i in range(DSP_HEIGHT):
            l=[]
            for j in range(DSP_WIDTH):
                l.append([" ", 0])
            self.display.append(l)

    def intensity(self, lum):
        for r in self.display:
            for c in r:
                c[1]=lum

    def display_chars(self, x, y, width, height, data):
        i=0
        for c in data:
            cur_x = x+i%width
            cur_y = y+i/width
            self.display[cur_y][cur_x][0]=c
            i=i+1

    def display_luminance(self, x, y, width, height, data):
        i=0
        for c in data:
            cur_x = x+i%width
            cur_y = y+i/width
            self.display[cur_y][cur_x][1]=struct.unpack("b", c)[0]
            i=i+1

    def receive(self):
        message, client = self.sock.recvfrom(2048)
        command, x, y, width, height = struct.unpack("HHHHH", message[0:10]) 
        data = message[10:len(message)-1]
        print command, x, y, width, height, data, len(data)
        if command in (CMD_CLEAR, CMD_RESET, CMD_HARDRESET):
            self.clear()
        elif command == CMD_INTENSITY:
            self.intensity(struct.unpack("b", data))
        elif command == CMD_WRITE_LUM_RAW:
            self.display_luminance(x, y, width, height, data)
        elif command == CMD_WRITE_RAW:
            self.display_chars(x, y, width, height, data)
        reply= \
            struct.pack("HHHHH", CMD_ACK, x, y, width, height) \
            + data \
            + struct.pack("b", 0)
        self.sock.sendto(reply, client)
    def listen(self):
        print "%c[2J" % 27
        self.sock.bind(self.host)
        while True:
            self.receive()
            self.print_display()
class Board:
    def __init__(self, host=NET_HOST, port=NET_PORT):
        self.sock = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        self.host = (host, port)
        self.timeout = 3 # seconds

    def write(self, text, x=0, y=0, lum=-1):
        """Writes some string to board - use display_chars instead!"""
        if lum > -1: # -1 = dont change
            self.send(CMD_WRITE_LUM_STD, data=struct.pack("b", lum))
        self.send(CMD_WRITE_STD, x, y, 1, 1, text)
    
    def reset(self, hard=False):
        if hard:
            self.send(CMD_HARDRESET);
        else:
            self.send(CMD_RESET);

    def set_luminance(self, lum):
        """Globally sets luminance of all cells"""
        self.send(CMD_INTENSITY, data=struct.pack("b", lum))

    def display(self, buffer, x=0, y=0):
        """Don't use this lame function."""
        lum_array=[]
        char_array=[]
        for r in buffer:
            lr=[]
            cr=[]
            for c in r:
                cr.append(c[0])
                lr.append(c[1])
            lum_array.append(lr)
            char_array.append(cr)
        self.display_luminance(lum_array, x, y)
        self.display_chars(char_array, x, y)

    def display_luminance(self, buffer, x=0, y=0):
        """Set luminance for sepecific cells.
        example: [["a", "b", "c"], ["d", "b", "f"]]"""
        columns = len(buffer[0])
        # TODO: Check type!
        rows = len(buffer)
        data = ""
        for r in buffer:
            for c in r:
                data+=struct.pack("b", c)
        self.send(CMD_WRITE_LUM_RAW, x, y, columns, rows, data)

    def display_chars(self, buffer, x=0, y=0):
        """example: [["a", "b", "c"], ["d", "b", "f"]]"""
        columns = len(buffer[0])
        # TODO: Check type!
        rows = len(buffer)
        data = ""
        for r in buffer:
            for c in r:
                data+=c
        self.send(CMD_WRITE_RAW, x, y, columns, rows, data)
        
    def clear(self):
        self.send(CMD_CLEAR)
        self.set_luminance(LUM_MAX)

    def send(self, command, x=0, y=0, width=0, height=0, data=""):
        """returns 0 if successful, 1 if timed out"""
        message= \
            struct.pack("HHHHH", command, x, y, width, height) \
            + data \
            + struct.pack("b", 0)
        self.sock.sendto(message,self.host)
        r, w, x = select.select([self.sock], [], [],3)
        # reset has no answer
        if command in (CMD_HARDRESET, CMD_RESET):
            return 0
        if r==[]:
            print "No answer received.... x("
            return 1
        else:
            answer, host = self.sock.recvfrom(4096)
        return 0

def brightness_demo():
    b=Board()
    b.clear()
    img=[]
    for i in range(16):
        img.append((str(i)[0], i))
        if i>=10:
            img.append((str(i%10), i))
        img.append((" ", 0))
    b.display([img])

def ccc_screensaver_demo():
    b=Board()
    while True:
        b.clear()
        x=random.choice(range(DSP_WIDTH-5))
        y=random.choice(range(DSP_HEIGHT-3))
        #b.display_chars([
        #    ["C", ":", ":", " ", " "],
        #    [" ", ":", "C", ":", " "],
        #    [" ", " ", ":", ":", "C"]
        #    ], x, y)
        #b.display_luminance([
        #    [15, 4, 4, 0, 0],
        #    [0, 4, 15, 4, 0],
        #    [0, 0, 4, 4, 15]
        #    ], x, y)
        b.display([
            [["C", 15], [":", 4], [":", 4], [" ", 0], [" ", 0]],
            [[" ", 0], [":", 4], ["C", 15], [":", 4], [" ", 0]],
            [[" ", 0], [" ", 0], [":", 4], [":", 4], ["C", 14]]
            ], x, y)
        time.sleep(2)

if __name__=="__main__":
    ccc_screensaver_demo()
