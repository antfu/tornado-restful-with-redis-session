#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author: Anthony
# @Date:   2016-02-12 00:02:53
# @Last Modified by:   Anthony
# @Last Modified time: 2016-02-19 23:11:30

__version__ = (0,0,0,2)

import tornado.ioloop
import tornado.web
import re
import json
import inspect
import sys
import session
import functools

def auth_required(auth_check = lambda x: bool(x)):
    ''' Decorator for checking authentication '''
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kw):
            username = self.session.get('username',None)
            if auth_check(username):
                return func(self,*args,**kw)
            else:
                self.write(json.dumps(dict(error='Authentication required.')))
                self.set_status(401)
                return
        return wrapper
    return decorator

def config(func, method, path, **kwparams):
    """ Decorator config function """
    def operation(*args,**kwargs):
        return func(*args,**kwargs)

    operation.func_name       = func.__name__
    operation._func_params    = inspect.getargspec(func).args[1:]
    operation._service_name   = re.findall(r"(?<=/)\w+",path)
    operation._service_params = re.findall(r"(?<={)\w+",path)
    operation._method         = method
    operation._query_params   = re.findall(r"(?<=<)\w+",path)
    operation._path           = path

    return operation

def get(path, *params, **kwparams):
    """ Decorator for config a python function like a Rest GET verb """
    def method(f):
        return config(f, 'GET', path, **kwparams)
    return method

def post(path, *params, **kwparams):
    """ Decorator for config a python function like a Rest POST verb    """
    def method(f):
        return config(f, 'POST', path, **kwparams)
    return method

def put(path, *params, **kwparams):
    """ Decorator for config a python function like a Rest PUT verb """
    def method(f):
        return config(f, 'PUT', path, **kwparams)
    return method

def delete(path, *params, **kwparams):
    """ Decorator for config a python function like a Rest PUT verb """
    def method(f):
        return config(f, 'DELETE', path, **kwparams)
    return method


class RestService(session.SessionApplication):
    """ Class to create Rest services in tornado web server """
    def __init__(self, rest_handlers, session_configs, resource=None,
                 handlers=None, *args, **kwargs):
        restservices = []
        self.resource = resource
        for r in rest_handlers:
            svs = self._generateRestServices(r)
            restservices += svs
        if handlers != None:
            restservices += handlers
        session.SessionApplication.__init__(self, session_configs,
                                    handlers = restservices, *args, **kwargs)

    def _generateRestServices(self,rest):
        svs = []
        paths = rest.get_paths()
        for p in paths:
            s = re.sub(r"(?<={)\w+}",".*",p).replace("{","")
            o = re.sub(r"(?<=<)\w+","",s).replace("<","").replace(">","").replace("&","").replace("?","")
            svs.append((o,rest,self.resource))
        return svs

class RestHandler(session.SessionHandler):
    def get(self):
        """ Executes get method """
        self._exe('GET')

    def post(self):
        """ Executes post method """
        self._exe('POST')

    def put(self):
        """ Executes put method"""
        self._exe('PUT')

    def delete(self):
        """ Executes put method"""
        self._exe('DELETE')

    def _exe(self, method):
        """ Executes the python function for the Rest Service """
        request_path = self.request.path
        path = request_path.split('/')
        services_and_params = list(filter(lambda x: x!='',path))

        # Get all function names configured in the class RestHandler
        functions    = list(filter(lambda op: hasattr(getattr(self,op),'_service_name') == True and inspect.ismethod(getattr(self,op)) == True, dir(self)))
        # Get all http methods configured in the class RestHandler
        http_methods = list(map(lambda op: getattr(getattr(self,op),'_method'), functions))

        if method not in http_methods:
            raise tornado.web.HTTPError(405,'The service not have %s verb' % method)
        for operation in list(map(lambda op: getattr(self,op), functions)):
            service_name          = getattr(operation,"_service_name")
            service_params        = getattr(operation,"_service_params")
            # If the _types is not specified, assumes str types for the params
            services_from_request = list(filter(lambda x: x in path,service_name))

            if operation._method == self.request.method and service_name == services_from_request and len(service_params) + len(service_name) == len(services_and_params):
                try:
                    params_values = self._find_params_value_of_url(service_name,request_path) + self._find_params_value_of_arguments(operation)
                    p_values      = self._convert_params_values(params_values)
                    body = str(self.request.body,'utf-8')
                    self.request_data = None
                    if body:
                        self.request_data = json.loads(body)
                    response = operation(*p_values)
                    self.request_data = None

                    if response == None:
                        return

                    self.set_header("Content-Type",'application/json')
                    self.write(json.dumps(response))
                    self.finish()
                except Exception as detail:
                    self.request_data = None
                    self.gen_http_error(500,"Internal Server Error : %s"%detail)
                    raise

    def _find_params_value_of_url(self, services, url):
        """ Find the values of path params """
        values_of_query = list()
        url_split = url.split("/")
        values = [item for item in url_split if item not in services and item != '']
        for v in values:
            if v != None:
                values_of_query.append(v)
        return values_of_query

    def _find_params_value_of_arguments(self, operation):
        values = []
        if len(self.request.arguments) > 0:
            a = operation._service_params
            b = operation._func_params
            params = [item for item in b if item not in a]
            for p in params:
                if p in self.request.arguments.keys():
                    v = self.request.arguments[p]
                    values.append(v[0])
                else:
                    values.append(None)
        elif len(self.request.arguments) == 0 and len(operation._query_params) > 0:
            values = [None]*(len(operation._func_params) - len(operation._service_params))
        return values

    def _convert_params_values(self, values_list):
        """ Converts the values to the specifics types """
        values = list()
        for v in values_list:
            values.append(v)
        return values

    def gen_http_error(self, status, msg):
        """ Generates the custom HTTP error """
        self.clear()
        self.set_status(status)
        self.write(json.dumps(dict(error=str(msg))))
        self.finish()

    @classmethod
    def get_services(self):
        """ Generates the resources (uri) to deploy the Rest Services """
        services = []
        for f in dir(self):
            o = getattr(self, f)
            if callable(o) and hasattr(o, '_service_name'):
                services.append(getattr(o, '_service_name'))
        return services

    @classmethod
    def get_paths(self):
        """ Generates the resources from path (uri) to deploy the Rest Services """
        paths = []
        for f in dir(self):
            o = getattr(self, f)
            if callable(o) and hasattr(o, '_path'):
                paths.append(getattr(o, '_path'))
        return paths

    @classmethod
    def get_handlers(self):
        """ Gets a list with (path, handler) """
        svs = []
        paths = self.get_paths()
        for p in paths:
            s = re.sub(r"(?<={)\w+}", ".*", p).replace("{", "")
            o = re.sub(r"(?<=<)\w+", "", s).replace("<", "").replace(">","").replace("&", "").replace("?", "")
            svs.append((o, self))

        return svs
