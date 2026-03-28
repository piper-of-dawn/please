import shutil
import subprocess

from please import please


@please
def play_yt(url):
    if not shutil.which("mpv"):
        raise RuntimeError("mpv not found in PATH")
    subprocess.Popen(["mpv", "--no-video", url])


@please
def sum(a: int, b: int) -> None:
    print(a + b)
