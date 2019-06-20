# python-tree-walk
a python module for deep_compare and patch of tree structures


python-tree-walk was my attempt to implement deep_compare between two trees.
At first I needed to compare two file system folders, but later I generalized
the algorithm relying on an abstract BaseTree class which can be overloaded
and expose the required path based tree API for any custom structure.

This module contains two possible BaseTree overloads:
* FileSystemTree - a path based tree like object that access files and folders
  in a file system. IMPORTANT: this implementation ignores file contents and
  only compared file's metadata using os.stat() call.
* MemoryTree - this is path base tree wrapper around a dictionary object or any
  tree like object that access nodes using the [] operator.
  
  
## notes

I am familiar with the alternatives:
* [python-json-patch](https://github.com/stefankoegl/python-json-patch)
* [deepdiff](https://pypi.org/project/deepdiff/)

python-json-patch is a json specific compare and patch module,
while python-tree-walk is more general supporting any tree like object and
support dictionary like objects out of the box.

deepdiff supports even more object types (not just dictionary like) but doesn't
have patch out of the box (though you could probably implement one on your own).




