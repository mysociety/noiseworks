import os

from django.core.management.commands.shell import Command
from ptpython.repl import embed


def ptpython(self, options):
    history_filename = os.path.expanduser("~/.ptpython_history")
    embed(globals(), locals(), vi_mode=True, history_filename=history_filename)


Command.ptpython = ptpython
Command.shells.insert(0, "ptpython")
