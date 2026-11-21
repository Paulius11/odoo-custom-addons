from . import models


def uninstall_hook(env):
    env["translation.override"]._restore_all_originals()
