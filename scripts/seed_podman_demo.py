#!/usr/bin/env python3
# Seed Podman install/revert demo projects in a running Ansible WebGUI stack.
# Usage: ./scripts/seed_podman_demo.py [--base-url http://localhost:8000] [--username admin] [--password ...] [--target-host 192.168.0.19] [--ssh-user tejas] [--ssh-password tez@123]

import argparse
import getpass
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar

INSTALL_PLAYBOOK = """---
- name: Install Podman
  hosts: all
  gather_facts: true
  tasks:
    - name: Install podman on Debian family
      ansible.builtin.apt:
        name: podman
        state: present
        update_cache: true
      when: ansible_os_family == "Debian"

    - name: Install podman on RedHat family
      ansible.builtin.dnf:
        name: podman
        state: present
      when: ansible_os_family == "RedHat"

    - name: Fail on unsupported OS family
      ansible.builtin.fail:
        msg: "Unsupported ansible_os_family: {{ ansible_os_family }}"
      when: ansible_os_family not in ["Debian", "RedHat"]

    - name: Read installed podman version
      ansible.builtin.command: podman --version
      register: podman_version
      changed_when: false

    - name: Show installed podman version
      ansible.builtin.debug:
        msg: "{{ podman_version.stdout }}"
"""

REVERT_PLAYBOOK = """---
- name: Revert Podman installation
  hosts: all
  gather_facts: true
  tasks:
    - name: Stop and disable podman socket
      ansible.builtin.systemd:
        name: podman.socket
        state: stopped
        enabled: false
      failed_when: false

    - name: Remove podman on Debian family
      ansible.builtin.apt:
        name: podman
        state: absent
        purge: true
        autoremove: true
      when: ansible_os_family == "Debian"

    - name: Remove podman on RedHat family
      ansible.builtin.dnf:
        name: podman
        state: absent
        autoremove: true
      when: ansible_os_family == "RedHat"

    - name: Purge container data and configuration
      ansible.builtin.file:
        path: "{{ item }}"
        state: absent
      loop:
        - /var/lib/containers
        - /etc/containers
        - "/home/{{ ansible_user }}/.local/share/containers"
        - "/home/{{ ansible_user }}/.config/containers"
"""


def parse_args():
    parser = argparse.ArgumentParser(description="Seed Podman demo projects through the WebGUI REST API.")
    parser.add_argument("--base-url", default=os.environ.get("WEBGUI_URL", "http://localhost:8000"))
    parser.add_argument("--username", default=os.environ.get("BOOTSTRAP_ADMIN_USER", "admin"))
    parser.add_argument("--password", default=os.environ.get("BOOTSTRAP_ADMIN_PASSWORD"))
    parser.add_argument("--target-host", default="192.168.0.19")
    parser.add_argument("--ssh-user", default="tejas")
    parser.add_argument("--ssh-password", default="tez@123")
    return parser.parse_args()


class Api:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip("/")
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))

    def call(self, method, path, body=None):
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            method=method,
            headers={"Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest"},
        )
        try:
            with self.opener.open(req) as resp:
                raw = resp.read().decode()
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode()
            try:
                detail = json.loads(raw).get("detail", {})
            except json.JSONDecodeError:
                detail = {}
            code = detail.get("code", f"http_{exc.code}") if isinstance(detail, dict) else f"http_{exc.code}"
            message = detail.get("message", raw) if isinstance(detail, dict) else raw
            raise SystemExit(f"{method} {path} failed: {code}: {message}") from None
        return json.loads(raw) if raw else {}


def by_name(items, name):
    return next((item for item in items if item.get("name") == name), None)


def status(action, kind, name):
    print(f"{action}: {kind} {name}")


def ensure_credential(api, project_id, name, kind, username, payload):
    existing = by_name(api.call("GET", f"/api/credentials?project_id={project_id}"), name)
    if existing:
        # ponytail: backend PATCH cannot accept JSON null for username; empty string normalizes to None.
        api.call("PATCH", f"/api/credentials/{existing['id']}", {"username": username if username is not None else "", "payload": payload})
        status("reused (updated)", "credential", name)
        return existing
    created = api.call("POST", "/api/credentials", {"project_id": project_id, "name": name, "kind": kind, "username": username, "payload": payload})
    status("created", "credential", name)
    return created


def ensure_created(api, path, name, body, kind, query=""):
    existing = by_name(api.call("GET", f"{path}{query}"), name)
    if existing:
        status("reused", kind, name)
        return existing
    created = api.call("POST", path, body)
    status("created", kind, name)
    return created

def ensure_inventory(api, content):
    existing = by_name(api.call("GET", "/api/inventories"), "demo-podman-host")
    body = {"filename": "demo-podman-host.ini", "name": "demo-podman-host", "format": "ini", "content": content, "message": "Seed podman demo inventory"}
    if existing:
        api.call("POST", f"/api/inventories/{existing['id']}/file", {"content": content, "message": "Update podman demo inventory"})
        status("reused (updated)", "inventory", "demo-podman-host")
        return existing
    created = api.call("POST", "/api/inventories", body)
    status("created", "inventory", "demo-podman-host")
    return created



def ensure_template(api, project_id, name, body):
    query = "?" + urllib.parse.urlencode({"project_id": project_id})
    existing = by_name(api.call("GET", f"/api/job_templates{query}"), name)
    if existing:
        update = {k: v for k, v in body.items() if k != "project_id"}
        api.call("PATCH", f"/api/job_templates/{existing['id']}", update)
        status("reused (updated)", "template", name)
        return {**existing, **update}
    created = api.call("POST", "/api/job_templates", body)
    status("created", "template", name)
    return created


def main():
    args = parse_args()
    if args.password is None:
        args.password = getpass.getpass("WebGUI password: ")
    print("WARNING: seeding a plaintext lab credential")

    api = Api(args.base_url)
    api.call("POST", "/api/auth/login", {"username": args.username, "password": args.password})


    inventory_content = f"""[podman_hosts]
{args.target_host}

[podman_hosts:vars]
ansible_user={args.ssh_user}
ansible_become=true
ansible_become_method=sudo
ansible_python_interpreter=auto_silent
ansible_ssh_common_args=-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null
"""
    inventory = ensure_inventory(api, inventory_content)

    install_project = ensure_created(api, "/api/projects", "podman-install-demo", {"name": "podman-install-demo"}, "project")
    revert_project = ensure_created(api, "/api/projects", "podman-revert-demo", {"name": "podman-revert-demo"}, "project")

    ssh_install = ensure_credential(api, install_project["id"], "demo-tejas-ssh", "ssh_password", args.ssh_user, args.ssh_password)
    become_install = ensure_credential(api, install_project["id"], "demo-tejas-become", "become_password", None, args.ssh_password)

    ssh_revert = ensure_credential(api, revert_project["id"], "demo-tejas-ssh", "ssh_password", args.ssh_user, args.ssh_password)
    become_revert = ensure_credential(api, revert_project["id"], "demo-tejas-become", "become_password", None, args.ssh_password)

    install_playbook = ensure_created(api, "/api/playbooks", "install-podman", {"project_id": install_project["id"], "rel_path": "playbooks/install_podman.yml", "name": "install-podman", "content": INSTALL_PLAYBOOK, "message": "Seed install-podman"}, "playbook", "?" + urllib.parse.urlencode({"project_id": install_project["id"]}))
    revert_playbook = ensure_created(api, "/api/playbooks", "revert-podman", {"project_id": revert_project["id"], "rel_path": "playbooks/revert_podman.yml", "name": "revert-podman", "content": REVERT_PLAYBOOK, "message": "Seed revert-podman"}, "playbook", "?" + urllib.parse.urlencode({"project_id": revert_project["id"]}))

    common = {"inventory_id": inventory["id"], "extra_vars": {}, "verbosity": 0, "forks": 5, "requires_approval": False, "diff_mode": False, "survey_spec": [], "ask_limit": True, "ask_extra_vars": True}
    install_template_name = f"Install Podman on {args.target_host}"
    revert_template_name = f"Revert Podman on {args.target_host}"
    ensure_template(api, install_project["id"], install_template_name, {**common, "credential_ids": [ssh_install["id"], become_install["id"]], "project_id": install_project["id"], "name": install_template_name, "playbook_id": install_playbook["id"]})
    ensure_template(api, revert_project["id"], revert_template_name, {**common, "credential_ids": [ssh_revert["id"], become_revert["id"]], "project_id": revert_project["id"], "name": revert_template_name, "playbook_id": revert_playbook["id"]})

    print(f"Template: {install_template_name}")
    print(f"Template: {revert_template_name}")
    print("Launch: Jobs -> Launch job -> pick template -> set mode=live -> Launch")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("aborted")
