#
# Example ZopeTestCase testing web access to a freshly started ZServer.
#
# Note that we need to set up the error_log before starting the ZServer.
#
# Note further that the test thread needs to explicitly commit its
# transactions, so the ZServer threads can see modifications made to
# the ZODB.
#
# IF YOU THINK YOU NEED THE WEBSERVER STARTED YOU ARE PROBABLY WRONG!
# This is only required in very special cases, like when testing
# ZopeXMLMethods where XSLT processing is done by external tools that
# need to URL-call back into the Zope server.
#
# If you want to write functional unit tests, see the testFunctional.py 
# example instead.
#

# $Id: testWebserver.py,v 1.14 2004/04/09 12:38:37 shh42 Exp $

import os, sys
if __name__ == '__main__':
    execfile(os.path.join(sys.path[0], 'framework.py'))

#os.environ['STUPID_LOG_FILE'] = os.path.join(os.getcwd(), 'zLOG.log')
#os.environ['STUPID_LOG_SEVERITY'] = '0'

from Testing import ZopeTestCase

from AccessControl import Unauthorized
import urllib

# Create the error_log object
ZopeTestCase.utils.setupSiteErrorLog()

# Start the web server
host, port = ZopeTestCase.utils.startZServer(4)
folder_url = 'http://%s:%d/%s' %(host, port, ZopeTestCase.folder_name)


class ManagementOpener(urllib.FancyURLopener):
    '''Logs on as manager when prompted'''
    def prompt_user_passwd(self, host, realm):
        return ('manager', 'secret')

class UnauthorizedOpener(urllib.FancyURLopener):
    '''Raises Unauthorized when prompted'''
    def prompt_user_passwd(self, host, realm):
        raise Unauthorized, 'The URLopener was asked for authentication'


class TestWebserver(ZopeTestCase.ZopeTestCase):

    def afterSetUp(self):
        uf = self.folder.acl_users
        uf._doAddUser('manager', 'secret', ['Manager'], [])
        manager = uf.getUserById('manager').__of__(uf)

        self.folder.addDTMLMethod('index_html', file='index_html called')
        self.folder.addDTMLMethod('secret_html', file='secret_html called')
        self.folder.manage_addFolder('object', '')

        for p in ZopeTestCase.standard_permissions:
            self.folder.secret_html.manage_permission(p, ['Manager'], acquire=0)

        self.folder.addDTMLMethod('object_ids', file='<dtml-var objectIds>')
        self.folder.addDTMLMethod('user_ids', file='<dtml-var "acl_users.getUserNames()">')
        self.folder.addDTMLMethod('change_title', 
            file='''<dtml-call "manage_changeProperties(title=REQUEST.get('title'))">'''
                 '''<dtml-var title_or_id>''')

        self.folder.object_ids.changeOwnership(manager)
        self.folder.user_ids.changeOwnership(manager)
        self.folder.change_title.changeOwnership(manager)

        # Commit so the ZServer threads can see the changes
        get_transaction().commit()

    def beforeClose(self):
        # Commit after cleanup
        get_transaction().commit()

    def testAccessPublicObject(self):
        # Test access to a public resource
        page = self.folder.index_html(self.folder)
        self.assertEqual(page, 'index_html called')

    def testURLAccessPublicObject(self):
        # Test web access to a public resource
        urllib._urlopener = ManagementOpener()
        page = urllib.urlopen(folder_url+'/index_html').read()
        self.assertEqual(page, 'index_html called')

    def testAccessProtectedObject(self):
        # Test access to a protected resource
        page = self.folder.secret_html(self.folder)
        self.assertEqual(page, 'secret_html called')

    def testURLAccessProtectedObject(self):
        # Test web access to a protected resource
        urllib._urlopener = ManagementOpener()
        page = urllib.urlopen(folder_url+'/secret_html').read()
        self.assertEqual(page, 'secret_html called')

    def testSecurityOfPublicObject(self):
        # Test security of a public resource
        try: 
            self.folder.restrictedTraverse('index_html')
        except Unauthorized:
            # Convert error to failure
            self.fail('Unauthorized')

    def testURLSecurityOfPublicObject(self):
        # Test web security of a public resource
        urllib._urlopener = UnauthorizedOpener()
        try: 
            urllib.urlopen(folder_url+'/index_html')
        except Unauthorized:
            # Convert error to failure
            self.fail('Unauthorized')

    def testSecurityOfProtectedObject(self):
        # Test security of a protected resource
        try:
            self.folder.restrictedTraverse('secret_html')
        except Unauthorized:
            pass    # Test passed
        else:
            self.fail('Resource not protected')

    def testURLSecurityOfProtectedObject(self):
        # Test web security of a protected resource
        urllib._urlopener = UnauthorizedOpener()
        try: 
            urllib.urlopen(folder_url+'/secret_html')
        except Unauthorized:
            pass    # Test passed
        else:
            self.fail('Resource not protected')

    def testModifyObject(self):
        # Test a script that modifies the ZODB
        self.setRoles(['Manager'])
        self.app.REQUEST.set('title', 'Foo')
        page = self.folder.object.change_title(self.folder.object, 
                                               self.app.REQUEST)
        self.assertEqual(page, 'Foo')
        self.assertEqual(self.folder.object.title, 'Foo')

    def testURLModifyObject(self):
        # Test a transaction that actually commits something
        urllib._urlopener = ManagementOpener()
        page = urllib.urlopen(folder_url+'/object/change_title?title=Foo').read()
        self.assertEqual(page, 'Foo')

    def testAbsoluteURL(self):
        # Test absolute_url
        self.assertEqual(self.folder.absolute_url(), folder_url)


class TestSandboxedWebserver(ZopeTestCase.Sandboxed, TestWebserver):
    '''Demonstrates that tests involving ZServer threads can also be 
       run from sandboxes. In fact, it may be preferable to do so.
    '''

    # Note: By inheriting from TestWebserver we run the same 
    # test methods as above!

    def testConnectionIsShared(self):
        # Due to sandboxing the ZServer thread operates on the
        # same connection as the main thread, allowing us to
        # see changes made to 'object' right away.
        urllib._urlopener = ManagementOpener()
        urllib.urlopen(folder_url+'/object/change_title?title=Foo')
        self.assertEqual(self.folder.object.title, 'Foo')

    def testCanCommit(self):
        # Additionally, it allows us to commit transactions without
        # harming the test ZODB.
        self.folder.foo = 1
        get_transaction().commit()
        self.folder.foo = 2
        get_transaction().commit()


def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(TestWebserver))
    suite.addTest(makeSuite(TestSandboxedWebserver))
    return suite

if __name__ == '__main__':
    framework()
