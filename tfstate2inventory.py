#!/usr/bin/env python3
#
# Script for parsing terraform state information and
# generating a dynamic ansible inventory file using
# terraform show command
#
# Date: 20211109
# Version: v7.1
#
# - This version supports infrastructure that is created 
#   1. using only root module resources.
#   2. using only child module resources.
#   3. using both root and child module resources.
#
# - Supports both fixed and floating ips for inventory file. Depending on the index given the corresponding NIC is used.
#   For example, if 'fixed 1' is given as input, then the IPs assigned to the eth1 NIC are used in the inventory. If eth1 does not exist, then the eth0 is used.
#   If no NIC index is given, NIC 0 is used. If 'floating 1' is given as input, then the floating IP associated with the eth1 NIC is used. If no floating IP is associated
#   with the specified NIC, then the corresponding value in the inventory file will be 'null'.
# - Supports both floating ips created dynamically and floating ip associated with fixed ips (pre-existing floating ips). In order to use the floating ips provided by the 
#   openstack_networking_floatingip_associate_v2 module, use 'floating <index> associate'. If, on the other hand, you want to use floating ips created dynamically and provided
#   by the openstack_networking_floatingip_v2 module, use 'floating <index> ip'. The latter is the default, if no value is given.
#
# - Supports setting variable [ansible_python_interpreter] into inventory file for ansible
#
# - Requires terraform v0.12.x. Supports only terraform state files of version 4.
#
import json
import yaml
import subprocess
import os
import getopt
import sys
import urllib.request,urllib.parse
from urllib.error import HTTPError,URLError,ContentTooShortError
from socket import gethostbyname,gaierror

urlelement = []
tfresourceslist = []
allcomputeresourcesattr = []
allfloatingresourcesattr = []
iptype = 'floating'

if len(sys.argv) == 1:
  sys.stderr.write('Error[700] ::: Usage: tfstate2inventory.py [mandatory:<url>|<file>] [optional:floating|fixed] [optional:<nic index>] [optional:ip|associate]\nFirst argument is the path or the URL to terraforma state file. Second, optional argument is the word "floating" or "fixed" that defines which IP address is going to be used to generate inventory. Third optional argument is the index of the NIC that is going to be used for remote communication by ansible (in case of multiple networks attached to a host). Defaults to 0 which is the first NIC of the host. Forth optional argument is the type of the floating ip used. Floating IPs can be derived from the floatingip module of terraform when floating IPs are created dynamically through the build process, or from the floatingip_associate module, when floating IPs already exist into the project and are associated with dynamically create ports of the project. Defaults to ip, assuming that floating IPs are created by the build process.\n')
  sys.exit(700)
elif len(sys.argv) == 5:
  if sys.argv[2] != 'floating' and sys.argv[2] != 'fixed':
    sys.stderr.write('Error[701] ::: Usage: tfstate2inventory.py [mandatory:<url>|<file>] [optional:floating|fixed] [optional:<nic index>] [optional:ip|associate]\nSecond argument must be one of [floating|fixed]. Third the index of the NIC that is going to be used for remote communication. Usually a number between 0-2.\nForth argument must be one of [ip|associate].\n')
    sys.exit(701)
  else:
    TERRAFORMSTATELOCATION = sys.argv[1]
    iptype = sys.argv[2]
    nic = sys.argv[3]
    if sys.argv[4] == 'ip':
      floating_module = 'openstack_networking_floatingip_v2'
    elif sys.argv[4] == 'associate':
      floating_module = 'openstack_networking_floatingip_associate_v2'
    else:
      sys.stderr.write('Error[702] ::: Usage: tfstate2inventory.py [mandatory:<url>|<file>] [optional:floating|fixed] [optional:<nic index>] [optional:ip|associate]\nSecond argument must be one of [floating|fixed]. Third the index of the NIC that is going to be used for remote communication. Usually a number between 0-2.\nForth argument must be one of [ip|associate].\n')
      sys.exit(702)
elif len(sys.argv) == 4:
  if sys.argv[2] != 'floating' and sys.argv[2] != 'fixed':
    sys.stderr.write('Error[703] ::: Usage: tfstate2inventory.py [mandatory:<url>|<file>] [optional:floating|fixed] [optional:<nic index>] [optional:ip|associate]\nSecond argument must be one of [floating|fixed]. Third the index of the NIC that is going to be used for remote communication. Usually a number between 0-2.\nForth argument must be one of [ip|associate].\n')
    sys.exit(703)
  else:
    TERRAFORMSTATELOCATION = sys.argv[1]
    iptype = sys.argv[2]
    nic = sys.argv[3]
    floating_module = 'openstack_networking_floatingip_v2'
elif len(sys.argv) == 3:
  if sys.argv[2] != 'floating' and sys.argv[2] != 'fixed':
    sys.stderr.write('Error[704] ::: Usage: tfstate2inventory.py [mandatory:<url>|<file>] [optional:floating|fixed] [optional:<nic index>] [optional:ip|associate]\nSecond argument must be one of [floating|fixed]. Third the index of the NIC that is going to be used for remote communication. Usually a number between 0-2.\nForth argument must be one of [ip|associate].\n')
    sys.exit(704)
  else:
    TERRAFORMSTATELOCATION = sys.argv[1]
    iptype = sys.argv[2]
    nic = 0
    floating_module = 'openstack_networking_floatingip_v2'
elif len(sys.argv) == 2:
  TERRAFORMSTATELOCATION = sys.argv[1]
  iptype = 'floating'
  nic = 0
  floating_module = 'openstack_networking_floatingip_v2'
else:
  sys.stderr.write('Error[706] ::: Usage: tfstate2inventory.py [mandatory:<url>|<file>] [optional:floating|fixed] [optional:<nic index>] [optional:ip|associate]\nSecond argument must be one of [floating|fixed]. Third the index of the NIC that is going to be used for remote communication. Usually a number between 0-2.\nForth argument must be one of [ip|associate].\n')
  sys.exit(706)

if TERRAFORMSTATELOCATION.startswith('http://') or TERRAFORMSTATELOCATION.startswith('https://'):
  urlelement = urllib.parse.urlparse(TERRAFORMSTATELOCATION)
  hostname = urlelement[1].split(':')
  try:
    gethostbyname(hostname[0])
  except gaierror as se:
    sys.stderr.write('Error[707] ::: Could not resolve hostname ['+hostname[0]+']. Please check for typos or dns resolving issues. Reason: '+se.strerror+'\n')
    sys.exit(707)
  try:
    urllib.request.urlretrieve(TERRAFORMSTATELOCATION, 'terraform.tfstate')
  except (URLError,HTTPError,ContentTooShortError) as urle:
    sys.stderr.write('Error[708] ::: Error during retrieval of remote terraform state file from ['+TERRAFORMSTATELOCATION+']. Reason: '+urle.reason+'\n')
    sys.exit(708)
  TERRAFORMSTATEFILE = 'terraform.tfstate'
else:
  TERRAFORMSTATEFILE = TERRAFORMSTATELOCATION

if os.path.exists(TERRAFORMSTATEFILE) and os.access(TERRAFORMSTATEFILE, os.R_OK):
  try:
    tfstatejson = subprocess.Popen(["terraform","show","-json",TERRAFORMSTATEFILE], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  except subprocess.CalledProcessError as sperr:
    sys.stderr.write('Error[709] ::: Error when executing terraform command.\n'+sperr.output+'\n')
    sys.exit(709)
else:
  sys.stderr.write('Error[710] ::: Input file ['+TERRAFORMSTATEFILE+'] could not be found or read.\n')
  sys.exit(710)

cmdout,cmderr = tfstatejson.communicate()
cmdrc = tfstatejson.returncode
if cmdrc != 0:
  sys.stderr.write('Error[711] ::: Error when executing terraform command.\n'+cmdout.decode('ascii')+cmderr.decode('ascii')+'\n')
  sys.exit(711)

terraformstate = json.loads(cmdout)

# Populate list of recourses with the resources created in the root module.
try:
  for resource_index in range(len(terraformstate['values']['root_module']['resources'])):
    try:
      if 'openstack_compute_instance_v2' in terraformstate['values']['root_module']['resources'][resource_index]['address']:
        computeresourceattr = {}
        computeresourceattr['id'] = terraformstate['values']['root_module']['resources'][resource_index]['values']['id']
        computeresourceattr['metadata_cluster'] = terraformstate['values']['root_module']['resources'][resource_index]['values']['metadata']['cluster']
        if 'ansible_extra_groups' in terraformstate['values']['root_module']['resources'][resource_index]['values']['metadata'] and terraformstate['values']['root_module']['resources'][resource_index]['values']['metadata']['ansible_extra_groups']:
          computeresourceattr['metadata_ansible_extra_groups'] = terraformstate['values']['root_module']['resources'][resource_index]['values']['metadata']['ansible_extra_groups']
        if 'ansible_port' in terraformstate['values']['root_module']['resources'][resource_index]['values']['metadata']:
          computeresourceattr['metadata_ansible_port'] = terraformstate['values']['root_module']['resources'][resource_index]['values']['metadata']['ansible_port']
        if 'ansible_user' in terraformstate['values']['root_module']['resources'][resource_index]['values']['metadata']:
          computeresourceattr['metadata_ansible_user'] = terraformstate['values']['root_module']['resources'][resource_index]['values']['metadata']['ansible_user']
        if 'ansible_ssh_private_key_file' in terraformstate['values']['root_module']['resources'][resource_index]['values']['metadata']:
          computeresourceattr['metadata_ansible_ssh_private_key_file'] = terraformstate['values']['root_module']['resources'][resource_index]['values']['metadata']['ansible_ssh_private_key_file']
        if 'ansible_python_interpreter' in terraformstate['values']['root_module']['resources'][resource_index]['values']['metadata']:
          computeresourceattr['metadata_ansible_python_interpreter'] = terraformstate['values']['root_module']['resources'][resource_index]['values']['metadata']['ansible_python_interpreter']
        computeresourceattr['name'] = terraformstate['values']['root_module']['resources'][resource_index]['values']['name']
        try:
          computeresourceattr['network.0.fixed_ip_v4'] = terraformstate['values']['root_module']['resources'][resource_index]['values']['network'][int(nic)]['fixed_ip_v4']
        except IndexError:
          sys.stderr.write('INFO ::: NIC with index '+nic+' does not exist on host with id '+computeresourceattr['id']+'. Auto revert index to 0..\n')
          computeresourceattr['network.0.fixed_ip_v4'] = terraformstate['values']['root_module']['resources'][resource_index]['values']['network'][0]['fixed_ip_v4']
        allcomputeresourcesattr.append(computeresourceattr)
      elif floating_module in terraformstate['values']['root_module']['resources'][resource_index]['address']:
        floatingresourceattr = {}
        floatingresourceattr['fixed_ip'] = terraformstate['values']['root_module']['resources'][resource_index]['values']['fixed_ip']
        if floating_module == 'openstack_networking_floatingip_associate_v2':
          floatingresourceattr['floating_ip'] = terraformstate['values']['root_module']['resources'][resource_index]['values']['floating_ip']
        elif floating_module == 'openstack_networking_floatingip_v2':
          floatingresourceattr['floating_ip'] = terraformstate['values']['root_module']['resources'][resource_index]['values']['address']
        allfloatingresourcesattr.append(floatingresourceattr)
    except KeyError:
      sys.stderr.write('INFO ::: Root module with no data found.\n')
except KeyError:
  sys.stderr.write('INFO ::: No root module resources found.\n')

# Populate list of recourses with the resources created in child modules.
try:
  for resource_index in range(len(terraformstate['values']['root_module']['child_modules'])):
    try:
      for child_resource_index in range(len(terraformstate['values']['root_module']['child_modules'][resource_index]['resources'])):
        if 'openstack_compute_instance_v2' in terraformstate['values']['root_module']['child_modules'][resource_index]['resources'][child_resource_index]['address']:
          computeresourceattr = {}
          computeresourceattr['id'] = terraformstate['values']['root_module']['child_modules'][resource_index]['resources'][child_resource_index]['values']['id']
          computeresourceattr['metadata_cluster'] = terraformstate['values']['root_module']['child_modules'][resource_index]['resources'][child_resource_index]['values']['metadata']['cluster']
          if 'ansible_extra_groups' in terraformstate['values']['root_module']['child_modules'][resource_index]['resources'][child_resource_index]['values']['metadata'] and terraformstate['values']['root_module']['child_modules'][resource_index]['resources'][child_resource_index]['values']['metadata']['ansible_extra_groups']:
            computeresourceattr['metadata_ansible_extra_groups'] = terraformstate['values']['root_module']['child_modules'][resource_index]['resources'][child_resource_index]['values']['metadata']['ansible_extra_groups']
          if 'ansible_port' in terraformstate['values']['root_module']['child_modules'][resource_index]['resources'][child_resource_index]['values']['metadata']:
            computeresourceattr['metadata_ansible_port'] = terraformstate['values']['root_module']['child_modules'][resource_index]['resources'][child_resource_index]['values']['metadata']['ansible_port']
          if 'ansible_user' in terraformstate['values']['root_module']['child_modules'][resource_index]['resources'][child_resource_index]['values']['metadata']:
            computeresourceattr['metadata_ansible_user'] = terraformstate['values']['root_module']['child_modules'][resource_index]['resources'][child_resource_index]['values']['metadata']['ansible_user']
          if 'ansible_ssh_private_key_file' in terraformstate['values']['root_module']['child_modules'][resource_index]['resources'][child_resource_index]['values']['metadata']:
            computeresourceattr['metadata_ansible_ssh_private_key_file'] = terraformstate['values']['root_module']['child_modules'][resource_index]['resources'][child_resource_index]['values']['metadata']['ansible_ssh_private_key_file']
          if 'ansible_python_interpreter' in terraformstate['values']['root_module']['child_modules'][resource_index]['resources'][child_resource_index]['values']['metadata']:
            computeresourceattr['metadata_ansible_python_interpreter'] = terraformstate['values']['root_module']['child_modules'][resource_index]['resources'][child_resource_index]['values']['metadata']['ansible_python_interpreter']
          computeresourceattr['name'] = terraformstate['values']['root_module']['child_modules'][resource_index]['resources'][child_resource_index]['values']['name']
          try:
            computeresourceattr['network.0.fixed_ip_v4'] = terraformstate['values']['root_module']['child_modules'][resource_index]['resources'][child_resource_index]['values']['network'][int(nic)]['fixed_ip_v4']
          except IndexError:
            sys.stderr.write('INFO ::: NIC with index '+nic+' does not exist on host with id '+computeresourceattr['id']+'. Auto revert index to 0..\n')
            computeresourceattr['network.0.fixed_ip_v4'] = terraformstate['values']['root_module']['child_modules'][resource_index]['resources'][child_resource_index]['values']['network'][0]['fixed_ip_v4']
          allcomputeresourcesattr.append(computeresourceattr)
        elif floating_module in terraformstate['values']['root_module']['child_modules'][resource_index]['resources'][child_resource_index]['address']:
          floatingresourceattr = {}
          floatingresourceattr['fixed_ip'] = terraformstate['values']['root_module']['child_modules'][resource_index]['resources'][child_resource_index]['values']['fixed_ip']
          if floating_module == 'openstack_networking_floatingip_associate_v2':
            floatingresourceattr['floating_ip'] = terraformstate['values']['root_module']['child_modules'][resource_index]['resources'][child_resource_index]['values']['floating_ip']
          elif floating_module == 'openstack_networking_floatingip_v2':
            floatingresourceattr['floating_ip'] = terraformstate['values']['root_module']['child_modules'][resource_index]['resources'][child_resource_index]['values']['address']
          allfloatingresourcesattr.append(floatingresourceattr)
    except KeyError:
      sys.stderr.write('INFO ::: Module with no data found.\n')
except KeyError:
  sys.stderr.write('INFO ::: No child module resources found.\n')

for cres in range(len(allcomputeresourcesattr)):
  for fres in range(len(allfloatingresourcesattr)):
    if allcomputeresourcesattr[cres]['network.0.fixed_ip_v4'] == allfloatingresourcesattr[fres]['fixed_ip']:
      allcomputeresourcesattr[cres]['floating_ip'] = allfloatingresourcesattr[fres]['floating_ip']

inventory = {}
inventory['all'] = {}
inventory['all']['children'] = {}

for indexc in range(len(allcomputeresourcesattr)):
  sshport = None
  sshuser = None
  sshkey = None
  extragroups = None
  name = allcomputeresourcesattr[indexc]['name']
  try:
    floatingip = allcomputeresourcesattr[indexc]['floating_ip']
  except KeyError:
    sys.stderr.write('INFO ::: No floating ip key exists on compute instance resources list.\n')
    floatingip = None
  fixedip = allcomputeresourcesattr[indexc]['network.0.fixed_ip_v4']
  group = allcomputeresourcesattr[indexc]['metadata_cluster']
  if 'metadata_ansible_port' in allcomputeresourcesattr[indexc]:
    sshport = allcomputeresourcesattr[indexc]['metadata_ansible_port']
  if 'metadata_ansible_user' in allcomputeresourcesattr[indexc]:
    sshuser = allcomputeresourcesattr[indexc]['metadata_ansible_user']
  if 'metadata_ansible_ssh_private_key_file' in allcomputeresourcesattr[indexc]:
    sshkey = allcomputeresourcesattr[indexc]['metadata_ansible_ssh_private_key_file']
  if 'metadata_ansible_python_interpreter' in allcomputeresourcesattr[indexc]:
    python = allcomputeresourcesattr[indexc]['metadata_ansible_python_interpreter']
  if 'metadata_ansible_extra_groups' in allcomputeresourcesattr[indexc]:
    extragroups = allcomputeresourcesattr[indexc]['metadata_ansible_extra_groups'].split(',')
  if group in inventory['all']['children']:
    inventory['all']['children'][group]['hosts'][name] = {}
    if iptype == 'floating':
      inventory['all']['children'][group]['hosts'][name]['ansible_host'] = floatingip
    elif iptype == 'fixed':
      inventory['all']['children'][group]['hosts'][name]['ansible_host'] = fixedip
    if sshport:
      inventory['all']['children'][group]['hosts'][name]['ansible_port'] = int(sshport)
    if sshuser:
      inventory['all']['children'][group]['hosts'][name]['ansible_user'] = sshuser
    if sshkey:
      inventory['all']['children'][group]['hosts'][name]['ansible_ssh_private_key_file'] = sshkey
    if python:
      inventory['all']['children'][group]['hosts'][name]['ansible_python_interpreter'] = python
  else:
    inventory['all']['children'][group] = {}
    inventory['all']['children'][group]['hosts'] = {}
    inventory['all']['children'][group]['hosts'][name] = {}
    if iptype == 'floating':
      inventory['all']['children'][group]['hosts'][name]['ansible_host'] = floatingip
    elif iptype == 'fixed':
      inventory['all']['children'][group]['hosts'][name]['ansible_host'] = fixedip
    if sshport:
      inventory['all']['children'][group]['hosts'][name]['ansible_port'] = int(sshport)
    if sshuser:
      inventory['all']['children'][group]['hosts'][name]['ansible_user'] = sshuser
    if sshkey:
      inventory['all']['children'][group]['hosts'][name]['ansible_ssh_private_key_file'] = sshkey
    if python:
      inventory['all']['children'][group]['hosts'][name]['ansible_python_interpreter'] = python
  if extragroups:
    for secgroup in extragroups:
      if secgroup in inventory['all']['children']:
        inventory['all']['children'][secgroup]['hosts'][name] = {}
        if iptype == 'floating':
          inventory['all']['children'][secgroup]['hosts'][name]['ansible_host'] = floatingip
        elif iptype == 'fixed':
          inventory['all']['children'][secgroup]['hosts'][name]['ansible_host'] = fixedip
        if sshport:
          inventory['all']['children'][secgroup]['hosts'][name]['ansible_port'] = int(sshport)
        if sshuser:
          inventory['all']['children'][secgroup]['hosts'][name]['ansible_user'] = sshuser
        if sshkey:
          inventory['all']['children'][secgroup]['hosts'][name]['ansible_ssh_private_key_file'] = sshkey
        if python:
          inventory['all']['children'][group]['hosts'][name]['ansible_python_interpreter'] = python
      else:
        inventory['all']['children'][secgroup] = {}
        inventory['all']['children'][secgroup]['hosts'] = {}
        inventory['all']['children'][secgroup]['hosts'][name] = {}
        if iptype == 'floating':
          inventory['all']['children'][secgroup]['hosts'][name]['ansible_host'] = floatingip
        elif iptype == 'fixed':
          inventory['all']['children'][secgroup]['hosts'][name]['ansible_host'] = fixedip
        if sshport:
          inventory['all']['children'][secgroup]['hosts'][name]['ansible_port'] = int(sshport)
        if sshuser:
          inventory['all']['children'][secgroup]['hosts'][name]['ansible_user'] = sshuser
        if sshkey:
          inventory['all']['children'][secgroup]['hosts'][name]['ansible_ssh_private_key_file'] = sshkey
        if python:
          inventory['all']['children'][group]['hosts'][name]['ansible_python_interpreter'] = python

with open('inventory', 'w') as outfile:
  print(yaml.safe_dump(inventory, outfile, default_flow_style=False))
print(yaml.safe_dump(inventory, default_flow_style=False))
