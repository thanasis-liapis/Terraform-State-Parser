# Terraform State Parser

Terraform State Parser is a python script that parses a terraform state file and produces an ansible inventory file.


### How to use the script

The primary group of each host (defined by an openstack compute instance v2) is read by the metadata attribute 'cluster' of the specific resource. Using the following custom metadata attributes, you can further define the following ansible inventory variables that control how ansible communicates with provisioning remote hosts...

* ansible_port: Define the connection port for SSH-type connections to the remote host, if not the default 22.
* ansible_user: Define the user name to use when connecting to the remote host.
* ansible_ssh_private_key_file: Define a private key to use by SSH protocol for connecting to the remote host. Useful if multiple keys are required.
* ansible_extra_groups: Define secondary ansible inventory groups that the specific host belongs to, separeted by comma.


### Arguments to provide in the script

1. Provide the path (absolute or relative) to the terraform state file
2. Provide the type of IP that the script should use to generate the inventory file.
	There are two different types of IP addresses that a host can obtain. These are
	* Fixed IP
	* Floating IP
	
	Depending on which IP is accessible by the ansible provisioning host, generate inventory file either with argument [-floating] when floating ip is the one that gives access to the host, or [-fixed] when the internal, fixed ip of the host provides the required accessibility to remote ansible provisioning host.


### Generic Information
This version supports infrastructure that is created 
1. using only root module resources.
2. using only child module resources.
3. using both root and child module resources.

Supports both fixed and floating ips for inventory file. Depending on the index given the corresponding NIC is used.
For example, if 'fixed 1' is given as input, then the IPs assigned to the eth1 NIC are used in the inventory. If eth1 does not exist, then the eth0 is used.
If no NIC index is given, NIC 0 is used. If 'floating 1' is given as input, then the floating IP associated with the eth1 NIC is used. If no floating IP is associated
with the specified NIC, then the corresponding value in the inventory file will be 'null'.

Supports both floating ips created dynamically and floating ip associated with fixed ips (pre-existing floating ips). In order to use the floating ips provided by the 
openstack_networking_floatingip_associate_v2 module, use 'floating <index> associate'. If, on the other hand, you want to use floating ips created dynamically and provided
by the openstack_networking_floatingip_v2 module, use 'floating <index> ip'. The latter is the default, if no value is given.

Supports setting variable [ansible_python_interpreter] into inventory file for ansible

Requires terraform v0.12.x. Supports only terraform state files of version 4.

