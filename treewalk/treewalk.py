import logging
import os
import stat
import shutil
import json


def get_logger():
    return logging.getLogger(__name__)


class BaseTree(object):
    def __init__(self, root):
        self.root = root

    def is_exist(self, node_ref):
        return False

    def get_node_data(self, node_ref):
        return None

    def is_leaf(self, node_data):
        return False

    def get_subnodes(self, node_ref, node_data):
        return []

    def get_relative_ref(self, node_ref):
        return os.path.normpath(os.path.relpath(node_ref, self.root))

    def get_abs_ref(self, node_ref):
        return os.path.normpath(os.path.join(self.root, node_ref))

    def read(self, node_ref):
        return None

    def write(self, node_ref, data):
        pass

    def make_node(self, node_ref):
        pass

    def del_node(self, node_ref):
        pass


class FileSystemTree(BaseTree):
    def __init__(self, root, is_mirror=False):
        super().__init__(root)
        self.is_mirror = is_mirror

    def is_exist(self, node_ref):
        return os.path.exists(node_ref)

    def get_node_data(self, node_ref):
        return os.stat(node_ref)

    def is_leaf(self, node_data):
        mode = node_data.st_mode
        return not stat.S_ISDIR(mode)

    def get_subnodes(self, node_ref, node_data):
        return [os.path.join(node_ref, x) for x in os.listdir(node_ref)
                if x != '.']

    def read(self, node_ref):
        with open(node_ref, 'r') as read_file:
            data = json.load(read_file)
        return data

    def write(self, node_ref, data):
        try:
            with open(node_ref, 'w+') as write_file:
                json.dump(data, write_file)
        except IOError:
            head, _ = os.path.split(node_ref)
            os.makedirs(head)
            self.write(node_ref, data)

    def make_node(self, node_ref):
        os.mkdir(node_ref)

    def del_node(self, node_ref):
        shutil.rmtree(node_ref, ignore_errors=True)

    def del_leaf(self, node_ref):
        os.remove(node_ref)


class MemoryTree(BaseTree):
    def __init__(self, root, tree_object):
        super().__init__(root)
        self.tree_object = tree_object

    def is_exist(self, node_ref):
        try:
            self.get_node_data(node_ref)
        except KeyError:
            return False
        return True

    def get_node_data(self, node_ref):
        return self.read(node_ref)

    def is_leaf(self, node_data):
        return not isinstance(node_data, dict)

    def get_subnodes(self, node_ref, node_data):
        return [os.path.join(node_ref, x) for x in node_data.keys()]

    def read(self, node_ref):
        node_path_list = node_ref.split(os.path.sep)
        data = self.tree_object
        for node_name in node_path_list:
            if node_name == '':
                continue
            data = data[node_name]
        return data

    def write(self, node_ref, data):
        head, tail = os.path.split(node_ref)
        node = self.make_node(head)
        node[tail] = data

    def make_node(self, node_ref):
        node_path_list = node_ref.split(os.path.sep)
        node = self.tree_object
        for node_name in node_path_list:
            if node_name == '':
                continue
            if node_name not in node:
                node[node_name] = {}
            node = node[node_name]
        return node

    def del_node(self, node_ref):
        self.del_leaf(node_ref)

    def del_leaf(self, node_ref):
        head, tail = os.path.split(node_ref)
        node = self.read(head)
        node.pop(tail)


class BaseContext(object):
    def node(self, node_ref, node_data):
        pass

    def leaf(self, node_ref, node_data):
        pass

    def node_filter(self, node_ref):
        return True

    def leaf_filter(self, node_ref):
        return True


class NodeCountContext(BaseContext):
    def __init__(self):
        self.node_count = 0
        self.leaf_count = 0

    def node(self, node_ref, node_data):
        # print u'node {}'.format(node_ref)
        self.node_count += 1

    def leaf(self, node_ref, node_data):
        # print u'leaf {}'.format(node_ref)
        self.leaf_count += 1


class BuildTreeContext(BaseContext):
    def __init__(self, tree):
        self.tree = tree

    def node(self, node_ref, node_data):
        self.tree.make_node(node_ref)

    def leaf(self, node_ref, node_data):
        self.tree.write(node_ref, node_data)


class FilterContext(BaseContext):
    def __init__(self, sub_context,
                 node_filter=lambda x: True, leaf_filter=lambda x: True):
        self.sub_context = sub_context
        self.node_filter = node_filter
        self.leaf_filter = leaf_filter

    def node(self, node_ref, node_data):
        self.sub_context.node(node_ref, node_data)

    def leaf(self, node_ref, node_data):
        self.sub_context.leaf(node_ref, node_data)


class MirrorTreeContext(BaseContext):
    def __init__(self, tree, mirror_tree, sub_context):
        self.tree = tree
        self.mirror_tree = mirror_tree
        self.sub_context = sub_context

    def reflect_ref(self, node_ref):
        rel_ref = self.tree.get_relative_ref(node_ref)
        abs_ref = self.mirror_tree.get_abs_ref(rel_ref)
        # print u'node_ref {}, rel_ref {}, abs_ref {}'.format(node_ref, rel_ref, abs_ref)
        return abs_ref

    def node(self, node_ref, node_data):
        self.sub_context.node(self.reflect_ref(node_ref), node_data)

    def leaf(self, node_ref, node_data):
        self.sub_context.leaf(self.reflect_ref(node_ref), node_data)


class DiffContext(MirrorTreeContext):
    def __init__(self, tree_a, tree_b, sub_context, is_reflected=False):
        super(DiffContext, self).__init__(tree_a, tree_b, sub_context)
        self.is_reflected = is_reflected

    def node(self, node_ref, node_data):
        pass  # diff in nodes are handled with node filter

    def leaf(self, node_ref, node_data):
        reflect_ref = self.reflect_ref(node_ref)
        if not self.mirror_tree.is_exist(reflect_ref):
            value = reflect_ref if self.is_reflected else node_ref
            self.sub_context.leaf(value, node_data)


class ModifContext(MirrorTreeContext):
    def __init__(self, tree_a, tree_b, sub_context, leaf_compare=lambda x, y: x == y):
        super(ModifContext, self).__init__(tree_a, tree_b, sub_context)
        self.leaf_compare = leaf_compare

    def node(self, node_ref, node_data):
        pass  # ignore folder modification times for now (doesn't work in exFAT anyway)

    def leaf(self, node_ref, node_data):
        reflect_ref = self.reflect_ref(node_ref)
        if self.mirror_tree.is_exist(reflect_ref):
            other_node_data = self.mirror_tree.get_node_data(reflect_ref)
            if not self.leaf_compare(node_data, other_node_data):
                self.sub_context.leaf(node_ref, node_data)


class ComposeContext(BaseContext):
    def __init__(self, sub_context_a, sub_context_b):
        self.sub_context_a = sub_context_a
        self.sub_context_b = sub_context_b

    def node(self, node_ref, node_data):
        self.sub_context_a.node(node_ref, node_data)
        self.sub_context_b.node(node_ref, node_data)

    def leaf(self, node_ref, node_data):
        self.sub_context_a.leaf(node_ref, node_data)
        self.sub_context_b.leaf(node_ref, node_data)


class CallbackContext(BaseContext):
    def __init__(self, node_cb, leaf_cb):
        self.node_cb = node_cb
        self.leaf_cb = leaf_cb

    def node(self, node_ref, node_data):
        self.node_cb(node_ref, node_data)

    def leaf(self, node_ref, node_data):
        self.leaf_cb(node_ref, node_data)


class DictContext(BaseContext):
    def __init__(self, nodes, leafs):
        self.nodes = nodes
        self.leafs = leafs

    def node(self, node_ref, node_data):
        self.nodes[node_ref] = node_data

    def leaf(self, node_ref, node_data):
        self.leafs[node_ref] = node_data


class PatchContext(object):
    def __init__(self):
        self.insert_nodes = {}
        self.insert_leafs = {}
        self.modif_nodes = {}
        self.modif_leafs = {}
        self.delete_nodes = {}
        self.delete_leafs = {}
        self.insert_context = ComposeContext(
            DictContext(self.insert_nodes, self.insert_leafs),
            CallbackContext(self.node_inserted, self.leaf_inserted))
        self.delete_context = ComposeContext(
            DictContext(self.delete_nodes, self.delete_leafs),
            CallbackContext(self.node_deleted, self.leaf_deleted))
        self.modif_context = ComposeContext(
            DictContext(self.modif_nodes, self.modif_leafs),
            CallbackContext(self.node_modified, self.leaf_modified))

    def node_inserted(self, node_ref, node_data):
        pass

    def leaf_inserted(self, node_ref, node_data):
        pass

    def node_modified(self, node_ref, node_data):
        pass

    def leaf_modified(self, node_ref, node_data):
        pass

    def node_deleted(self, node_ref, node_data):
        pass

    def leaf_deleted(self, node_ref, node_data):
        pass


def tree_walk(tree, node_ref, context):
    try:
        node_data = tree.get_node_data(node_ref)
        if tree.is_leaf(node_data):
            if context.leaf_filter(node_ref):
                context.leaf(node_ref, node_data)
            return

        if not context.node_filter(node_ref):
            return

        context.node(node_ref, node_data)
        sub_nodes = tree.get_subnodes(node_ref, node_data)
        for sub_node_ref in sub_nodes:
            tree_walk(tree, sub_node_ref, context)
    except IOError:
        get_logger().warning(u'failed to scan {}'.format(node_ref), exc_info=True)
        # raise e


def count_nodes(tree, leaf_filter=lambda x: True, node_filter=lambda x: True):
    node_count_context = NodeCountContext()
    filter_context = FilterContext(node_count_context,
                                   leaf_filter=leaf_filter, node_filter=node_filter)
    tree_walk(tree, tree.root, filter_context)
    return node_count_context.leaf_count, node_count_context.node_count


def reflect_tree(source, target,
                 leaf_filter=lambda x: True, node_filter=lambda x: True):
    build_context = BuildTreeContext(target)
    mirror_context = MirrorTreeContext(source, target, build_context)
    filter_context = FilterContext(mirror_context,
                                   leaf_filter=leaf_filter, node_filter=node_filter)
    tree_walk(source, source.root, filter_context)


def deleted_node_handler(node_ref, diff_context, context, sub_filter):
    reflect_ref = diff_context.reflect_ref(node_ref)
    if not sub_filter(reflect_ref):
        return False
    reflect_node_exist = diff_context.mirror_tree.is_exist(reflect_ref)
    if not reflect_node_exist:
        # print 'deleted node {}'.format(node_ref)
        context.node(reflect_ref, '')
    return reflect_node_exist  # continue recursion only for nodes that exist on both trees


def deep_compare(tree_a, tree_b, patch_context,
                 leaf_compare=lambda x, y: x == y,
                 leaf_filter=lambda x: True, node_filter=lambda x: True):
    # 1st pass: find inserts / modifs
    diff_insert_context = DiffContext(tree_a, tree_b, patch_context.insert_context)
    modif_context = ModifContext(tree_a, tree_b, patch_context.modif_context,
                                 leaf_compare=leaf_compare)
    filter_context = FilterContext(ComposeContext(diff_insert_context, modif_context),
                                   leaf_filter=leaf_filter, node_filter=node_filter)
    tree_walk(tree_a, tree_a.root, filter_context)

    # 2nd pass: find deletes
    diff_context = DiffContext(tree_b, tree_a, patch_context.delete_context, is_reflected=True)
    filter_context = FilterContext(
        diff_context,
        node_filter=lambda x: deleted_node_handler(x, diff_context, patch_context.delete_context, node_filter))
    tree_walk(tree_b, tree_b.root, filter_context)


def patch_tree(tree, patch_context, callback=lambda x, y: (x, y)):
    for leaf_ref in patch_context.insert_leafs:
        process_ref, process_data = callback(leaf_ref, patch_context.insert_leafs[leaf_ref])
        tree.write(process_ref, process_data)
    for leaf_ref in patch_context.modif_leafs:
        process_ref, process_data = callback(leaf_ref, patch_context.modif_leafs[leaf_ref])
        tree.write(process_ref, process_data)
    for leaf_ref in patch_context.delete_leafs:
        process_ref, process_data = callback(leaf_ref, None)
        tree.del_leaf(process_ref)
    for node_ref in patch_context.delete_nodes:
        process_ref, process_data = callback(node_ref, None)
        tree.del_node(process_ref)
