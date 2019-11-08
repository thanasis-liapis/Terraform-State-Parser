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
3. using both root and child module resiources.

In case of creating an infrastructure with no floating ips, the ip that will be used for remote connection is the ip of the network interface that will be defined in the cmd. If no NIC index is given, NIC 0 is used.

Requires terraform v0.12.x. Supports only terraform state files of version 4.

Tfstate2inventory v5 includes fix for error produced when no resources of one or more modules existed in an IaC configuration.
