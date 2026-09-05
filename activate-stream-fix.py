"""Exact-source server-only activation. Never recreates Claude sessions."""
import copy
import http.client
import json
import socket
import subprocess

SOURCE = "qwen38-pango"
BACKUP = "qwen38-pango-before-stream-fix-20260905"
IMAGE = "sha256:db815495d86fa23ffa3c898ca48d3dcb5e2a09240a092fd99e4601bd53274bfa"

def run(*args):
    return subprocess.check_output(args, text=True).strip()

original = json.loads(run("docker", "inspect", SOURCE))[0]
assert original["Image"] == "sha256:6fa3424b7b470632addc9d63edab4f5fd4e80cf0c73c0e48a913c5094169838a"
assert BACKUP not in run("docker", "ps", "-a", "--format", "{{.Names}}").splitlines()
assert run("docker", "image", "inspect", IMAGE, "--format", "{{.Id}}") == IMAGE
config = copy.deepcopy(original["Config"])
assert "--chat-template" not in config["Cmd"]
config["Image"] = IMAGE
config["Cmd"] += ["--chat-template", "/opt/pango-patches/qwen-inline-system.jinja"]
config["HostConfig"] = original["HostConfig"]

class DockerConnection(http.client.HTTPConnection):
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect("/var/run/docker.sock")

run("docker", "stop", "-t", "30", SOURCE)
run("docker", "rename", SOURCE, BACKUP)
conn = DockerConnection("localhost")
conn.request("POST", "/containers/create?name=" + SOURCE, json.dumps(config), {"Content-Type": "application/json"})
response = conn.getresponse()
body = json.loads(response.read())
if response.status != 201:
    run("docker", "rename", BACKUP, SOURCE)
    run("docker", "start", SOURCE)
    raise SystemExit("CREATE_FAILED_ROLLBACK_STARTED HTTP " + str(response.status))
run("docker", "start", SOURCE)
current = json.loads(run("docker", "inspect", SOURCE))[0]
assert current["Config"]["Cmd"] == config["Cmd"]
print(json.dumps({"image": current["Image"], "rollback": BACKUP, "state": "STARTING"}))
