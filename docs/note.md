
# sphinx document

generate rst for source code
```
sphinx-apidoc -o docs src
```

document live reload
```
py .\docs\sphinx-live.py
```

configure rtd to auto update
1. log into rtd with github account
2. import repository

# publish to pypi

build package
```
py -m build
```

check package
```
twine check dist/*
```

upload to test.pypi.org
```
twine upload -r testpypi dist/* 
```

upload to pypi.org
```
twine upload dist/* 
```