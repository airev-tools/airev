import subprocess
from collections import OrderedDict

result = subprocess.run(["ls"], capture_output=True)
x: int | None = None
y: list[str] = []
d = OrderedDict()
