#!/usr/bin/env python
# pip install livereload
import os

from livereload import Server, shell

make = os.path.join(os.path.dirname(__file__), "make.bat")
print(make)
server = Server()
# server.watch("jigsawwm/**/**.py", shell("sphinx-apidoc -f -o docs .", cwd=".."))
server.watch(
    "docs/*.rst",
    shell([make, "html"], cwd=".."),
)
server.watch(
    "jigsawwm/*.py",
    shell([make, "html"], cwd=".."),
)
server.watch(
    "jigsawwm/*/*.py",
    shell([make, "html"], cwd=".."),
)
server.serve(root="docs/_build/html")
