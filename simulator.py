#!/usr/bin/python
import struct
import socket
import board

class Simulator():
    def __init__(self, port=board.NET_PORT):
        self.sock = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        self.host = ("", port)
        self.clear()
        self.print_display()

    def print_display(self):
        print "%c[0;0H" % 27
        border="+"
        for i in range(board.DSP_WIDTH):
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
        for i in range(board.DSP_HEIGHT):
            l=[]
            for j in range(board.DSP_WIDTH):
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
        #print command, x, y, width, height, data, len(data)
        if command in (board.CMD_CLEAR, board.CMD_RESET, board.CMD_HARDRESET):
            self.clear()
        elif command == board.CMD_INTENSITY:
            self.intensity(struct.unpack("b", data))
        elif command == board.CMD_WRITE_LUM_RAW:
            self.display_luminance(x, y, width, height, data)
        elif command == board.CMD_WRITE_RAW:
            self.display_chars(x, y, width, height, data)
        reply= \
            struct.pack("HHHHH", board.CMD_ACK, x, y, width, height) \
            + data \
            + struct.pack("b", 0)
        self.sock.sendto(reply, client)
    def listen(self):
        print "%c[2J" % 27
        self.sock.bind(self.host)
        while True:
            self.receive()
            self.print_display()

if __name__=="__main__":
    s = Simulator()
    s.listen()
