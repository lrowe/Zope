##############################################################################
# 
# Zope Public License (ZPL) Version 1.0
# -------------------------------------
# 
# Copyright (c) Digital Creations.  All rights reserved.
# 
# This license has been certified as Open Source(tm).
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
# 
# 1. Redistributions in source code must retain the above copyright
#    notice, this list of conditions, and the following disclaimer.
# 
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions, and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
# 
# 3. Digital Creations requests that attribution be given to Zope
#    in any manner possible. Zope includes a "Powered by Zope"
#    button that is installed by default. While it is not a license
#    violation to remove this button, it is requested that the
#    attribution remain. A significant investment has been put
#    into Zope, and this effort will continue if the Zope community
#    continues to grow. This is one way to assure that growth.
# 
# 4. All advertising materials and documentation mentioning
#    features derived from or use of this software must display
#    the following acknowledgement:
# 
#      "This product includes software developed by Digital Creations
#      for use in the Z Object Publishing Environment
#      (http://www.zope.org/)."
# 
#    In the event that the product being advertised includes an
#    intact Zope distribution (with copyright and license included)
#    then this clause is waived.
# 
# 5. Names associated with Zope or Digital Creations must not be used to
#    endorse or promote products derived from this software without
#    prior written permission from Digital Creations.
# 
# 6. Modified redistributions of any form whatsoever must retain
#    the following acknowledgment:
# 
#      "This product includes software developed by Digital Creations
#      for use in the Z Object Publishing Environment
#      (http://www.zope.org/)."
# 
#    Intact (re-)distributions of any official Zope release do not
#    require an external acknowledgement.
# 
# 7. Modifications are encouraged but must be packaged separately as
#    patches to official Zope releases.  Distributions that do not
#    clearly separate the patches from the original work must be clearly
#    labeled as unofficial distributions.  Modifications which do not
#    carry the name Zope may be packaged in any form, as long as they
#    conform to all of the clauses above.
# 
# 
# Disclaimer
# 
#   THIS SOFTWARE IS PROVIDED BY DIGITAL CREATIONS ``AS IS'' AND ANY
#   EXPRESSED OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
#   IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
#   PURPOSE ARE DISCLAIMED.  IN NO EVENT SHALL DIGITAL CREATIONS OR ITS
#   CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
#   SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
#   LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF
#   USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
#   ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
#   OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT
#   OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
#   SUCH DAMAGE.
# 
# 
# This software consists of contributions made by Digital Creations and
# many individuals on behalf of Digital Creations.  Specific
# attributions are listed in the accompanying credits file.
# 
##############################################################################
__doc__="""Python Object Publisher -- Publish Python objects on web servers

$Id: Publish.py,v 1.135 1999/08/04 18:05:28 jim Exp $"""
__version__='$Revision: 1.135 $'[11:-2]

import sys, os
from string import lower, atoi, rfind, strip
from Response import Response
from Request import Request
from maybe_lock import allocate_lock
from mapply import mapply

class Retry(Exception):
    """Raise this to retry a request
    """

def call_object(object, args, request):
    result=apply(object,args) # Type s<cr> to step into published object.
    return result

def missing_name(name, request):
    if name=='self': return request['PARENTS'][0]
    request.response.badRequestError(name)

def dont_publish_class(klass, request):
    request.response.forbiddenError("class %s" % klass.__name__)

def publish(request, module_name, after_list, debug=0,
            # Optimize:
            call_object=call_object,
            missing_name=missing_name,
            dont_publish_class=dont_publish_class,
            mapply=mapply,
            ):

    (bobo_before, bobo_after, object, realm, debug_mode, err_hook,
     have_transactions)= get_module_info(module_name)

    parents=None

    try:
        request.processInputs()

        request_get=request.get
        response=request.response
    
        # First check for "cancel" redirect:
        cancel=''
        if lower(strip(request_get('SUBMIT','')))=='cancel':
            cancel=request_get('CANCEL_ACTION','')
            if cancel: raise 'Redirect', cancel
    
        after_list[0]=bobo_after
        if debug_mode: response.debug_mode=debug_mode
        if realm and not request.get('REMOTE_USER',None):
            response.realm=realm
    
        if bobo_before is not None: bobo_before();
    
        # Get a nice clean path list:
        path=strip(request_get('PATH_INFO'))
    
        request['PARENTS']=parents=[object]
        
        if have_transactions: get_transaction().begin()
    
        object=request.traverse(path)
    
        # Record transaction meta-data
        if have_transactions:
            get_transaction().note(request_get('PATH_INFO'))
            auth_user=request_get('AUTHENTICATED_USER',None)
            if auth_user is not None:
                get_transaction().setUser(auth_user,
                                          request_get('AUTHENTICATION_PATH'))
    
        result=mapply(object, request.args, request,
                      call_object,1,
                      missing_name, 
                      dont_publish_class,
                      request)
    
        if result is not response: response.setBody(result)
    
        if have_transactions: get_transaction().commit()

        return response

    except:
        if err_hook is not None:
            if parents: parents=parents[-1]
            try:
                return err_hook(parents, request,
                                sys.exc_info()[0],
                                sys.exc_info()[1],
                                sys.exc_info()[2],
                                )
            except Retry:
                # We need to try again....
                if not request.supports_retry():
                    return err_hook(parents, request,
                                    sys.exc_info()[0],
                                    sys.exc_info()[1],
                                    sys.exc_info()[2],
                                    )
                return publish(request.retry(), module_name, after_list, debug)
        else: raise
            

def publish_module(module_name,
                   stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr,
                   environ=os.environ, debug=0, request=None, response=None):
    must_die=0
    status=200
    after_list=[None]
    try:
        try:
            if response is None:
                response=Response(stdout=stdout, stderr=stderr)
            else:
                stdout=response.stdout

            if request is None:
                request=Request(stdin, environ, response)

            response = publish(request, module_name, after_list, debug=debug)
        except SystemExit, v:
            if hasattr(sys, 'exc_info'): must_die=sys.exc_info()
            else: must_die = SystemExit, v, sys.exc_traceback
            response.exception(must_die)
        except ImportError, v:
            if type(v) is type(()) and len(v)==3: must_die=v
            elif hasattr(sys, 'exc_info'): must_die=sys.exc_info()
            else: must_die = SystemExit, v, sys.exc_traceback
            response.exception(1, v)
        except:
            response.exception()
            status=response.getStatus()

        if response:
            response=str(response)
            if response:
                stdout.write(response)

        # The module defined a post-access function, call it
        if after_list[0] is not None: after_list[0]()

    finally:
        if request is not None: request.other={}

    if must_die: raise must_die[0], must_die[1], must_die[2]
    sys.exc_type, sys.exc_value, sys.exc_traceback = None, None, None
    return status


_l=allocate_lock()
def get_module_info(module_name, modules={},
                    acquire=_l.acquire,
                    release=_l.release,
                    ):

    if modules.has_key(module_name): return modules[module_name]

    if module_name[-4:]=='.cgi': module_name=module_name[:-4]

    acquire()
    tb=None
    try:
      try:
        module=__import__(module_name, globals(), globals(), ('__doc__',))
    
        realm=module_name
                
        # Let the app specify a realm
        if hasattr(module,'__bobo_realm__'):
            realm=module.__bobo_realm__
        elif os.environ.has_key('Z_REALM'):
            realm=os.environ['Z_REALM']
        elif os.environ.has_key('BOBO_REALM'):
            realm=os.environ['BOBO_REALM']
        else: realm=module_name

        # Check for debug mode
        if hasattr(module,'__bobo_debug_mode__'):
            debug_mode=not not module.__bobo_debug_mode__
        elif (os.environ.has_key('Z_DEBUG_MODE') or
              os.environ.has_key('BOBO_DEBUG_MODE')):
            if os.environ.has_key('Z_DEBUG_MODE'):
                debug_mode=lower(os.environ['Z_DEBUG_MODE'])
            else:
                debug_mode=lower(os.environ['BOBO_DEBUG_MODE'])
            if debug_mode=='y' or debug_mode=='yes':
                debug_mode=1
            else:
                try: debug_mode=atoi(debug_mode)
                except: debug_mode=None
        else: debug_mode=None
 
        if hasattr(module,'__bobo_before__'):
            bobo_before=module.__bobo_before__
        else: bobo_before=None
                
        if hasattr(module,'__bobo_after__'): bobo_after=module.__bobo_after__
        else: bobo_after=None
    
        if hasattr(module,'bobo_application'):
            object=module.bobo_application
        elif hasattr(module,'web_objects'):
            object=module.web_objects
        else: object=module

        error_hook=getattr(module,'zpublisher_exception_hook', None)

        try: get_transaction()
        except: have_transactions=0
        else: have_transactions=1
    
        info= (bobo_before, bobo_after, object, realm, debug_mode,
               error_hook, have_transactions)
    
        modules[module_name]=modules[module_name+'.cgi']=info

        return info
      except:
          t,v,tb=sys.exc_info()
          v=str(v)
          raise ImportError, (t, v), tb
    finally:
        tb=None
        release()
