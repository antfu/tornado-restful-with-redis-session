#/usr/bin/python
# coding: utf-8

import sys
sys.path.append("..")

import tornado.ioloop
import restful
from restful import get,post,put,delete
from configs.config import configs

class EchoService(restful.RestHandler):
    @get(path="/echo/{name}")
    def g(self,name,*args,**kwargs):
        return {'name':name,'data':self.response_data,'args':args,'kwargs':kwargs}

    @post(path="/echo/{name}")
    def sayFuck(self,name,*args,**kwargs):
        return {'name':name,'data':self.response_data,'args':args,'kwargs':kwargs}

    @put(path="/echo/{name}")
    def p(self,name,*args,**kwargs):
        return {'name':name,'data':self.response_data,'args':args,'kwargs':kwargs}

    @delete(path="/echo/{name}")
    def d(self,name,*args,**kwargs):
        return {'name':name,'data':self.response_data,'args':args,'kwargs':kwargs}

class SessionService(restful.RestHandler):
    @post(path="/session")
    def post_session(self):
        name = self.response_data.get('username')
        password = self.response_data.get('password')

        # Add some authentication here
        self.session['username'] = name
        self.session.save()
        return self.session

    @get(path="/session")
    def get_session(self):
        return {'name':self.session.get('username')}

    @delete(path="/session")
    def delete_session(self):
        self.session.clear()
        return



if __name__ == '__main__':
     try:
          print("Start the echo service")
          app = restful.RestService(
               [EchoService,SessionService],
               configs.session,
               cookie_secret = configs['cookie_secret']
          )
          app.listen(8080)
          tornado.ioloop.IOLoop.instance().start()
     except KeyboardInterrupt:
          print("\nStop the echo service")
