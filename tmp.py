from Rpyc import *
c = SocketConnection('localhost')
print('instance %r'%c.modules.pydebug.pydebug_instance)
print('pydebug home: %r'%c.modules.pydebug.pydebug_instance.pydebug_home)