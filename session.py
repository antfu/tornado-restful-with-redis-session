#/usr/bin/python
# coding: utf-8

import uuid
import hmac
import ujson
import hashlib
import time

class SessionData(dict):
    def __init__(self, session_id, hmac_key):
        self.session_id = session_id
        self.hmac_key = hmac_key
#    @property
#    def sid(self):
#        return self.session_id
#    @x.setter
#    def sid(self, value):
#        self.session_id = value

class Session(SessionData):
    def __init__(self, session_manager, request_handler):

        self.session_manager = session_manager
        self.request_handler = request_handler

        try:
            current_session = session_manager.get(request_handler)
        except InvalidSessionException:
            current_session = session_manager.get()
        for key, data in current_session.items():
            self[key] = data
        self.session_id = current_session.session_id
        self.hmac_key = current_session.hmac_key

    def save(self):
        self.session_manager.set(self.request_handler, self)

    def clear(self):
        self.session_manager.clear(self.request_handler)


class SessionManager(object):
    def __init__(self, configs):
        self.secret = configs['session_secret']
        self.session_timeout = configs['session_timeout']

        if configs['storage']['agent'] == 'redis':
            import redis
            redis_connect = redis.StrictRedis(
                    host=configs['storage']['redis_host'],
                    port=configs['storage']['redis_port'],
                    password=configs['storage']['redis_pass']
                )
            self.storage = {
                'storage': redis_connect,
                'get': lambda _id: redis_connect.get(_id),
                'set': lambda _id,timeout,data: redis_connect.setex(_id,timeout,data)
            }
        else:
            def dict_get(dic,k):
                v = dic.get(k,None)
                if v:
                    if v[0] > time.time():
                        return v[1]
                    else:
                        del(dic[k])
                return None
            def dict_set(dic,k,timeout,v):
                dic[k] = (int(time.time() + timeout * 60),v)
            dict_storage = {}
            self.storage = {
                'storage': dict_storage,
                'get': lambda _id: dict_get(dict_storage,_id),
                'set': lambda _id,timeout,data: dict_set(dict_storage,_id,timeout,data)
             }

    def _fetch(self, session_id):
        try:
            session_data = raw_data = self.storage['get'](session_id)
            if raw_data != None:
                self.storage['set'](session_id, self.session_timeout, raw_data)
                session_data = ujson.loads(raw_data)

            if type(session_data) == type({}):
                return session_data
            else:
                return {}
        except IOError:
            return {}

    def get(self, request_handler = None):
        if (request_handler == None):
            session_id = None
            hmac_key = None
        else:
            session_id = request_handler.get_secure_cookie("session_id").decode()
            hmac_key = request_handler.get_secure_cookie("verification").decode()

        if session_id == None:
            session_exists = False
            session_id = self._generate_id()
            hmac_key = self._generate_hmac(session_id)
        else:
            session_exists = True
        check_hmac = self._generate_hmac(session_id)
        if hmac_key != check_hmac:
            raise InvalidSessionException()

        session = SessionData(session_id, hmac_key)

        if session_exists:
            session_data = self._fetch(session_id)
            for key, data in session_data.items():
                session[key] = data
        return session

    def set(self, request_handler, session):
        request_handler.set_secure_cookie("session_id", session.session_id)
        request_handler.set_secure_cookie("verification", session.hmac_key)

        session_data = ujson.dumps(dict(session.items()))

        self.storage['set'](session.session_id, self.session_timeout, session_data)

    def clear(self, request_handler):
        request_handler.clear_cookie("session_id")
        request_handler.clear_cookie("verification")

    def _generate_id(self):
        new_id = hashlib.sha256((self.secret + str(uuid.uuid4())).encode())
        return new_id.hexdigest()

    def _generate_hmac(self, session_id):
        if isinstance(session_id,str):
            session_id = session_id.encode()
        return hmac.new(session_id, self.secret.encode(), hashlib.sha256).hexdigest()



class InvalidSessionException(Exception):
    pass
