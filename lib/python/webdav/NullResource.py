##############################################################################
#
# Zope Public License (ZPL) Version 0.9.4
# ---------------------------------------
# 
# Copyright (c) Digital Creations.  All rights reserved.
# 
# Redistribution and use in source and binary forms, with or
# without modification, are permitted provided that the following
# conditions are met:
# 
# 1. Redistributions in source code must retain the above
#    copyright notice, this list of conditions, and the following
#    disclaimer.
# 
# 2. Redistributions in binary form must reproduce the above
#    copyright notice, this list of conditions, and the following
#    disclaimer in the documentation and/or other materials
#    provided with the distribution.
# 
# 3. Any use, including use of the Zope software to operate a
#    website, must either comply with the terms described below
#    under "Attribution" or alternatively secure a separate
#    license from Digital Creations.
# 
# 4. All advertising materials, documentation, or technical papers
#    mentioning features derived from or use of this software must
#    display the following acknowledgement:
# 
#      "This product includes software developed by Digital
#      Creations for use in the Z Object Publishing Environment
#      (http://www.zope.org/)."
# 
# 5. Names associated with Zope or Digital Creations must not be
#    used to endorse or promote products derived from this
#    software without prior written permission from Digital
#    Creations.
# 
# 6. Redistributions of any form whatsoever must retain the
#    following acknowledgment:
# 
#      "This product includes software developed by Digital
#      Creations for use in the Z Object Publishing Environment
#      (http://www.zope.org/)."
# 
# 7. Modifications are encouraged but must be packaged separately
#    as patches to official Zope releases.  Distributions that do
#    not clearly separate the patches from the original work must
#    be clearly labeled as unofficial distributions.
# 
# Disclaimer
# 
#   THIS SOFTWARE IS PROVIDED BY DIGITAL CREATIONS ``AS IS'' AND
#   ANY EXPRESSED OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
#   LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND
#   FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.  IN NO EVENT
#   SHALL DIGITAL CREATIONS OR ITS CONTRIBUTORS BE LIABLE FOR ANY
#   DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
#   CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
#   PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
#   DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
#   ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
#   LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
#   IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF
#   THE POSSIBILITY OF SUCH DAMAGE.
# 
# Attribution
# 
#   Individuals or organizations using this software as a web site
#   must provide attribution by placing the accompanying "button"
#   and a link to the accompanying "credits page" on the website's
#   main entry point.  In cases where this placement of
#   attribution is not feasible, a separate arrangment must be
#   concluded with Digital Creations.  Those using the software
#   for purposes other than web sites must provide a corresponding
#   attribution in locations that include a copyright using a
#   manner best suited to the application environment.
# 
# This software consists of contributions made by Digital
# Creations and many individuals on behalf of Digital Creations.
# Specific attributions are listed in the accompanying credits
# file.
# 
##############################################################################

"""WebDAV support - null resource objects."""

__version__='$Revision: 1.10 $'[11:-2]

import sys, os, string, mimetypes
import Acquisition, OFS.content_types
from common import absattr, aq_base, urlfix
from AccessControl.Permission import Permission
from Resource import Resource
from Globals import Persistent


class NullResource(Persistent, Acquisition.Implicit, Resource):
    """Null resources are used to handle HTTP method calls on
    objects which do not yet exist in the url namespace."""

    __dav_null__=1

    __ac_permissions__=(
        ('View',                             ('HEAD',)),
        ('Access contents information',      ('PROPFIND',)),
        ('Add Documents, Images, and Files', ('PUT',)),
        ('Add Folders',                      ('MKCOL',)),
        ('Delete objects',                   ('DELETE',)),
        ('Manage properties',                ('PROPPATCH',)),
    )

    def __init__(self, parent, name, request=None):
        self.__name__=name
        self.__parent__=parent

#        if hasattr(parent, '__ac_permissions__'):
#            for p in parent.__ac_permissions__:
#                n, v=p[:2]
#                if n=='Add Documents, Images, and Files':
#                    roles=Permission(n, v, parent).getRoles()
#                    break
#            self.PUT__roles__=roles

    def __bobo_traverse__(self, REQUEST, name=None):
        # We must handle traversal so that we can recognize situations
        # where a 409 Conflict must be returned instead of the normal
        # 404 Not Found, per [WebDAV 8.3.1].
        try:    return getattr(self, name)
        except: pass
        method=REQUEST.get('REQUEST_METHOD', 'GET')
        if method in ('MKCOL',):
            raise 'Conflict', 'Collection ancestors must already exist.'
        raise 'Not Found', 'The requested resource was not found.'

    def HEAD(self, REQUEST, RESPONSE):
        """Retrieve resource information without a response message body."""
        self.dav__init(REQUEST, RESPONSE)
        raise 'Not Found', 'The requested resource does not exist.'

    # Most methods return 404 (Not Found) for null resources.
    DELETE=OPTIONS=TRACE=PROPFIND=PROPPATCH=COPY=MOVE=HEAD

    def PUT(self, REQUEST, RESPONSE):
        """Create a new non-collection resource."""
        self.dav__init(REQUEST, RESPONSE)
        type=REQUEST.get_header('content-type', None)
        body=REQUEST.get('BODY', '')
        name=self.__name__
        if type is None:
            type, enc=mimetypes.guess_type(name)
        if type is None:
            if OFS.content_types.find_binary(body) >= 0:
                content_type='application/octet-stream'
            else: type=OFS.content_types.text_type(body)
        type=string.lower(type)
        from OFS.Image import Image, File
        if type in ('text/html', 'text/xml', 'text/plain'):
            self.__parent__.manage_addDTMLDocument(name, '', body)
        elif type[:6]=='image/':
            ob=Image(name, '', body, content_type=type)
            self.__parent__._setObject(name, ob)
        else:
            ob=File(name, '', body, content_type=type)
            self.__parent__._setObject(name, ob)
        RESPONSE.setStatus(201)
        RESPONSE.setBody('')
        return RESPONSE

    def MKCOL(self, REQUEST, RESPONSE):
        """Create a new collection resource."""
        self.dav__init(REQUEST, RESPONSE)
        if REQUEST.get('BODY', ''):
            raise 'Unsupported Media Type', 'Unknown request body.'
        parent=self.__parent__
        name=self.__name__
        if hasattr(aq_base(parent), name):
            raise 'Method Not Allowed', 'The name %s is in use.' % name
        if not hasattr(parent, '__dav_collection__'):
            raise 'Forbidden', 'Unable to create collection resource.'
        parent.manage_addFolder(name)
        RESPONSE.setStatus(201)
        RESPONSE.setBody('')
        return RESPONSE

    def LOCK(self, REQUEST, RESPONSE):
        """Create a lock-null resource."""
        self.dav__init(REQUEST, RESPONSE)
        raise 'Method Not Allowed', 'Method not supported for this resource.'
    
    def UNLOCK(self):
        """Remove a lock-null resource."""
        self.dav__init(REQUEST, RESPONSE)
        raise 'Method Not Allowed', 'Method not supported for this resource.'
