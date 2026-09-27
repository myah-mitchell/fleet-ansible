# Private repo: starter skeleton

This folder is a worked example of the private repo that holds your real environment. The public ansible repo never reads it at run time. Copy it to start your own private repo, for running this project against your real hosts instead of the example data.

## Why two repos

The public ansible repo runs on its own against the example inventory in its root `hosts.yml`, with every private value falling back to an empty role default. Nothing you would rather not publish has to live in a public repo: real hostnames and addresses, SSH keys, CA certificates, a login banner, and the secrets. It all lives in the private repo, which this folder mirrors.

| File | Written by | Holds |
| --- | --- | --- |
| `hosts.yml` | You | The inventory: what each host is, and which stacks it runs |
| `group_vars/all/private.yml` | You | Fleet values that are not secret |
| `group_vars/all/secrets.sops.yaml` | You, through sops | The secrets Ansible needs for the Proxmox hosts |
| `opentofu/prod.tfvars` | You | The Proxmox servers, and each VM's size, disks and network |
| `komodo/stacks/<host>.toml` | `komodo-sync.yml` | Each host's Komodo Stacks, which Komodo's Resource Sync reads |
| `nixos/fleet.json` | `nixos-sync.yml` | The values every NixOS host shares |
| `nixos/hosts/<host>.json` | `nixos-sync.yml` | One NixOS host's network, features, and what its stacks need |
| `secrets/fleet.yaml` | You, through sops | The secrets every NixOS host reads |
| `secrets/hosts/<host>.yaml` | You, through sops | One host's own secrets. Optional |
| `secrets/host-keys/<host>.yaml` | `new-host-key` | The host's SSH host keys, which no host can read |
| `secrets/installer.yaml` | `new-installer-key` | The installer ISO's SSH host key, which no host can read |
| `.sops.yaml` | You, `new-host-key` and `new-installer-key` | Who can decrypt each sops file |

Each file owns one kind of fact, and the host name links them. `opentofu/prod.tfvars` repeats a VM's address, prefix length and gateway, and `site.yml` fails when they differ from the inventory.

`provision.yml` needs only `hosts.yml` and the two files under `group_vars/all/`. The rest matter to `site.yml`.

## What this folder leaves out

This folder has no encrypted file, since a sops file is only readable with its key.

| Left out | In its place |
| --- | --- |
| `group_vars/all/secrets.sops.yaml` | `group_vars/all/secrets.sops.yaml.example`, which shows the keys before encryption. Ansible does not load it |
| `secrets/` | Nothing. The nixos-fleet repo's `example/` folder shows these files |
| `komodo/` | Nothing. Run `komodo-sync.yml` against this inventory to see the files |

The age keys in `.sops.yaml` are placeholders, so sops rejects the file until they are replaced with real ones.

The files under `nixos/` are what `nixos-sync.yml` wrote from this inventory. They hold the text of docker-stacks' seed files, so they go out of date when docker-stacks changes one.

## Secrets

Every secret is encrypted with sops to age keys, and `.sops.yaml` lists which keys can decrypt which file.

| Key | Whose it is | Decrypts |
| --- | --- | --- |
| `admin` | A person. The private key is in a password manager | Every file |
| `deploy` | The control node and Semaphore, from `SOPS_AGE_KEY` or `SOPS_AGE_KEY_FILE` | Every file |
| One per host | The host, derived from its ed25519 SSH host key | `secrets/fleet.yaml` and its own `secrets/hosts/<host>.yaml` |

Ansible loads `group_vars/all/secrets.sops.yaml` like any other variables file, decrypting it on the control node. Once that file exists, every playbook run against this inventory needs sops and a key that decrypts it, the two sync playbooks included.

> [!WARNING]
> Never commit a private age key, or a secrets file before sops has encrypted it. The repo being private does not make either one safe.

## Building your own

These steps need nix with flakes enabled, sops, and age on the control node. They use three placeholders.

| Placeholder | Value |
| --- | --- |
| `<admin-public-key>` | The public key `age-keygen` prints for your own key |
| `<deploy-public-key>` | The public key `age-keygen` prints for the deploy key |
| `<host>` | A NixOS host's name in `hosts.yml`, such as `ex01` |

1. Create a new private git repo, such as `fleet-private`, and check it out next to the public repo.
2. Copy this folder's files into it, at the same relative paths, leaving out `nixos/` and `secrets.sops.yaml.example`.
3. Fill in your real values in `hosts.yml`, `group_vars/all/private.yml` and `opentofu/prod.tfvars`. The comments in each file say what a value drives.
4. Make the admin key and the deploy key, one run each, and keep both files out of the repo:

   ```bash
   age-keygen -o admin.key
   age-keygen -o deploy.key
   ```

5. In `.sops.yaml`, replace the `admin` and `deploy` placeholders with `<admin-public-key>` and `<deploy-public-key>`. Remove the `ex01` key, the rule for its own file, and its name in the rule for `secrets/fleet.yaml`.
6. Make each NixOS host's SSH host keys, which also adds the host to `.sops.yaml`:

   ```bash
   nix run github:myah-mitchell/nixos-fleet#new-host-key -- --fleet ../fleet-private <host>
   ```

7. Make the installer's SSH host key. The installer ISO is built with it, and `install-host` sends a host its keys only to a machine that has it:

   ```bash
   nix run github:myah-mitchell/nixos-fleet#new-installer-key -- --fleet ../fleet-private
   ```

8. Write the two secrets files. Each command opens an editor and encrypts on save:

   ```bash
   cd ../fleet-private
   sops group_vars/all/secrets.sops.yaml
   sops secrets/fleet.yaml
   ```

   The first holds `server_password`. The second holds `server-password-hash` and `komodo-onboarding-key`.
9. Write the generated files, from the public repo's checkout:

   ```bash
   ansible-playbook -i ../fleet-private/hosts.yml nixos-sync.yml
   ansible-playbook -i ../fleet-private/hosts.yml komodo-sync.yml
   ```

10. Commit everything in the private repo. The flake reads only the files git tracks, so a file that is not committed does not reach a host.

If you have forked the public ansible repo under your own GitHub account, set `github_user` in its `group_vars/all/vars.yml` to match. That is the only place your GitHub user name is recorded.

## Keeping it current

Run the two sync playbooks again whenever a NixOS host changes in `hosts.yml`, a fleet value changes in `private.yml`, or docker-stacks changes a stack. Commit what they wrote. `site.yml` stops at a host whose committed files are out of date.

## Using it

Point Ansible at the private repo's inventory. Ansible loads the `group_vars/` folder next to an inventory file, and the roles find the other folders there too, so nothing is copied between the repos.

```bash
cd ansible
ansible-playbook -i ../fleet-private/hosts.yml provision.yml -e target=vh01
ansible-playbook -i ../fleet-private/hosts.yml site.yml -e target=ex01
```

Both repos stay ordinary git checkouts. Commit and push changes to the private repo from its own folder. Semaphore reads the inventory straight from the private repo, so a pushed change applies to its next run.
