##############################################################################
#
# Copyright (c) 2003 Zope Corporation and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.0 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
#
##############################################################################
"""Test Zope Guards

Well, at least begin testing some of the functionality

$Id$
"""

import os, sys
import unittest
import ZODB
import AccessControl.SecurityManagement
from AccessControl.SimpleObjectPolicies import ContainerAssertions
from AccessControl import Unauthorized
from AccessControl.ZopeGuards \
    import guarded_getattr, get_dict_get, get_dict_pop, get_list_pop, \
    get_iter, guarded_min, guarded_max, safe_builtins, guarded_enumerate, \
    guarded_sum, guarded_apply

try:
    __file__
except NameError:
    __file__ = os.path.abspath(sys.argv[1])
_FILEPATH = os.path.abspath( __file__ )
_HERE = os.path.dirname( _FILEPATH )

class SecurityManager:

    def __init__(self, reject=0):
        self.calls = []
        self.reject = reject

    def validate(self, *args):
        self.calls.append(('validate', args))
        if self.reject:
            raise Unauthorized
        return 1

    def validateValue(self, *args):
        self.calls.append(('validateValue', args))
        if self.reject:
            raise Unauthorized
        return 1

    def checkPermission(self, *args):
        self.calls.append(('checkPermission', args))
        return not self.reject


class GuardTestCase(unittest.TestCase):

    def setSecurityManager(self, manager):
        key = AccessControl.SecurityManagement.get_ident()
        old = AccessControl.SecurityManagement._managers.get(key)
        if manager is None:
            del AccessControl.SecurityManagement._managers[key]
        else:
            AccessControl.SecurityManagement._managers[key] = manager

        return old


class Method:

    def __init__(self, *args):
        self.args = args


class TestGuardedGetattr(GuardTestCase):

    def setUp(self):
        self.__sm = SecurityManager()
        self.__old = self.setSecurityManager(self.__sm)

    def tearDown(self):
        self.setSecurityManager(self.__old)

    def test_calls_validate_for_unknown_type(self):
        guarded_getattr(self, 'test_calls_validate_for_unknown_type')
        self.assert_(self.__sm.calls)

    def test_attr_handler_table(self):
        d = {}
        _dict = type(d)
        old = ContainerAssertions.get(_dict)

        mytable = {'keys': 1,
                   'values': Method,
                   }
        ContainerAssertions[_dict] = mytable
        try:
            guarded_getattr(d, 'keys')
            self.assertEqual(len(self.__sm.calls), 0)
            values = guarded_getattr(d, 'values')
            self.assertEqual(values.__class__, Method)
            self.assertEqual(values.args, (d, 'values'))
            self.assertRaises(Unauthorized, guarded_getattr, d, 'items')
        finally:
            ContainerAssertions[_dict] = old


class TestDictGuards(GuardTestCase):

    def test_get_simple(self):
        get = get_dict_get({'foo': 'bar'}, 'get')
        self.assertEqual(get('foo'), 'bar')

    def test_get_default(self):
        get = get_dict_get({'foo': 'bar'}, 'get')
        self.failUnless(get('baz') is None)
        self.assertEqual(get('baz', 'splat'), 'splat')

    def test_get_validates(self):
        sm = SecurityManager()
        old = self.setSecurityManager(sm)
        get = get_dict_get({'foo':GuardTestCase}, 'get')
        try:
            get('foo')
        finally:
            self.setSecurityManager(old)
        self.assert_(sm.calls)

    def test_pop_simple(self):
        pop = get_dict_pop({'foo': 'bar'}, 'pop')
        self.assertEqual(pop('foo'), 'bar')

    def test_pop_raises(self):
        pop = get_dict_pop({'foo': 'bar'}, 'pop')
        self.assertRaises(KeyError, pop, 'baz')

    def test_pop_default(self):
        pop = get_dict_pop({'foo': 'bar'}, 'pop')
        self.assertEqual(pop('baz', 'splat'), 'splat')

    def test_pop_validates(self):
        sm = SecurityManager()
        old = self.setSecurityManager(sm)
        pop = get_dict_get({'foo':GuardTestCase}, 'pop')
        try:
            pop('foo')
        finally:
            self.setSecurityManager(old)
        self.assert_(sm.calls)

    if sys.version_info >= (2, 2):

        def test_iterkeys_simple(self):
            d = {'foo':1, 'bar':2, 'baz':3}
            iterkeys = get_iter(d, 'iterkeys')
            keys = d.keys()
            keys.sort()
            ikeys = list(iterkeys())
            ikeys.sort()
            self.assertEqual(keys, ikeys)

        def test_iterkeys_empty(self):
            iterkeys = get_iter({}, 'iterkeys')
            self.assertEqual(list(iterkeys()), [])

        def test_iterkeys_validates(self):
            sm = SecurityManager()
            old = self.setSecurityManager(sm)
            iterkeys = get_iter({GuardTestCase: 1}, 'iterkeys')
            try:
                iterkeys().next()
            finally:
                self.setSecurityManager(old)
            self.assert_(sm.calls)

        def test_itervalues_simple(self):
            d = {'foo':1, 'bar':2, 'baz':3}
            itervalues = get_iter(d, 'itervalues')
            values = d.values()
            values.sort()
            ivalues = list(itervalues())
            ivalues.sort()
            self.assertEqual(values, ivalues)

        def test_itervalues_empty(self):
            itervalues = get_iter({}, 'itervalues')
            self.assertEqual(list(itervalues()), [])

        def test_itervalues_validates(self):
            sm = SecurityManager()
            old = self.setSecurityManager(sm)
            itervalues = get_iter({GuardTestCase: 1}, 'itervalues')
            try:
                itervalues().next()
            finally:
                self.setSecurityManager(old)
            self.assert_(sm.calls)

class TestListGuards(GuardTestCase):

    def test_pop_simple(self):
        pop = get_list_pop(['foo', 'bar', 'baz'], 'pop')
        self.assertEqual(pop(), 'baz')
        self.assertEqual(pop(0), 'foo')

    def test_pop_raises(self):
        pop = get_list_pop([], 'pop')
        self.assertRaises(IndexError, pop)

    def test_pop_validates(self):
        sm = SecurityManager()
        old = self.setSecurityManager(sm)
        pop = get_list_pop([GuardTestCase], 'pop')
        try:
            pop()
        finally:
            self.setSecurityManager(old)
        self.assert_(sm.calls)


class TestBuiltinFunctionGuards(GuardTestCase):

    def test_min_fails(self):
        sm = SecurityManager(1) # rejects
        old = self.setSecurityManager(sm)
        self.assertRaises(Unauthorized, guarded_min, [1,2,3])
        self.assertRaises(Unauthorized, guarded_min, 1,2,3)
        self.setSecurityManager(old)

    def test_max_fails(self):
        sm = SecurityManager(1) # rejects
        old = self.setSecurityManager(sm)
        self.assertRaises(Unauthorized, guarded_max, [1,2,3])
        self.assertRaises(Unauthorized, guarded_max, 1,2,3)
        self.setSecurityManager(old)

    def test_enumerate_fails(self):
        sm = SecurityManager(1) # rejects
        old = self.setSecurityManager(sm)
        enum = guarded_enumerate([1,2,3])
        self.assertRaises(Unauthorized, enum.next)
        self.setSecurityManager(old)

    def test_sum_fails(self):
        sm = SecurityManager(1) # rejects
        old = self.setSecurityManager(sm)
        self.assertRaises(Unauthorized, guarded_sum, [1,2,3])
        self.setSecurityManager(old)

    def test_min_succeeds(self):
        sm = SecurityManager() # accepts
        old = self.setSecurityManager(sm)
        self.assertEqual(guarded_min([1,2,3]), 1)
        self.assertEqual(guarded_min(1,2,3), 1)
        self.setSecurityManager(old)

    def test_max_succeeds(self):
        sm = SecurityManager() # accepts
        old = self.setSecurityManager(sm)
        self.assertEqual(guarded_max([1,2,3]), 3)
        self.assertEqual(guarded_max(1,2,3), 3)
        self.setSecurityManager(old)

    def test_enumerate_succeeds(self):
        sm = SecurityManager() # accepts
        old = self.setSecurityManager(sm)
        enum = guarded_enumerate([1,2,3])
        self.assertEqual(enum.next(), (0,1))
        self.assertEqual(enum.next(), (1,2))
        self.assertEqual(enum.next(), (2,3))
        self.assertRaises(StopIteration, enum.next)
        self.setSecurityManager(old)

    def test_sum_succeeds(self):
        sm = SecurityManager() # accepts
        old = self.setSecurityManager(sm)
        self.assertEqual(guarded_sum([1,2,3]), 6)
        self.assertEqual(guarded_sum([1,2,3], start=36), 42)
        self.setSecurityManager(old)

    def test_apply(self):
        sm = SecurityManager(1) # rejects
        old = self.setSecurityManager(sm)
        gapply = safe_builtins['apply']
        def f(a=1, b=2):
            return a+b
        # This one actually succeeds, because apply isn't given anything
        # to unpack.
        self.assertEqual(gapply(f), 3)
        # Likewise, because the things passed are empty.
        self.assertEqual(gapply(f, (), {}), 3)

        self.assertRaises(Unauthorized, gapply, f, [1])
        self.assertRaises(Unauthorized, gapply, f, (), {'a': 2})
        self.assertRaises(Unauthorized, gapply, f, [1], {'a': 2})

        sm = SecurityManager(0) # accepts
        self.setSecurityManager(sm)
        self.assertEqual(gapply(f), 3)
        self.assertEqual(gapply(f, (), {}), 3)
        self.assertEqual(gapply(f, [0]), 2)
        self.assertEqual(gapply(f, [], {'b': 18}), 19)
        self.assertEqual(gapply(f, [10], {'b': 1}), 11)

        self.setSecurityManager(old)

class TestGuardedDictListTypes(unittest.TestCase):

    def testDictCreation(self):
        d = safe_builtins['dict']
        self.assertEquals(d(), {})
        self.assertEquals(d({1:2}), {1:2})
        self.assertEquals(d(((1,2),)), {1:2})
        self.assertEquals(d(foo=1), {"foo":1})
        self.assertEquals(d.fromkeys((1,2,3)), {1:None, 2:None, 3:None})
        self.assertEquals(d.fromkeys((1,2,3), 'f'), {1:'f', 2:'f', 3:'f'})

    def testListCreation(self):
        l = safe_builtins['list']
        self.assertEquals(l(), [])
        self.assertEquals(l([1,2,3]), [1,2,3])
        x = [3,2,1]
        self.assertEquals(l(x), [3,2,1])
        if sys.version_info >= (2, 4):
            self.assertEquals(sorted(x), [1,2,3])

class TestRestrictedPythonApply(GuardTestCase):

    def test_apply(self):
        sm = SecurityManager(1) # rejects
        old = self.setSecurityManager(sm)
        gapply = guarded_apply
        def f(a=1, b=2):
            return a+b
        # This one actually succeeds, because apply isn't given anything
        # to unpack.
        self.assertEqual(gapply(*(f,)), 3)
        # Likewise, because the things passed are empty.
        self.assertEqual(gapply(*(f,), **{}), 3)

        self.assertRaises(Unauthorized, gapply, *(f, 1))
        self.assertRaises(Unauthorized, gapply, *(f,), **{'a': 2})
        self.assertRaises(Unauthorized, gapply, *(f, 1), **{'a': 2})

        sm = SecurityManager(0) # accepts
        self.setSecurityManager(sm)
        self.assertEqual(gapply(*(f,)), 3)
        self.assertEqual(gapply(*(f,), **{}), 3)
        self.assertEqual(gapply(*(f, 0)), 2)
        self.assertEqual(gapply(*(f,), **{'b': 18}), 19)
        self.assertEqual(gapply(*(f, 10), **{'b': 1}), 11)

        self.setSecurityManager(old)


# Map function name to the # of times it's been called.
wrapper_count = {}
class FuncWrapper:
    def __init__(self, funcname, func):
        self.funcname = funcname
        wrapper_count[funcname] = 0
        self.func = func

    def __call__(self, *args, **kws):
        wrapper_count[self.funcname] += 1
        return self.func(*args, **kws)

    def __repr__(self):
        return "<FuncWrapper around %r>" % self.func

# Given the high wall between AccessControl and RestrictedPython, I suppose
# the next one could be called an integration test.  But we're simply
# trying to run restricted Python with the *intended* implementations of
# the special wrappers here, so no apologies.
class TestActualPython(GuardTestCase):
    def testPython(self):
        from RestrictedPython.tests import verify

        code, its_globals = self._compile("actual_python.py")
        verify.verify(code)

        # Fiddle the global and safe-builtins dicts to count how many times
        # the special functions are called.
        self._wrap_replaced_dict_callables(its_globals)
        self._wrap_replaced_dict_callables(its_globals['__builtins__'])

        sm = SecurityManager()
        old = self.setSecurityManager(sm)
        try:
            exec code in its_globals
        finally:
            self.setSecurityManager(old)

        # Use wrapper_count to determine coverage.
        ## print wrapper_count # uncomment to see wrapper names & counts
        untouched = [k for k, v in wrapper_count.items() if v == 0]
        if untouched:
            untouched.sort()
            self.fail("Unexercised wrappers: %r" % untouched)

    def test_dict_access(self):
        from RestrictedPython.tests import verify

        SIMPLE_DICT_ACCESS_SCRIPT = """
def foo(text):
    return text

kw = {'text':'baz'}
print foo(**kw)

kw = {'text':True}
print foo(**kw)
"""
        code, its_globals = self._compile_str(SIMPLE_DICT_ACCESS_SCRIPT, 'x')
        verify.verify(code)

        sm = SecurityManager()
        old = self.setSecurityManager(sm)
        try:
            exec code in its_globals
        finally:
            self.setSecurityManager(old)

        self.assertEqual(its_globals['_print'](),
                        'baz\nTrue\n')
        
    def _compile_str(self, text, name):
        from RestrictedPython import compile_restricted
        from AccessControl.ZopeGuards import get_safe_globals, guarded_getattr

        code = compile_restricted(text, name, 'exec')

        g = get_safe_globals()
        g['_getattr_'] = guarded_getattr
        g['__debug__'] = 1  # so assert statements are active
        g['__name__'] = __name__ # so classes can be defined in the script
        return code, g

    def testPythonRealAC(self):
        code, its_globals = self._compile("actual_python.py")
        exec code in its_globals

    # Compile code in fname, as restricted Python. Return the
    # compiled code, and a safe globals dict for running it in.
    # fname is the string name of a Python file; it must be found
    # in the same directory as this file.
    def _compile(self, fname):
        from RestrictedPython import compile_restricted
        from AccessControl.ZopeGuards import get_safe_globals, guarded_getattr

        fn = os.path.join( _HERE, fname)
        text = open(fn).read()
        return self._compile_str(text, fn)

    # d is a dict, the globals for execution or our safe builtins.
    # The callable values which aren't the same as the corresponding
    # entries in __builtin__ are wrapped in a FuncWrapper, so we can
    # tell whether they're executed.
    def _wrap_replaced_dict_callables(self, d):
        import __builtin__
        for k, v in d.items():
            if callable(v) and v is not getattr(__builtin__, k, None):
                d[k] = FuncWrapper(k, v)

def test_suite():
    suite = unittest.TestSuite()
    for cls in (TestGuardedGetattr,
                TestDictGuards,
                TestBuiltinFunctionGuards,
                TestListGuards,
                TestGuardedDictListTypes,
                TestRestrictedPythonApply,
                TestActualPython,
                ):
        suite.addTest(unittest.makeSuite(cls))
    return suite


if __name__ == '__main__':
    unittest.main()
