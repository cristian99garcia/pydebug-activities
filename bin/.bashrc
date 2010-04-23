# .bashrc

# User specific aliases and functions

alias rm='rm -i'
alias cp='cp -i'
alias mv='mv -i'

# Source global definitions
if [ -f /etc/bashrc ]; then
	. /etc/bashrc
fi

# some more ls aliases
alias ll='ls -l'
alias la='ls -A'
alias l='ls -CF'
alias df='df -h'
alias du1='du --max-depth=1 -h'
alias du2='du --max-depth=2 -h'
alias rve='pydbgp -d10.44.75.230:9000 /home/olpc/Activities/VideoEdit/bin/pitivi'
alias ipy=ipython

