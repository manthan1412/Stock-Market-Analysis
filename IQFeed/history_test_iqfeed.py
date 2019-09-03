import socket

print("Connect to Admin port")
#settings = "HISTORY"
settings = "LIVE_INTERVAL_BARS"

def signal(message, s):
  s.sendall(message)
  i = 0
  while 1:
    data = ""
    data = s.recv(4096)
    data = data.decode("UTF-8")
    if '!ENDMSG!' in data:
      return
    print ("\n{0}\n".format(str(i)))
    print(data)
    i += 1


if settings == "HISTORY":
  host = "127.0.0.1"
  port = 9100
  sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  sock.connect((host,port))
  message1 = b'HIT,FB,300,20190202 100000,,,,,0,1,100\r\nHIT,GOOGL,300,20190202 100000,,,,,0,2,100\r\n'
  # message = b'HIT,FB,300,20190201 100000,,,,,0,,,s,1\r\n'
  signal(message1, sock)
  sock.shutdown(socket.SHUT_RDWR)


if settings == "LIVE_INTERVAL_BARS":
  host = "127.0.0.1"
  port = 9400
  sock2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  sock2.connect((host,port))
  message2 = b'BW,FB,300,20190201 100000,1,10,,,100,s,,0\r\nBW,GOOGL,300,20190201 100000,1,10,,,101,s,,0\r\n'
  message2 = 'BW,FB,300,20190201 100000,1,10,,,100,s,,0\r\nBW,GOOGL,300,20190201 100000,1,10,,,101,s,,0\r\n'
  signal(message2.encode("UTF-8"), sock2)
  sock2.shutdown(socket.SHUT_RDWR)
