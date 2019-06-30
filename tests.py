import unittest
import treewalk
import logging
import os
import randomtree
import copy


logging.basicConfig()


class RandomTreeSetup(unittest.TestCase):
    def setUp(self):
        self.tree_object = {"root": {"A": {}}}
        self.tree = treewalk.MemoryTree('/root', self.tree_object)
        self.leaf_count = randomtree.random_tree(
            self.tree,
            lambda tree, node_ref, node_data: tree.write(node_ref, node_data),
            count=10000, variance=2000)
        self.maxDiff = None

    def tearDown(self):
        self.tree_object = None
        self.tree = None
        self.leaf_count = 0

    def assertEqualPatch(self, patch_a, patch_b):
        self.assertEqual(patch_a.insert_leafs, patch_b.insert_leafs)
        self.assertEqual(patch_a.insert_nodes, patch_b.insert_nodes)
        self.assertEqual(patch_a.modif_leafs, patch_b.modif_leafs)
        self.assertEqual(patch_a.modif_nodes, patch_b.modif_nodes)
        self.assertEqual(patch_a.delete_leafs, patch_b.delete_leafs)
        self.assertEqual(patch_a.delete_nodes, patch_b.delete_nodes)


class SubtreeSetup(RandomTreeSetup):
    def setUp(self):
        super(SubtreeSetup, self).setUp()
        self.subtree = treewalk.MemoryTree('/root/A', self.tree_object)

    def tearDown(self):
        self.subtree = None
        super(SubtreeSetup, self).tearDown()


class CountReflectTestCase(SubtreeSetup):
    def test_count_nodes(self):
        leaf_count, node_count = treewalk.count_nodes(self.tree)
        self.assertEqual(leaf_count, self.leaf_count)

        leaf_count2, node_count2 = treewalk.count_nodes(self.subtree)
        self.assertTrue(leaf_count2 <= leaf_count)
        self.assertTrue(node_count2 <= node_count)

        leaf_count3, node_count3 = treewalk.count_nodes(
            self.tree,
            node_filter=lambda x: x != '/root/A')

        self.assertEqual(leaf_count, leaf_count2 + leaf_count3)
        self.assertEqual(node_count, node_count2 + node_count3)

        leaf_count4, node_count4 = treewalk.count_nodes(
            self.tree,
            leaf_filter=lambda x: len(x) > 17)
        leaf_count5, node_count5 = treewalk.count_nodes(
            self.tree,
            leaf_filter=lambda x: len(x) <= 17)

        self.assertEqual(leaf_count, leaf_count4 + leaf_count5)
        self.assertEqual(node_count, node_count4)
        self.assertEqual(node_count, node_count5)

    def test_reflect_tree(self):
        mirror_object = {"mirror": {}}
        mirror_tree = treewalk.MemoryTree('/mirror', mirror_object)
        treewalk.reflect_tree(self.tree, mirror_tree)
        self.assertEqual(self.tree_object['root'], mirror_object['mirror'])

        inplace_mirror_tree = treewalk.MemoryTree('/root/.mirror', self.tree_object)
        treewalk.reflect_tree(self.tree, inplace_mirror_tree,
                              node_filter=lambda x: x != '/root/.mirror')

        leaf_count, _ = treewalk.count_nodes(self.tree)
        self.assertEqual(leaf_count, self.leaf_count * 2)


class CompareBaseSetup(RandomTreeSetup):
    def setUp(self):
        super(CompareBaseSetup, self).setUp()
        self.other_tree_object = {'other_root': {}}
        self.other_tree_object['other_root'] = copy.deepcopy(self.tree_object['root'])
        self.other_tree = treewalk.MemoryTree('/other_root', self.other_tree_object)
        self.patch_context = treewalk.PatchContext()

    def tearDown(self):
        self.other_tree_object = None
        self.other_tree = None
        super(CompareBaseSetup, self).tearDown()


class CompareTestCase(CompareBaseSetup):
    def test_simple_compare(self):
        treewalk.deep_compare(self.tree, self.other_tree, self.patch_context)

        empty_patch = treewalk.PatchContext()
        self.assertEqualPatch(self.patch_context, empty_patch)


def insert_leaf(tree, node_ref, node_data, patch):
    tree.write(node_ref, node_data)
    patch.insert_leafs[node_ref] = node_data


def simulate_delete_leaf(tree, other_tree, node_ref, node_data, patch):
    reflected_node_ref = other_tree.get_abs_ref(tree.get_relative_ref(node_ref))
    other_tree.write(reflected_node_ref, node_data)
    head, _ = os.path.split(node_ref)
    tree.make_node(head)
    patch.delete_leafs[node_ref] = node_data
    # print 'added leaf {}, added node {}'.format(node_ref, head)


def simulate_modif(tree, other_tree, node_ref, node_data, patch):
    reflected_node_ref = other_tree.get_abs_ref(tree.get_relative_ref(node_ref))
    tree.write(node_ref, node_data + 1)
    other_tree.write(reflected_node_ref, node_data)
    patch.modif_leafs[node_ref] = node_data + 1


def simulate_delete_node(tree, other_tree, node_ref, patch):
    reflected_node_ref = other_tree.get_abs_ref(tree.get_relative_ref(node_ref))
    head, _ = os.path.split(node_ref)
    reflect_head, _ = os.path.split(reflected_node_ref)
    deleted_node = os.path.join(reflect_head, 'DELETED_NODE')
    tree.make_node(head)
    other_tree.make_node(deleted_node)
    patch.delete_nodes[os.path.join(head, 'DELETED_NODE')] = ''


class CompareWithModificationsSetup(CompareBaseSetup):
    def setUp(self):
        super(CompareWithModificationsSetup, self).setUp()
        num = 1000
        var = 300
        randomtree.random_tree(
            self.tree,
            lambda tree, node_ref, node_data: insert_leaf(tree, node_ref, node_data, self.patch_context),
            count=num, variance=var)
        randomtree.random_tree(
            self.tree,
            lambda tree, random_ref, random_data: simulate_delete_leaf(
                tree, self.other_tree, random_ref, random_data, self.patch_context),
            count=num, variance=var)
        randomtree.random_tree(
            self.tree,
            lambda tree, random_ref, random_data: simulate_modif(
                tree, self.other_tree, random_ref, random_data, self.patch_context),
            count=num, variance=var)
        randomtree.random_tree(self.tree,
                               lambda tree, random_ref, random_data: simulate_delete_node(
                                   tree, self.other_tree, random_ref, self.patch_context),
                               count=num, variance=var)

    def tearDown(self):
        super(CompareWithModificationsSetup, self).tearDown()


class CompareWithModificationsTestCase(CompareWithModificationsSetup):
    def test_compare_with_modifications(self):
        # print json.dumps(self.tree_object, indent=4)
        # print json.dumps(self.other_tree_object, indent=4)
        patch = treewalk.PatchContext()
        treewalk.deep_compare(self.tree, self.other_tree, patch)
        # print json.dumps(self.patch_context.modif_context.leafs, indent=4)
        # print json.dumps(patch.modif_context.leafs, indent=4)
        self.assertEqualPatch(patch, self.patch_context)


class CompareInplaceSetup(RandomTreeSetup):
    def setUp(self):
        super(CompareInplaceSetup, self).setUp()
        self.tree.make_node('/root/in_place_mirror')
        self.subtree = treewalk.MemoryTree('/root/in_place_mirror', self.tree_object)
        treewalk.reflect_tree(
            self.tree, self.subtree,
            node_filter=lambda x: x != '/root/in_place_mirror')

        self.patch_context = treewalk.PatchContext()
        num = 1000
        var = 300
        randomtree.random_tree(
            self.tree,
            lambda tree, node_ref, node_data: insert_leaf(tree, node_ref, node_data, self.patch_context),
            count=num, variance=var)
        randomtree.random_tree(
            self.tree,
            lambda tree, random_ref, random_data: simulate_delete_leaf(
                tree, self.subtree, random_ref, random_data, self.patch_context),
            count=num, variance=var)
        randomtree.random_tree(
            self.tree,
            lambda tree, random_ref, random_data: simulate_modif(
                tree, self.subtree, random_ref, random_data, self.patch_context),
            count=num, variance=var)
        randomtree.random_tree(self.tree,
                               lambda tree, random_ref,
                               random_data: simulate_delete_node(tree, self.subtree, random_ref, self.patch_context),
                               count=num, variance=var)
        # print json.dumps(self.tree_object, indent=4)

    def tearDown(self):
        self.subtree = None
        self.patch_context = None
        super(CompareInplaceSetup, self).tearDown()


class CompareInplaceTestCase(CompareInplaceSetup):
    def test_compare_in_place(self):
        patch = treewalk.PatchContext()
        treewalk.deep_compare(
            self.tree, self.subtree, patch,
            node_filter=lambda x: x != '/root/in_place_mirror')
        self.assertEqualPatch(patch, self.patch_context)


class PatchTreeTestCase(CompareWithModificationsSetup):
    def test_patch_tree(self):
        patch = treewalk.PatchContext()
        treewalk.deep_compare(self.tree, self.other_tree, patch)
        mirror_context = treewalk.MirrorTreeContext(self.tree, self.other_tree, None)
        treewalk.patch_tree(self.other_tree, patch, callback=lambda x, y: (mirror_context.reflect_ref(x), y))
        patch2 = treewalk.PatchContext()
        treewalk.deep_compare(self.tree, self.other_tree, patch2)
        empty_patch = treewalk.PatchContext()
        self.assertEqualPatch(patch2, empty_patch)


test_cases = (CountReflectTestCase, CompareTestCase,
              CompareWithModificationsTestCase, CompareInplaceTestCase,
              PatchTreeTestCase)


def load_tests(loader, std_tests, pattern):
    treewalk_suite = unittest.TestSuite()
    for test_class in test_cases:
        tests = loader.loadTestsFromTestCase(test_class)
        treewalk_suite.addTests(tests)
    return treewalk_suite


if __name__ == '__main__':
    suite = load_tests(unittest.TestLoader(), [], None)
    unittest.TextTestRunner(verbosity=2).run(suite)
