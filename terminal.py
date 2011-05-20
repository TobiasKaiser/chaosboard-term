#!/usr/bin/python
import pty
import os, sys
import curses
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
import getopt

class Buffer:
    def __init__(self):
        self.char = []
        self.lum = []
        self.latency=-1
        for i in range(board.DSP_HEIGHT):
            ll=[]
            cl=[]
            for j in range(board.DSP_WIDTH):
                ll.append(0)
                cl.append(" ")
            self.char.append(cl)
            self.lum.append(ll)

    def curses_render(self, window):
        """Respects border."""
        for i in range(board.DSP_HEIGHT):
            for j in range(board.DSP_WIDTH):
                window.addch(i+1,j+1, ord(self.char[i][j]))
        window.refresh()

    def getcell_compat(self, row, col):
        return [self.char[row][col], self.lum[row][col]]

    def setcell_compat(self, row, col, cell):
        self.char[row][col]=cell[0]
        self.lum[row][col]=cell[1]

class TermBuffer(Buffer):
    def delta_transmit(self, bd, previous, colored=False):
        t=time.time()
        self.nu_delta_transmit(bd, previous, colored)
        self.latency=time.time()-t

    def nu_delta_transmit(self, bd, previous, colored):
        bd.display_chars(self.char)
        if colored: bd.display_luminance(self.lum)

    def old_delta_transmit(self, bd, previous, colored):
        for i in range(board.DSP_HEIGHT):
            for j in range(board.DSP_WIDTH):
                t = previous.getcell_compat(i, j)
                n = self.getcell_compat(i, j)
                if t[0]!=n[0]:
                    bd.display_chars([[n[0]]], x=j, y=i)
                    t[0]=n[0]
                if not colored: continue
                if t[1]!=n[1]:
                    bd.display_luminance([[n[1]]], x=j, y=i)
                    t[1]=n[1]

    def clear_down(self, cursor):
        # this might be buggy
        for i in range(board.DSP_HEIGHT-cursor[1]-1):
            for j in range(board.DSP_WIDTH):
                self.setcell_compat(cursor[1]+i, j, [" ", 0])

    def clear_line(self, cursor):
        for i in range(board.DSP_WIDTH-cursor[0]):
            try:
                self.setcell_compat(cursor[1], cursor[0]+i,[" ", board.LUM_MAX])
            except: pass
    
    def scroll(self, scroll_range):
        # append new line
        lc=[]
        ll=[]
        for i in range(board.DSP_WIDTH):
            lc.append(" ")
        for i in range(board.DSP_WIDTH):
            ll.append(0)
        self.char.pop(scroll_range[0])
        self.char.insert(scroll_range[1], lc)
        self.lum.pop(scroll_range[0])
        self.lum.insert(scroll_range[1], ll)

    def scroll_up(self, scroll_range):
        lc=[]
        ll=[]
        for i in range(board.DSP_WIDTH):
            ll.append(0)
            lc.append(" ")

        self.lum.pop(scroll_range[1])
        self.lum.insert(scroll_range[0], ll)
        self.char.pop(scroll_range[1])
        self.char.insert(scroll_range[0], lc)

class Terminal:
    def __init__(self):
        self.debug_mode=False
        self.debug_no=0
        self.colored=False
        self.fps=30
        self.style2lum_dict={0:10, 7:10, # white
            6:3, 5:3, 4:3, 3:3, 2:3, 1:3}
        #self.visual_cursor=["\xdb", 7] # block cursor
        self.visual_cursor=["_", 7]

        self.cursor_blink_interval=0.5
        self.cursor_blink_state=0 

        self.slave, self.master = pty.fork()
        if self.slave==0:
            os.environ["DISPLAY"]=""
            os.environ["TERM"]="xterm"
            os.execl(os.environ["SHELL"], "")

        self.term = os.fdopen(self.master, "r", 0)

        fcntl.ioctl(self.master, termios.TIOCSWINSZ,
            struct.pack("hhhh", board.DSP_HEIGHT, board.DSP_WIDTH, 0, 0))

        attr = termios.tcgetattr(self.master)
        attr[3] &= ~termios.ICANON
        termios.tcsetattr(self.master, termios.TCSAFLUSH, attr)

        self.cursor=[0,0]
        self.multichar_buffer=""

        self.style_lum=self.style2lum_dict[7]

        self.transmitted_display=TermBuffer()
        self.clear()
        
        # this fixes carriage returns as last character in a line (width +
        # 1st).. only \n and any escape sequence reset this variable.. (and
        # carriage return itself)
        self.last_wrapped=False

    def connect(self, host, port, dry_run=False):
        self.board=board.Board(host, port, dry_run=dry_run)
    
    def handler_sigint(self, s, frame): # ^C received
        os.write(self.master, "\x03")
        return signal.SIG_IGN

    def clear(self):
        self.display=TermBuffer()
        self.cursor_visible=True
        self.scroll_range=[0, board.DSP_HEIGHT-1]

    def delta_transmit(self):
#        self.debug("update.")
        self.display.delta_transmit(self.board, self.transmitted_display,
            self.colored)
        self.transmitted_display=copy.deepcopy(self.display)
        self.display.curses_render(self.win_term)

    def new_line(self, wrap=False):
        self.cursor[0]=0
        self.last_wrapped=wrap
        if self.cursor[1]>=(self.scroll_range[1]):
            self.display.scroll(self.scroll_range)
        else:
            self.cursor[1]+=1

    def cursor_incr(self):
        if self.cursor[0]>=(board.DSP_WIDTH-1):
            self.new_line(True)
        else:
            self.cursor[0]+=1
    
    def style(self, key):
        try:
            key=int(key)
        except:
            key=0
        if key==0:
            self.style_lum=self.style2lum_dict[7]
        elif 30<=key<=37:
            col=key-30
            self.style_lum=self.style2lum_dict[col] 
        
    def process_escape_sequence(self, sequence):
        s = sequence[1:len(sequence)]
        cmd = sequence[len(sequence)-1]
        arg = s[1:len(s)-1]
        unhandled=0
        self.last_wrapped=False
        if s.startswith("?"): # drop that ^^
            return

        if cmd=="m": # character style
            for a in arg.split(";"):
                if a=="":
                    continue
                self.style(a)
        elif cmd=="K":
            self.display.clear_line(self.cursor)
        elif cmd=="r":
            try:
                b, e = arg.split(";")
                try:
                    b=int(b)-1
                    e=int(e)-1
                    self.scroll_range=[b, e]
                except: pass
            except:
                self.scroll_range=[0, board.DSP_HEIGHT-1]
        elif cmd=="h" and arg=="?25":
            self.cursor_visible=True
        elif cmd=="l" and arg=="?25":
            self.cursor_visible=False
        elif cmd=="B":
            if arg=="":
                arg=1
            try:
                self.cursor[1]+=int(arg)
            except: pass
        elif cmd=="M": # scroll up 1 line
            self.display.scroll_up(self.scroll_range)
        elif cmd=="C": # move cursor forward
            try:
                self.cursor[0]+=int(arg)
            except:
                self.cursor[0]+=1
        elif cmd=="D": # move cursor backward
            self.cursor[0]-=int(arg)
        elif cmd=="G":
            try: self.cursor[0]=int(arg)
            except: pass
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
                except: pass
        elif cmd=="J": # clear
            i=0
            if arg!="":
                try:
                    i=int(arg)
                except: pass
            if i==1:
                unhandled="Clear upwards"
            elif i==0:
                self.display.clear_down(self.cursor)
            elif i==2:
                self.clear()
        else:
            unhandled="Unknown"
        
        if unhandled:
            self.debug("Unhandled escape sequence: cmd=%s, arg=%s (%s)" %
                (cmd, arg, unhandled))

    def char_processor(self, char):
        if self.multichar_buffer=="":
            if char in string.letters+string.digits+string.punctuation+" ":
                try:
                    self.display.setcell_compat(self.cursor[1],
                        self.cursor[0], [char.encode("CP437"), self.style_lum])
                    self.cursor_incr()
                except: pass
            elif char=="\x1b": # ANSI Escape
                self.multichar_buffer+=char
            elif char=="\r":
                if self.cursor[0]==0 and self.last_wrapped:
                    self.cursor[1]-=1
                    self.last_wrapped=False
                self.cursor[0]=0
            elif char=="\n":
                self.new_line()
            elif char=="\b":
                self.cursor[0]-=1
            else:
                self.debug("Unknown char %02x"%ord(char))
        else:
            # process escape sequences
            self.multichar_buffer+=char
            if char in string.letters:
                self.process_escape_sequence(self.multichar_buffer)
                self.multichar_buffer=""
            if len(self.multichar_buffer)>10:
                print "Multichar buffer overflow:", self.multichar_buffer
                self.multichar_buffer=""
                sys.exit(1)
    
    def cursor_refresh(self):
        if not self.cursor_visible: return
        if self.cursor_blink_state:
            temp_display=copy.deepcopy(self.display)
            try:
                self.display.setcell_compat(self.cursor[1], self.cursor[0],
                    self.visual_cursor)
                self.delta_transmit()
                self.display=temp_display
            except: pass
        else:
            self.delta_transmit()
        
    def stat_refresh(self):
        if not time.time()>self.last_stat+1:
            return
        self.last_stat=time.time()
        self.status_print("Bytes: %sb/5s\tLatency: %.1fms"
            %(sum(self.stat_outbits), self.display.latency*1000))
        self.stat_outbits=self.stat_outbits[:len(self.stat_outbits)-1]
        self.stat_outbits.insert(0, 0) 
         

    def debug(self,message):
        message=str(message)
        if not self.debug_mode: return
        self.win_debug.scroll(-1)
        self.win_debug.addstr(0,0,str(self.debug_no)+' '+message)
        self.win_debug.refresh()
        self.debug_no+=1

    def status_print(self, text):
        self.win_status.addstr(0,0," "*2*len(self.status_string))
        self.status_string=text
        self.win_status.addstr(0,0,self.status_string)
        self.win_status.refresh()

    def curses_init(self, stdscr):
        self.last_stat=time.time()
        self.status_string=""
        self.stat_interval=5
        self.stat_outbits=[0]*int(self.stat_interval/self.cursor_blink_interval)
        curses.start_color()
        curses.noecho()
        curses.cbreak()
        curses.curs_set(0)
        curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_CYAN)
        curses.init_pair(2, curses.COLOR_WHITE, curses.COLOR_RED)
        curses.init_pair(3, curses.COLOR_WHITE, curses.COLOR_BLACK)
        theight,twidth=stdscr.getmaxyx()

        if(self.debug_mode):
            self.win_term=curses.newwin(board.DSP_HEIGHT+2, board.DSP_WIDTH+2,
                (theight-board.DSP_HEIGHT)/2-1, 0)

            dw1=curses.newwin(theight-1, twidth-2-board.DSP_WIDTH,
                0, board.DSP_WIDTH+2)
            dw1.bkgd(' ', curses.color_pair(2))
            dw1.border()
            dw1.refresh()
            self.win_debug=dw1.derwin(theight-1-2, twidth-2-2-board.DSP_WIDTH,
                1, 1)
            self.win_debug.bkgd(' ', curses.color_pair(2))
            self.win_debug.refresh()
            self.win_debug.scrollok(True)

        else:
            self.win_term=curses.newwin(board.DSP_HEIGHT+2, board.DSP_WIDTH+2,
                (theight-board.DSP_HEIGHT)/2-1, (twidth-board.DSP_WIDTH)/2-1)

        self.win_term.bkgd(' ', curses.color_pair(1))
        self.win_term.border()

        self.win_prompt=curses.newwin(1, twidth, theight-2, 0)

        self.win_status=curses.newwin(1, twidth, theight-1, 0)
        self.win_status.bkgd(' ', curses.color_pair(3))

    def run(self, stdscr):
        self.curses_init(stdscr)
        self.status_print("Connecting...")
        time.sleep(.5)
        self.board.clear() 
        self.board.set_luminance(7)
        signal.signal(signal.SIGINT, self.handler_sigint)
        
        self.prompt_buffer=""

        input_state="term"        

        last_update=time.time()
        self.last_blink=0
        while(True):
            timeout = self.last_blink-time.time()+self.cursor_blink_interval
            if timeout < 0: timeout=0
            try:
                rl = select.select([sys.stdin, self.term], [], [], timeout)[0]
            #except KeyboardInterrupt:
            #    pass # work is done by handler_sigint
            #except select.error: # Interrupted system call, esp. by SIGWINCH
            #    continue
            except: continue
            #self.debug(self.scroll_range)
            self.stat_refresh()
            if rl==[]: # timeout for blinking cursor
                self.last_blink=time.time()
                self.cursor_refresh()
                last_update=time.time()
                if self.cursor_blink_state:
                    self.cursor_blink_state=False
                else:
                    self.cursor_blink_state=True
                continue

            for r in rl:
                if r==sys.stdin:
                    c = os.read(0,1)
                    if input_state=="term":
                        if(ord(c)==23): # ^W
                            input_state="com"
                        else:
                            os.write(self.master,c)
                    else:
                        if c=='\n':
                            self.prompt_buffer=""
                        else:
                            self.prompt_buffer+=c
                        self.win_prompt.clear()
                        self.win_prompt.addstr(0,0, self.prompt_buffer)
                        self.win_prompt.refresh()
                        self.prompt_buffer
                        
                elif r==self.term:
                    try:
                        c = os.read(self.master, 1)
                        self.stat_outbits[0]+=1
                    except:
                        self.board.clear()
                        return # end of terminal life
                    self.char_processor(c)
                    self.cursor_blink_state=True
                    self.last_blink=0

            if(time.time()-last_update>(1.0/self.fps)):
                self.delta_transmit()
                last_update=time.time()
            

def usage():
    print "Usage: terminal.py [host] [-c|--colored] [-d|--debug] [-p|--port]"
    print

def main():
    t=Terminal()
    port=board.NET_PORT
    host=board.NET_HOST
    dry_run=False
    try:
        opts, args=getopt.gnu_getopt(sys.argv[1:],
            "hcdp:y", ("help", "colored", "debug", "port=", "dry-run"))
    except getopt.GetoptError, err:
        print str(err)
        usage()
        sys.exit(1)
    if(len(args)==1):
        host=args[0]
    if(len(args)>1):
        usage()
        sys.exit(1)
    for o, a in opts:
        if o in ("-h", "--help"): usage(); return
        if o in ("-c", "--colored"): t.colored=True
        if o in ("-p", "--port"): port=a
        if o in ("-d", "--debug"): t.debug_mode=True
        if o in ("-r", "--remote"): host=a
        if o in ("-y", "--dry-run"): dry_run=True
    t.connect(host, port, dry_run)
    curses.wrapper(t.run)
    
if __name__=="__main__": main()
