import os


def configure_ime_environment() -> None:
    os.environ.setdefault("QT_IM_MODULE", "ibus")
    os.environ.setdefault("GTK_IM_MODULE", "ibus")
    os.environ.setdefault("XMODIFIERS", "@im=ibus")
