# The VMs site.yml creates, for the example hosts in hosts.yml. The reference
# for this file, with every rule and key explained, is the opentofu repo's
# envs/prod/terraform.tfvars.example.

servers = {
  vh01 = {
    endpoint     = "https://203.0.113.11:8006/"
    insecure     = true
    default_node = "vh01"
  }
}

vms = {
  ex01 = {
    server       = "vh01"
    cores        = 2
    memory_mb    = 4096
    vlan_id      = 7
    ipv4_address = "192.0.2.110/24"
    ipv4_gateway = "192.0.2.1"
    dns_servers  = ["192.0.2.1"]

    extra_disks = {
      persist = { interface = "scsi2", size_gb = 20 }
    }
  }
}
