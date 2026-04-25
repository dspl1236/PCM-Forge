#!/usr/bin/env python3
"""PCM-Forge Remote Shell — Execute commands on PCM 3.1 via telnet.

Usage:
  python pcm_shell.py                      # Interactive mode
  python pcm_shell.py "ls /" "ifconfig"    # Run specific commands
  python pcm_shell.py --host 192.168.0.154 "pidin ar"
"""
import socket, time, sys

class PCMShell:
    def __init__(self, host='192.168.0.154', port=23):
        self.s = socket.socket()
        self.s.settimeout(3)
        self.s.connect((host, port))
        time.sleep(1)
        self._negotiate()
        self.s.sendall(b'root\n')
        time.sleep(2)
        self._drain()
    
    def _negotiate(self):
        try:
            while True:
                d = self.s.recv(1024)
                if not d: break
                i = 0
                while i < len(d):
                    if d[i] == 0xFF and i+2 < len(d):
                        if d[i+1] == 0xFD:
                            self.s.sendall(bytes([0xFF, 0xFC, d[i+2]]))
                        elif d[i+1] == 0xFB:
                            self.s.sendall(bytes([0xFF, 0xFE, d[i+2]]))
                        i += 3
                    else:
                        i += 1
        except socket.timeout:
            pass
    
    def _drain(self):
        try:
            while self.s.recv(4096): pass
        except socket.timeout:
            pass
    
    def cmd(self, command):
        self.s.sendall((command + '\n').encode())
        time.sleep(1.5)
        out = b''
        try:
            while True:
                d = self.s.recv(4096)
                if not d: break
                out += d
        except socket.timeout:
            pass
        text = out.decode('ascii', errors='replace')
        return ''.join(c for c in text if ord(c) >= 32 or c in '\n\r')
    
    def close(self):
        self.s.close()

if __name__ == '__main__':
    host = '192.168.0.154'
    cmds = []
    for a in sys.argv[1:]:
        if a.startswith('--host='):
            host = a.split('=')[1]
        else:
            cmds.append(a)
    
    t = PCMShell(host)
    if cmds:
        for c in cmds:
            print(f'=== {c} ===')
            print(t.cmd(c))
    else:
        print(f'PCM-Forge Shell -- Connected to {host}')
        try:
            while True:
                c = input('PCM> ')
                if c.strip():
                    print(t.cmd(c))
        except (KeyboardInterrupt, EOFError):
            print('\nDisconnected.')
    t.close()
