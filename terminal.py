#!/usr/bin/python

import pty
import os, sys
import termios
import subprocess
import select
import fcntl
import struct
import random
import string
import copy
import board
import time
import signal

ANSI_ESC=27
ANSI_CARRIAGE_RETURN=13
ANSI_BACKSPACE=8

PRINTABLE_CHARS=string.letters+string.digits+string.punctuation+" "

def gendisplay():
    d = []
    for i in range(board.DSP_HEIGHT):
        l=[]
        for j in range(board.DSP_WIDTH):
            l.append([" ", 0])
        d.append(l)
    return d

class Terminal:
    def signal_handler(self, s, frame):
        print "^C received."
        os.write(self.master, chr(3))
        return signal.SIG_IGN
    def __init__(self):

        self.visual_cursor=["_", 7]


        signal.signal(signal.SIGINT, self.signal_handler)
        self.cursor_blink_interval=0.5
        self.cursor_blink_state=0 

        #self.master, self.slave = os.openpty()
        slavepid, self.master = pty.fork()
        if slavepid==0:
            os.environ["TERM"]="vt100"
            os.execl(os.environ["SHELL"], "")

        self.term = os.fdopen(self.master, "r", 0)

        # setup local
        attr = termios.tcgetattr(sys.stdin)
        attr[3] &= ~( termios.ICANON | termios.ECHO )
        termios.tcsetattr(sys.stdin, termios.TCSANOW, attr)


        # setup remote side
        fcntl.ioctl(self.master, termios.TIOCSWINSZ,
            struct.pack("hhhh", board.DSP_HEIGHT, board.DSP_WIDTH, 0, 0))

        #self.shell = subprocess.Popen(os.environ["SHELL"],
        #    stdin=self.slave,
        #    stdout=self.slave,
        #    stderr=self.slave, bufsize=0)

        attr = termios.tcgetattr(self.master)
        attr[3] &= ~termios.ICANON
        termios.tcsetattr(self.master, termios.TCSAFLUSH, attr)

        self.board=board.Board()
        self.cursor=[0,0]
        self.multichar_buffer=""

        self.reset_style()
        self.clear()
        
        # this fixes carriage returns as last character in a line (width +
        # 1st).. only \n and any escape sequence reset this variable.. (and
        # carriage return itself)
        self.last_wrapped=False
    
    def clear(self):
        self.display=gendisplay()
        self.board.clear()
        self.transmitted_display=gendisplay()
        self.cursor_visible=True
        self.scroll_range=[0, board.DSP_HEIGHT-1]
        self.board.clear();
        self.board.set_luminance(0)


    def delta_transmit(self):
        self.delta_transmit_old()

    def delta_transmit_old(self):
        try:
            for i in range(board.DSP_HEIGHT):
                for j in range(board.DSP_WIDTH):
                    t = self.transmitted_display[i][j]
                    n = self.display[i][j]
                    if t[1]!=n[1]:
                        self.board.display_luminance([[n[1]]], x=j, y=i)
                        t[1]=n[1]
                    if t[0]!=n[0]:
                        self.board.display_chars([[n[0]]], x=j, y=i)
                        t[0]=n[0]
        except select.error:
            pass

    def scroll_down(self):
        #self.display=self.display[1:len(self.display)]
        # append new line
        l=[]
        for i in range(board.DSP_WIDTH):
            l.append([" ", board.LUM_MAX])
        #self.display.append(l)
        self.display.pop(self.scroll_range[0])
        self.display.insert(self.scroll_range[1], l)
        
        self.board.display(self.display)
        self.transmitted_display=copy.deepcopy(self.display)

    def new_line(self, wrap=False):
        self.cursor[0]=0
        self.last_wrapped=wrap
        if self.cursor[1]>=(self.scroll_range[1]):
            self.scroll_down()
        else:
            self.cursor[1]+=1

    def cursor_incr(self):
        if self.cursor[0]>=(board.DSP_WIDTH-1):
            self.new_line(True)
        else:
            self.cursor[0]+=1
    
    def clear_line(self):
        for i in range(board.DSP_WIDTH-self.cursor[0]):
            try:
                self.display[self.cursor[1]][self.cursor[0]+i]=[" ", board.LUM_MAX]
            except:
                pass
    
    def clear_downwards(self):
        self.clear_line()
        self.display=self.display[0:self.cursor[1]+1]
        self.display+=gendisplay()[0:board.DSP_HEIGHT-self.cursor[1]-1]


    def reset_style(self):
        # colors are greyscale between board.LUM_MIN and MAX
        self.style_lum=board.LUM_MAX

    def style(self, key):
        try:
            key=int(key)
        except:
            key=0
        if key==0:
            self.reset_style()
        elif 30<=key<=37:
            col=key-30
            if col==7: # white
                self.style_lum=7
            elif col==6:
                self.style_lum=3
            elif col==5:
                self.style_lum=3
            elif col==4:
                self.style_lum=3
            elif col==3:
                self.style_lum=3
            elif col==2:
                self.style_lum=3
            elif col==1:
                self.style_lum=3
            else:
                print "broop", col
                self.style_lum=7
            self.style_lum=15
        else:
            print "UNHANDLED", key
    def scroll_up(self):
        l=[]
        for i in range(board.DSP_WIDTH):
            l.append([" ", 0])

        self.display.pop(self.scroll_range[1])
        self.display.insert(self.scroll_range[0], l)
        
        self.board.display(self.display)
        self.transmitted_display=copy.deepcopy(self.display)
        
    def process_escape_sequence(self, sequence):
        s = sequence[1:len(sequence)]
        cmd = sequence[len(sequence)-1]
        arg = s[1:len(s)-1]
        unhandled=0
        self.last_wrapped=False
        if s.startswith("?"):
            # drop that ^^
            return

        if cmd=="m": # character style
            for a in arg.split(";"):
                if a=="":
                    continue
                self.style(a)
        elif cmd=="K":
            self.clear_line()
        elif cmd=="r":
            try:
                b, e = arg.split(";")
                try:
                    b=int(b)-1
                    e=int(e)-1
                except:
                    print "ooops"
                print "nu scroll range", cmd, arg
                self.scroll_range=[b, e]
            except:
                self.scroll_range=[0, board.DSP_HEIGHT-1]
        elif cmd=="h" and arg=="?25":
            self.cursor_visible=True
        elif cmd=="l" and arg=="?25":
            self.cursor_visible=False
        elif cmd=="B":
            if arg=="":
                arg=1
            self.cursor[1]+=int(arg)
        elif cmd=="M": # scroll up 1 line
            self.scroll_up()
        elif cmd=="C": # move cursor forward
            try:
                self.cursor[0]+=int(arg)
            except:
                self.cursor[0]+=1
        elif cmd=="D": # move cursor backward
            self.cursor[0]-=int(arg)
        elif cmd=="G":
            self.cursor[0]=int(arg)
        elif cmd=="A": # move cursor UP
            if arg=="":
                arg=1
            self.cursor[1]-=int(arg)
        elif cmd in ("H", "f"):
            if len(arg)==0:
                self.cursor=[0,0]
            else:
                try:
                    y,x=arg.split(";")
                    if x=="" and y=="":
                        self.cursor=[0,0]
                    else:
                        self.cursor=[int(x)-1, int(y)-1]
                except:
                    pass
        elif cmd=="J": # clear
            i=0
            if arg!="":
                try:
                    i=int(arg)
                except:
                    pass
                    #print arg
            if i==1:
                unhandled="Clear upwards"
            elif i==0:
                self.clear_downwards()
            elif i==2:
                self.clear()
        else:
            unhandled="Unknown"
        
        if unhandled:
            print "Unhandled escape sequence: cmd=%s, arg=%s (%s)" % (cmd,
                arg, unhandled)

    def char_processor(self, char):
        if self.multichar_buffer=="":
            if char in PRINTABLE_CHARS:
                try:
                    self.display[self.cursor[1]][self.cursor[0]]= \
                        [char, self.style_lum]
                    self.cursor_incr()
                except:
                    pass
            elif ord(char)==ANSI_ESC:
                self.multichar_buffer+=char
            elif ord(char) == ANSI_CARRIAGE_RETURN:
                if self.cursor[0]==0 and self.last_wrapped:
                    self.cursor[1]-=1
                    self.last_wrapped=False
                self.cursor[0]=0
            elif char=="\n":
                self.new_line()
            elif ord(char) == ANSI_BACKSPACE:
                self.cursor[0]-=1
                self.display[self.cursor[1]][self.cursor[0]]=[" ", 0]
            else:
                print "Unhandled character code:", ord(char)
            self.delta_transmit()
        else:
            # process escape sequences
            self.multichar_buffer+=char
            if char in string.letters:
                self.process_escape_sequence(self.multichar_buffer)
                self.delta_transmit()
                self.multichar_buffer=""
            if len(self.multichar_buffer)>10:
                print "Multichar buffer overflow:", self.multichar_buffer
                self.multichar_buffer=""
                sys.exit(1)
    
    def cursor_refresh(self):
        if not self.cursor_visible: return
        if self.cursor_blink_state:
            self.board.display([[self.visual_cursor]],
                self.cursor[0], self.cursor[1])
            self.transmitted_display[self.cursor[1]][self.cursor[0]]=\
                copy.copy(self.visual_cursor)
        else:
            self.delta_transmit()

    def run(self):
        self.last_blink=0
        while(True):
            timeout = self.last_blink-time.time()+self.cursor_blink_interval
            if timeout < 0:
                timeout = 0
            try:
                rl = select.select([sys.stdin, self.term], [], [], timeout)[0]
            except:
                # The keyboard interrupt (^C) is handled by passing a certain
                # character to the pty master - nothing to do here 
                pass

            if rl==[]: # and time.time()-self.last_blink>self.cursor_blink_interval:
                self.last_blink=time.time()
                print "DELTA TRANSMISSION!"
                self.delta_transmit()
                if self.cursor_blink_state:
                    self.cursor_blink_state=False
                else:
                    self.cursor_blink_state=True
                self.cursor_refresh()

            for r in rl:
                if r==sys.stdin:
                    c = os.read(0,1)
                    if c==27:
                        os.write(self.master, c)
                    else:
                        #print ord(c)
                        os.write(self.master,c)
                elif r==self.term:
                    try:
                        c = os.read(self.master, 1)
                    except:
                        print "EOF read - cleaing up - bye"
                        self.board.clear()
                        return
                    self.char_processor(c)
                    self.cursor_blink_state=True
                    self.last_blink=0

if __name__=="__main__":
    t=Terminal()
    t.run()
