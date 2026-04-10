import shutil
import subprocess

from call import call


@call
def play_yt(url):
    if not shutil.which("mpv"):
        raise RuntimeError("mpv not found in PATH")
    proc = subprocess.Popen(["mpv", "--no-video", url])
    print(f"PID: {proc.pid}")


@call
def sum(a: int, b: int) -> None:
    print(a + b)
