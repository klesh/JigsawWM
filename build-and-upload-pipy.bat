rm dist/*
py -m build
twine upload dist/*