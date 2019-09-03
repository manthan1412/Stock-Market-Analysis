
import subprocess
import sys
import socket
import string


print("Connect to Admin port")

host = "127.0.0.1"
port = 9300
message = b'S,CLIENTSTATS ON\r\n'

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect((host,port))
s.sendall(message)

while 1:
 data = ""
 data = s.recv(4096)
 print(data.decode("UTF-8"))
