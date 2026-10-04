# The VMs site.yml creates, for the example hosts in hosts.yml. The reference
# for this file, with every rule and key explained, is the fleet-opentofu repo's
# envs/prod/terraform.tfvars.example.

servers = {
  vh01 = {
    endpoint     = "https://172.16.1.11:8006/"
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
    ipv4_address = "172.16.7.91/24"
    ipv4_gateway = "172.16.7.1"
    dns_servers  = ["172.16.7.1"]

    extra_disks = {
      persist = { interface = "scsi2", size_gb = 20 }
    }
  }
}
