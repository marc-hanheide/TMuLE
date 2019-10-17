#!/usr/bin/env python

from __future__ import print_function

from os import path
from uuid import uuid4

from json import loads, dumps
from pprint import pformat

from autobahn.twisted.websocket import WebSocketServerProtocol, \
    WebSocketServerFactory

from autobahn.twisted.resource import WebSocketResource, WSGIRootResource
from twisted.python import log

class JsonWSProtocol(WebSocketServerProtocol):

    def onConnect(self, request):
        log.msg("Client connecting: {0}".format(request.peer))

    def onOpen(self):
        log.msg("WebSocket connection open.")
        self.wait_responses = {}

    def sendJSON(self, data, callback=None):
        data = data.copy()
        data['_id'] = str(uuid4())
        if callback:
            self.wait_responses[data['_id']] = callback
        buf = dumps(data)
        self.sendMessage(buf.encode('utf-8'), False)

    def onMessage(self, payload, isBinary):
        # Debug
        if isBinary:
            log.msg("Binary message received: {0} bytes".format(len(payload)))
        else:
            message_text = payload.decode('utf8')
            payload = loads(message_text)
            result = self._dispatch(payload)
            if result:
                try:
                    r = result.copy()
                    r['_response_to'] = payload['_id']
                    r['_query'] = payload
                    self.sendJSON(r)
                except Exception as e:
                    log.err(e)

    def _dispatch(self, payload):
        if 'method' in payload:
            method = payload['method']
            try:
                method_to_call = getattr(self, 'on_%s' % method)
                log.msg('dispatch to method on_%s' % method)
            except AttributeError as e:
                log.err(e, 'cannot dispatch method %s' % method)
                return
            return method_to_call(payload)
        elif '_response_to' in payload:
            if payload['_response_to'] in self.wait_responses:
                log.msg('got a response we have been waiting for')
                method = self.wait_responses.pop(payload['_response_to'])
                method(payload)

            log.msg('got a response to %s for method %s' %
                 (payload['_response_to'], payload['_query']['method']))
        else:
            log.err("don't know what to do with message %s" % pformat(payload))

    def onJSON(self, payload):
        log.err('should be overwritten')

    def onClose(self, wasClean, code, reason):
        log.msg("WebSocket connection closed: {0}".format(reason))


class EchoJSONProtocol(JsonWSProtocol):
    def onJSON(self, payload):
        log.msg('echo called')
        return payload


