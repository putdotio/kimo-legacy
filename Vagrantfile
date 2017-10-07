# -*- mode: ruby -*-
# vi: set ft=ruby :

PRIVATE_IP = "192.168.74.2"

Vagrant.configure("2") do |config|
  config.vm.box = "ubuntu/xenial64"
  config.vm.box_check_update = false

  # Network
  config.vm.network :private_network, ip: PRIVATE_IP
  config.vm.network :forwarded_port, guest: 35759, host: 35759

  config.vm.synced_folder ".", "/kimo"
end
