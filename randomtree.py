import random
import os

# TODO: handle random seed correctly (with commandline arguments support)
random.seed()


def random_name():
    return ''.join(random.choice('abcdefghi') for _ in range(random.randint(15, 20)))


def random_path():
    depth = random.randint(1,5)
    return os.path.sep.join([random.choice('ABCDE') for _ in range(depth)] + [random_name()])


def random_tree(tree, callback, count=100, variance=20):
    leaf_count = random.randint(count - variance, count + variance)
    for _ in range(leaf_count):
        path = os.path.join(tree.root, random_path())
        data = random.randint(1,100000)
        callback(tree, path, data)
    return leaf_count
