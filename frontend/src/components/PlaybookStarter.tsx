export function playbookStarter(name: string) {
  return `---
- name: ${name}
  hosts: all
  become: false
  gather_facts: true
  tasks:
    - name: Ping hosts
      ansible.builtin.ping:
`;
}

export const slugPath = (name: string) => `playbooks/${name.toLowerCase().replace(/[^a-z0-9._-]/g, "-")}.yml`;

export interface Starter { id: string; label: string; description: string; build(name: string): string }

export const PLAYBOOK_STARTERS: Starter[] = [
  { id: "ping", label: "Ping check", description: "Verify connectivity to every host.", build: playbookStarter },
  { id: "packages", label: "Install packages", description: "Install a list of packages with the OS package manager.", build: (name: string) => `---
- name: ${name}
  hosts: all
  become: true
  gather_facts: true
  vars:
    packages:
      - htop
  tasks:
    - name: Install packages
      ansible.builtin.package:
        name: "{{ packages }}"
        state: present
` },
  { id: "service", label: "Restart service", description: "Ensure a service is enabled and restarted.", build: (name: string) => `---
- name: ${name}
  hosts: all
  become: true
  gather_facts: false
  vars:
    service_name: nginx
  tasks:
    - name: Restart service
      ansible.builtin.service:
        name: "{{ service_name }}"
        state: restarted
        enabled: true
` },
  { id: "blank", label: "Blank", description: "Start from an empty play.", build: (name: string) => `---
- name: ${name}
  hosts: all
  tasks: []
` },
];

export function playbookEditorOptions(readOnly = false) {
  return {
    readOnly,
    minimap: { enabled: false },
    wordWrap: "off" as const,
    lineNumbers: "on" as const,
    renderLineHighlight: "all" as const,
    stickyScroll: { enabled: true },
    scrollBeyondLastLine: false,
    automaticLayout: true,
    tabSize: 2,
    insertSpaces: true,
  };
}
