#!/usr/bin/env python
#ipy_sh is module which encapsulates IPython.IPShellEmbed to work with gtk gui
import IPython
import inspect
from IPython.frontend.terminal.embed import InteractiveShellEmbed

class PSE(InteractiveShellEmbed):
    def __init__(self):
        frame = inspect.currentframe()
        try:
            info = inspect.getframeinfo(frame,context=3)
        finally:
            del frame
        print('filename:%s line:%s function:%s index into code %s'%(info[0],info[1],info[2],info[4],))
        for line in info[3]:
            print line,
        args = ['=pi1','in <\\#>:','-po','Out<\\#>:']
        InteractiveShellEmbed.__init__(self,args,banner='Now in shell at your breakpoint\nTry debug\n')
        
if __name__ == '__main__':
    test = PSE()
        