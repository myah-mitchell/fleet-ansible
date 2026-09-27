# ansible

Ansible playbooks with two jobs. `provision.yml` configures and hardens Proxmox hosts (VE, PBS and PMG) and other Debian-based hosts. `site.yml` builds the fleet's NixOS VMs: it creates each VM, installs NixOS on it, and deploys its stacks through Komodo.

The repo runs as it is against the included example inventory, `hosts.yml`, which holds placeholder data only: no real hostnames, keys, certificates or credentials. To layer your real data on top, see [Using your own environment](#using-your-own-environment).

## What the control node needs

The control node is the machine `ansible-playbook` runs on. What it needs depends on the playbook.

| Tool | Needed by | What for |
| --- | --- | --- |
| ansible-core >= 2.15 | Every playbook | `ansible.builtin.deb822_repository` |
| The collections in `requirements.yml` | Every playbook | Installed with `ansible-galaxy` |
| Python's netaddr and jmespath | `provision.yml` | The `ansible.utils.ipaddr` and `json_query` filters |
| sshpass | `provision.yml` | Password logins with `--ask-pass` |
| nix, with flakes enabled | `site.yml`, and `provision.yml` on a Proxmox VE host | Installing and deploying NixOS, and building the installer ISO |
| sops, with the age key | Every playbook, once the inventory has a sops file | Decrypting `group_vars/all/secrets.sops.yaml` |
| OpenTofu | `site.yml` | Creating the VMs |

netaddr and jmespath run on the control node, so whichever Python `ansible-playbook` runs under has to be able to import them. `provision.yml` uses `json_query` in its own target prompt, so it needs both on every run, not only for a Proxmox VE host.

Flakes are enabled by this line in `/etc/nix/nix.conf` or `~/.config/nix/nix.conf`:

```ini
experimental-features = nix-command flakes
```

sops reads the age key from `SOPS_AGE_KEY` or `SOPS_AGE_KEY_FILE` in the environment. The example inventory has no sops file, so it needs neither sops nor a key.

With nix on the control node, the other tools can come from it, with nothing installed:

```bash
nix shell nixpkgs#ansible nixpkgs#sops nixpkgs#opentofu -c \
  ansible-playbook -i ../fleet-private/hosts.yml site.yml -e target=ex01
```

## Quick start

This provisions the machine you run it on, as the example host `ubuntu`, on a current Debian or Ubuntu release.

```bash
sudo apt install git ansible sudo python3-netaddr python3-jmespath sshpass figlet

git clone https://github.com/myah-mitchell/ansible /tmp/ansible
cd /tmp/ansible

ansible-galaxy install -r requirements.yml

ansible-playbook -i hosts.yml -c local provision.yml \
  -e '{"target":"ubuntu", "server_password":"", "short_name":"", "abbr_name":"", "location_abbr":"", "domain_name":""}'
```

`provision.yml` needs `server_password` and four identity values: `short_name`, `abbr_name`, `location_abbr` and `domain_name`. The commands here pass them with `-e`, which sets them for the whole run. They can also live in the inventory, per host, per group, or fleet-wide under `all: vars:` in `hosts.yml`, but only when `-e` leaves them out, since `-e` always wins.

Whatever neither sets is asked for once at the start of the run. Without a terminal, as under Semaphore, nothing can be asked. A missing identity value then stops the run, and a missing `server_password` counts as empty, which leaves every password as it is.

### Running from a virtualenv instead

The quick start installs into the system's Python. To keep this repo's dependencies apart, use a virtualenv for the Python side. `figlet` and `sudo` stay system packages either way.

```bash
sudo apt install git python3-venv sshpass figlet

git clone https://github.com/myah-mitchell/ansible /tmp/ansible
cd /tmp/ansible

python3 -m venv .venv
source .venv/bin/activate
pip install ansible-core netaddr jmespath

ansible-galaxy install -r requirements.yml

ansible-playbook -i hosts.yml -c local provision.yml \
  -e '{"target":"ubuntu", "server_password":"", "short_name":"", "abbr_name":"", "location_abbr":"", "domain_name":""}'
```

Run `source .venv/bin/activate` again in any new shell before using `ansible-playbook` or `ansible-galaxy`.

### Running against a remote host

The quick start uses `-c local`, so everything runs on the machine you call `ansible-playbook` from. To provision a remote host over SSH instead:

1. Set the host's `ansible_host` to its real address, in `hosts.yml` or in your private repo's inventory.
2. Drop `-c local`, so Ansible connects over SSH.
3. Connect as `root`, or as an existing account that can use sudo, for the first run. A new host has no `ansible` account yet, since the `users` role creates it on that run.

```bash
ansible-playbook -i hosts.yml provision.yml \
  -e '{"target":"pve_host", "server_password":"", "short_name":"", "abbr_name":"", "location_abbr":"", "domain_name":""}' \
  -u root --ask-pass --ask-become-pass
```

| Option | What it does |
| --- | --- |
| `-u root` | Picks the connecting user, in place of `ansible_account` |
| `--ask-pass` | Asks for the SSH password. Use `--private-key` with a path instead for key authentication |
| `--ask-become-pass` | Asks for the password that privilege escalation needs. Drop it when the account has passwordless sudo, or when you connect as `root` |

On later runs, drop `-u root` and the password options. The `users` role has created the `ansible` account and installed your `ansible_ssh_public_keys` on it, so Ansible connects as that account with its key.

`provision.yml` never runs against a NixOS VM. Those are built by `site.yml`.

## From nothing to running stacks: site.yml

`site.yml` builds the NixOS VMs, which are the inventory's hosts with `NIXOS: true`. For each host in `target` it runs four stages, and each one has a tag of the same name.

| Stage | What it does |
| --- | --- |
| `vms` | Creates the Proxmox VM through the [opentofu](https://github.com/myah-mitchell/opentofu) repo, when the private repo's `opentofu/prod.tfvars` describes one. The VM is blank and boots the installer ISO |
| `wait` | Waits for the host to answer on its SSH port |
| `nixos` | Installs NixOS when the host is running the installer, then deploys the host's configuration |
| `komodo` | Has Komodo deploy the host's Stacks through a Resource Sync |

```bash
ansible-playbook -i ../fleet-private/hosts.yml site.yml -e target=ex01
```

A host that already runs NixOS is never installed again, so a second run only deploys what changed. With `--check`, nothing is installed, and for a host that already runs NixOS the deploy evaluates its configuration on the control node and prints what would be built, without building it or reaching the host.

### What builds the host

Ansible does not configure a NixOS host. The host's whole system is a NixOS configuration, built by the [nixos-fleet](https://github.com/myah-mitchell/nixos-fleet) flake from two kinds of file in the private repo:

| File | Holds |
| --- | --- |
| `nixos/fleet.json` | The values every host shares: names, domain, accounts, SSH keys |
| `nixos/hosts/<host>.json` | One host's network, features, and the folders, files and ports its stacks need |

`nixos-sync.yml` writes both from the inventory, and `komodo-sync.yml` writes the files Komodo's Resource Sync reads. Run both after any change to a NixOS host in the inventory, then commit what they wrote. `site.yml` stops at a host whose committed files are out of date, and when anything under the private repo's `nixos/` or `secrets/` is not committed, since the flake reads only what git tracks.

```bash
ansible-playbook -i ../fleet-private/hosts.yml nixos-sync.yml
ansible-playbook -i ../fleet-private/hosts.yml komodo-sync.yml
```

Nothing in `site.yml` runs on the host itself, so a NixOS host needs no Python. Every task runs on the control node, where the `nixos` role clones the flake and calls its `host-state`, `install-host` and `deploy-host` commands, which do the SSH.

### The installer ISO

A new VM boots from the installer ISO on its Proxmox host's `local` storage. `provision.yml` puts it there: the `pve` role builds the ISO once on the control node and copies it to every Proxmox VE host. To do only that:

```bash
ansible-playbook -i ../fleet-private/hosts.yml provision.yml \
  -e target=pve_host --tags pve-installer-iso
```

The ISO carries the fleet's installer SSH host key, which `install-host` checks before it sends a host its keys. The key is in the private repo's `secrets/installer.yaml`. Make that file once, where `<flake>` is the nixos-fleet flake, such as `github:myah-mitchell/nixos-fleet`:

```bash
nix run <flake>#new-installer-key -- --fleet ../fleet-private
```

The ISO is built from the files git tracks in the private repo, so commit `nixos/fleet.json` and `secrets/installer.yaml` before building, and build again after the SSH keys in `fleet.json` change. The role stops when either file is untracked or has uncommitted changes, and skips the build when the private repo has no `nixos/fleet.json`. In check mode it checks the two files and neither builds nor copies the ISO.

The setup `site.yml` needs, the environment variables it reads, and what it overwrites are in [How a host is built](https://myah-mitchell.github.io/docs/fleet-bootstrap/concepts/how-a-host-is-built/).

## Using your own environment

Everything real and private lives in a private repo: hostnames, addresses, SSH public keys, CA certificates, the login banner, the account names, and the secrets.

| File | Holds |
| --- | --- |
| `hosts.yml` | The inventory: every host, with its variables |
| `group_vars/all/private.yml` | Fleet values that are not secret, loaded for every host |
| `group_vars/all/secrets.sops.yaml` | The secrets Ansible needs, encrypted with sops |
| `opentofu/prod.tfvars` | The Proxmox servers and the VMs, for `site.yml` |
| `komodo/stacks/<host>.toml` | Each host's Komodo Stacks, written by `komodo-sync.yml` |
| `nixos/` | Each NixOS host's data, written by `nixos-sync.yml` |
| `secrets/` | The secrets the NixOS hosts read, encrypted with sops |

Everything in this repo is generic automation with empty or generic defaults, so it never changes per environment.

To use your own data, build a private repo with those files. [private-repo.example](private-repo.example/) is a skeleton to copy, with full instructions. Check it out next to this repo:

```text
src/
  ansible/          this repo
  fleet-private/    yours
```

Then point Ansible at its inventory:

```bash
cd ansible
ansible-playbook -i ../fleet-private/hosts.yml provision.yml -e target=vh01
```

Ansible loads the `group_vars/` folder next to an inventory file, and the roles find the other files next to it too, so nothing is copied between the two repos. Each stays an ordinary git checkout. Semaphore does the same by reading the inventory from the private repo.

## Forking

The GitHub user or organisation these repos live under is one variable: `github_user` in [group_vars/all/vars.yml](group_vars/all/vars.yml). Change it to your own, and every clone URL in the roles follows.

## Structure

| Path | What it is |
| --- | --- |
| `hosts.yml` | The example inventory, with placeholder data |
| `provision.yml` | Configures an existing Debian-based host. Its roles can be picked by tag |
| `site.yml` | Builds the NixOS VMs: creates them, installs and deploys NixOS, and deploys their Komodo Stacks |
| `nixos-sync.yml` | Writes the private repo's `nixos/` files from the inventory |
| `komodo-sync.yml` | Writes the private repo's `komodo/stacks/<host>.toml` files from the inventory |
| `group_vars/all/vars.yml` | Shared defaults to edit in a fork, which is `github_user` only |
| `group_vars/all/stacks.yml` | `runs_stacks`, the one test of whether a host runs stacks, which the roles and the sync playbooks share |
| `roles/` | One role per concern |
| `private-repo.example/` | A worked example of the private repo |

Most roles configure a Debian-based host and run from `provision.yml`. Four belong to `site.yml` and the two sync playbooks, and run on the control node only:

| Role | What it does |
| --- | --- |
| `vms` | Creates the VMs through OpenTofu |
| `nixos` | Writes a host's NixOS data, and installs and deploys NixOS |
| `stacks` | Works out which stacks a host runs |
| `komodo_stacks` | Writes a host's Komodo sync file, and deploys its Stacks |
