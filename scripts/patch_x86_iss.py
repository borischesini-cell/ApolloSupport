import sys

p = r'C:/Desarrollo/P Python/ApolloSupport/agent/installer/ApolloSetup_x86.iss'
data = open(p, 'rb').read()

BS = chr(92)
old = ('Source: "..' + BS + 'ffmpeg.exe";').encode('ascii')
new = ('Source: "..' + BS + 'ffmpeg_x86.exe";').encode('ascii')

n = data.count(old)
assert n == 1, 'ocurrencias de %r: %d' % (old, n)

data = data.replace(old, new)
open(p, 'wb').write(data)

chk = open(p, 'rb').read()
assert chk.count(new) == 1 and chk.count(old) == 0
i = chk.find(new)
print('OK:', chk[i:i+90])
