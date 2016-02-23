#
# Copyright 2015-2016 IBM Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import sys
import os
import json
import subprocess
import codecs

import flask

from gevent.wsgi import WSGIServer

proxy = flask.Flask(__name__)
proxy.debug = False

SRC_EPILOGUE_FILE = "./epilogue.swift"
DEST_SCRIPT_FILE = "/swiftActionSource/action.swift"
PROCESS = [ "swift", DEST_SCRIPT_FILE ]

@proxy.route("/init", methods=['POST'])
def init():
    message = flask.request.get_json(force=True,silent=True)
    if not message or not isinstance(message, dict):
        flask.abort(403)

    message = message.get("value", {})

    if "code" in message:
        with codecs.open(DEST_SCRIPT_FILE, "w", "utf-8") as fp:
            fp.write(str(message["code"]))
            with codecs.open(SRC_EPILOGUE_FILE, "r", "utf-8") as ep:
                fp.write(ep.read())
        return ('OK', 200)
    else:
        flask.abort(403)

@proxy.route("/run", methods=['POST'])
def run():
    message = flask.request.get_json(force=True,silent=True)

    if not message or not isinstance(message, dict):
        flask.abort(403)

    if not "value" in message:
        flask.abort(403)

    value = message["value"]

    if not isinstance(value, dict):
        flask.abort(403)

    swift_env_in = { "WHISK_INPUT" : json.dumps(value) }

    p = subprocess.Popen(
        PROCESS,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        env=swift_env_in)

    # We run the Swift process, blocking until it completes.
    (o,e) = p.communicate()

    process_output = ""

    if o is not None:
        process_output_lines = o.strip().split("\n")

        last_line = process_output_lines[-1]

        for line in process_output_lines[:-1]:
            sys.stdout.write("%s\n" % line)

    if e is not None:
        sys.stderr.write(e)

    try:
        json_output = json.loads(last_line)
        if isinstance(json_output, dict):
            response = flask.jsonify(json_output)
            return response
        else:
            reponse = { "error": "the action did not return an object", "action_output": json_output }
            reponse.status_code = 502
            return response
    except:
        sys.stderr.write("Couldn't parse Swift script output as JSON: %s.\n" % last_line)
        json_output = { "error": "the action did not return a valid result" }
        response = flask.jsonify(json_output)
        response.status_code = 502
        return response

if __name__ == "__main__":
    PORT = int(os.getenv("FLASK_PROXY_PORT", 8080))
    server = WSGIServer(('', PORT), proxy, log=None)
    server.serve_forever()