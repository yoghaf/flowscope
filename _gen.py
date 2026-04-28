import base64,sys
f=open(sys.argv[1],"wb")
f.write(base64.b64decode(sys.stdin.read()))
f.close()
print("OK")